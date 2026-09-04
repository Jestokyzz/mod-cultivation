[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$ClientRoot='C:\Solo WotLK\test-client\20260831-rogue-paths-v3',
    [string]$ServerRoot='C:\Solo WotLK\test-server\20260831-rogue-paths-v3',
    [string]$PackageDirectory=(Join-Path $PSScriptRoot 'build\v1.5.0-candidate1'),
    [switch]$ClearClientCache
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$ClientRoot=[IO.Path]::GetFullPath($ClientRoot)
$ServerRoot=[IO.Path]::GetFullPath($ServerRoot)
if ($ClientRoot -ne 'C:\Solo WotLK\test-client\20260831-rogue-paths-v3' -or $ServerRoot -ne 'C:\Solo WotLK\test-server\20260831-rogue-paths-v3') { throw 'Unaccepted candidate: only named v3 clones allowed' }
$backupBase='F:\JestokyCraft Backups\rogue-paths'
if (!(Test-Path -LiteralPath $backupBase) -or (Get-PSDrive F).Free -lt 10GB) {throw 'F: backup gate failed'}
foreach ($process in Get-CimInstance Win32_Process) {
    if ($process.ExecutablePath -and ($process.ExecutablePath.StartsWith($ClientRoot+'\',[StringComparison]::OrdinalIgnoreCase) -or $process.ExecutablePath.StartsWith($ServerRoot+'\',[StringComparison]::OrdinalIgnoreCase))) {throw 'Stop exact v3 client/server before installation'}
}
$manifest=Get-Content -LiteralPath "$PackageDirectory\manifest.json" -Raw | ConvertFrom-Json
if ($manifest.schema_version -ne 5 -or $manifest.version -ne '1.5.0' -or $manifest.static_validation -ne 'passed') {throw 'Wrong candidate'}
if ((Get-FileHash -LiteralPath "$ClientRoot\Wow-NWQ.exe").Hash -ne $manifest.compatibility.client_exe_sha256) {throw 'Client EXE compatibility mismatch'}
$config=Get-Content -LiteralPath "$ClientRoot\WTF\Config.wtf" -Raw
foreach ($line in @('SET gxWindow "1"','SET gxMaximize "1"','SET gxResolution "1920x1080"')) {if (!$config.Contains($line)) {throw '1920x1080 borderless configuration required'}}
$sqlManifest=Get-Content -LiteralPath "$PackageDirectory\sql\manifest.json" -Raw | ConvertFrom-Json
foreach ($file in $sqlManifest.files.PSObject.Properties) {if ((Get-FileHash -LiteralPath "$PackageDirectory\sql\$($file.Name)").Hash -ne $file.Value) {throw 'SQL package hash mismatch'}}
$transfers=@()
foreach ($file in $manifest.files.PSObject.Properties) {$transfers+=@{Source="$PackageDirectory\$($file.Name)";Target="$ClientRoot\Data\ruRU\$($file.Name)";Hash=$file.Value}}
foreach ($file in $manifest.addon.PSObject.Properties) {$transfers+=@{Source=(Join-Path $PackageDirectory $file.Name);Target=(Join-Path $ClientRoot $file.Name);Hash=$file.Value}}
foreach ($file in $manifest.server_dbc.PSObject.Properties) {$transfers+=@{Source="$PackageDirectory\server\dbc\$($file.Name)";Target="$ServerRoot\data\dbc\$($file.Name)";Hash=$file.Value}}
$transfers+=@{Source="$PackageDirectory\server\worldserver.exe";Target="$ServerRoot\worldserver.exe";Hash=$manifest.worldserver_sha256}
foreach ($file in $transfers) {
    $file.Target=[IO.Path]::GetFullPath($file.Target)
    if (!($file.Target.StartsWith($ClientRoot+'\',[StringComparison]::OrdinalIgnoreCase) -or $file.Target.StartsWith($ServerRoot+'\',[StringComparison]::OrdinalIgnoreCase))) {throw 'Transfer escaped clone root'}
    if ((Get-FileHash -LiteralPath $file.Source).Hash -ne $file.Hash) {throw 'Artifact hash mismatch'}
}
$addonStates=@(Get-ChildItem -LiteralPath "$ClientRoot\WTF" -Recurse -File -Filter AddOns.txt | ForEach-Object FullName)
if (!$PSCmdlet.ShouldProcess("$ClientRoot and $ServerRoot",'Back up files and SQL on F:, restore-check SQL, deploy isolated schema 5')) {return}
$backup=Join-Path $backupBase ('pre-change-schema5-install-'+(Get-Date -Format 'yyyyMMddTHHmmss'))
New-Item -ItemType Directory -Path $backup,"$backup\files","$backup\restore-check" | Out-Null
$records=@()
$targets=@($transfers | ForEach-Object {$_.Target})+$addonStates
foreach ($target in $targets | Sort-Object -Unique) {
    $saved=Join-Path "$backup\files" (($target.Substring(3)) -replace '[:\\/]','_')
    $existed=Test-Path -LiteralPath $target -PathType Leaf
    $hash=$null
    if ($existed) {
        $hash=(Get-FileHash -LiteralPath $target).Hash
        Copy-Item -LiteralPath $target -Destination $saved
        $probe=Join-Path "$backup\restore-check" (Split-Path $saved -Leaf)
        Copy-Item -LiteralPath $saved -Destination $probe
        if ((Get-FileHash -LiteralPath $saved).Hash -ne $hash -or (Get-FileHash -LiteralPath $probe).Hash -ne $hash) {throw 'File backup/restore mismatch'}
    }
    $records+=@{Target=$target;Backup=$saved;Existed=$existed;SHA256=$hash}
}
$mysqlBin='C:\Solo WotLK\WoWBotServer\deps\mysql-8.4.10-winx64\bin'
$secrets=@{}
foreach ($line in Get-Content -LiteralPath 'C:\Solo WotLK\WoWBotServer\.local-secrets') {if ($line -match '^([A-Z0-9_]+)=(.*)$') {$secrets[$matches[1]]=$matches[2]}}
$dbNames=@{world='rogue_paths_test_world_v3';characters='rogue_paths_test_characters_v3'}
function Query([string]$db,[string]$sql,[switch]$RestoreProbeAdmin) {
    if ($db -notin $dbNames.Values -and $db -notmatch '^rogue_paths_backup_probe_(world|characters)_v3_[0-9]{14}$') {throw 'Unscoped database'}
    $savedPassword=$env:MYSQL_PWD
    $databaseUser='acore'
    if ($RestoreProbeAdmin) {
        if ($sql -notmatch '^((CREATE|DROP) DATABASE rogue_paths_backup_probe_(world|characters)_v3_[0-9]{14}|source F:/JestokyCraft Backups/rogue-paths/pre-change-schema5-install-|SELECT COUNT\(\*\) FROM )') {throw 'Admin command outside restore-probe scope'}
        $databaseUser='root'
        $env:MYSQL_PWD=$secrets['MYSQL_ROOT_PASSWORD']
    }
    try {
        $result=@(& "$mysqlBin\mysql.exe" --host=127.0.0.1 "--user=$databaseUser" --default-character-set=utf8mb4 --batch --raw --skip-column-names "--database=$db" "--execute=$sql")
        if ($LASTEXITCODE -ne 0) {throw 'Isolated SQL command failed'}
    } finally {$env:MYSQL_PWD=$savedPassword}
    return ,$result
}
$oldPassword=$env:MYSQL_PWD
$dumps=@()
$mutated=$false
$priorSchema5=$false
$record=@{Status='verified-file-backup-sql-pending';Kind='pre-change';Files=$records;Databases=$dumps;Package=$PackageDirectory;CacheCleared=$false;Accepted=$false}
$record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath "$backup\manifest.json" -Encoding utf8
try {
    $env:MYSQL_PWD=$secrets['ACORE_DB_PASSWORD']
    # All owning processes were confirmed stopped: online is only a stale runtime flag.
    [void](Query $dbNames.characters 'UPDATE characters SET online=0 WHERE online<>0')
    $suppressedTableExists=(Query $dbNames.characters "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='character_cultivation_rogue_suppressed_action'")[0] -eq '1'
    $priorSchema5=$suppressedTableExists -and (Query $dbNames.characters 'SELECT COUNT(*) FROM character_cultivation_rogue WHERE schema_version<>5')[0] -eq '0'
    $characterTables=@('character_cultivation_rogue','character_spell','character_aura')
    if ($suppressedTableExists) {$characterTables+='character_cultivation_rogue_suppressed_action'}
    $tables=@{world=@('spell_ranks','spell_script_names','spell_linked_spell','spell_proc','spell_group','spell_group_stack_rules','spell_custom_attr');characters=$characterTables}
    foreach ($role in @('world','characters')) {
        $dump="$backup\$role.sql"
        & "$mysqlBin\mysqldump.exe" --host=127.0.0.1 --user=acore --default-character-set=utf8mb4 --single-transaction --no-tablespaces --set-gtid-purged=OFF "--result-file=$dump" $dbNames[$role] @($tables[$role])
        if ($LASTEXITCODE -ne 0 -or (Get-Item -LiteralPath $dump).Length -lt 100) {throw 'Database backup failed'}
        $digest=(Get-FileHash -LiteralPath $dump).Hash
        $probe='rogue_paths_backup_probe_'+$role+'_v3_'+(Get-Date -Format 'yyyyMMddHHmmss')
        [void](Query $dbNames[$role] "CREATE DATABASE $probe CHARACTER SET utf8mb4" -RestoreProbeAdmin)
        [void](Query $probe ('source '+$dump.Replace('\','/')) -RestoreProbeAdmin)
        foreach ($table in $tables[$role]) {
            if ((Query $probe "SELECT COUNT(*) FROM $table" -RestoreProbeAdmin)[0] -ne (Query $dbNames[$role] "SELECT COUNT(*) FROM $table")[0]) {throw 'SQL restore row-count mismatch'}
        }
        if ((Get-FileHash -LiteralPath $dump).Hash -ne $digest) {throw 'SQL dump changed during restore'}
        [void](Query $dbNames[$role] "DROP DATABASE $probe" -RestoreProbeAdmin)
        $dumps+=@{Role=$role;Database=$dbNames[$role];File=$dump;SHA256=$digest;Restore='passed-table-row-counts'}
    }
    $record=@{Status='verified-backup';Kind='pre-change';Files=$records;Databases=$dumps;Package=$PackageDirectory;CacheCleared=$false;Accepted=$false}
    $record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath "$backup\manifest.json" -Encoding utf8
    foreach ($role in @('world','characters')) {[void](Query $dbNames[$role] ('source '+"$PackageDirectory\sql\$role.preflight.sql".Replace('\','/')))}
    $mutated=$true
    foreach ($role in @('world','characters')) {
        1..2 | ForEach-Object {[void](Query $dbNames[$role] ('source '+"$PackageDirectory\sql\$role.up.sql".Replace('\','/')))}
        [void](Query $dbNames[$role] ('source '+"$PackageDirectory\sql\$role.postflight.sql".Replace('\','/')))
    }
    foreach ($file in $transfers) {
        New-Item -ItemType Directory -Path (Split-Path $file.Target) -Force | Out-Null
        Copy-Item -LiteralPath $file.Source -Destination $file.Target -Force
        if ((Get-FileHash -LiteralPath $file.Target).Hash -ne $file.Hash) {throw 'Deployment readback mismatch'}
    }
    # Preserve every other AddOn setting and all SavedVariables/character bindings.
    foreach ($state in $addonStates) {
        $text=[IO.File]::ReadAllText($state)
        if ($text -match '(?m)^RoguePathsUI:\s*\d+\s*$') {$text=[regex]::Replace($text,'(?m)^RoguePathsUI:\s*\d+\s*$','RoguePathsUI: enabled')}
        if ($text -match '(?m)^RoguePathsUI:\s*(enabled|disabled)\s*$') {$text=[regex]::Replace($text,'(?m)^RoguePathsUI:\s*(enabled|disabled)\s*$','RoguePathsUI: enabled')}
        else {$text=$text.TrimEnd("`r","`n")+"`r`nRoguePathsUI: enabled`r`n"}
        [IO.File]::WriteAllText($state,$text,[Text.UTF8Encoding]::new($false))
    }
    if ($ClearClientCache) {
        $cache=[IO.Path]::GetFullPath((Join-Path $ClientRoot 'Cache'))
        if ($cache -ne 'C:\Solo WotLK\test-client\20260831-rogue-paths-v3\Cache') {throw 'Cache removal target mismatch'}
        if (Test-Path -LiteralPath $cache) {
            $cacheBackup=Join-Path $backup 'client-cache'
            Copy-Item -LiteralPath $cache -Destination $cacheBackup -Recurse
            $cacheRecords=@()
            foreach ($file in Get-ChildItem -LiteralPath $cache -File -Recurse) {
                $relative=$file.FullName.Substring($cache.Length).TrimStart('\')
                $digest=(Get-FileHash -LiteralPath $file.FullName).Hash
                if ((Get-FileHash -LiteralPath (Join-Path $cacheBackup $relative)).Hash -ne $digest) {throw 'Cache backup mismatch'}
                $cacheRecords+=@{Relative=$relative;SHA256=$digest}
            }
            $record.CacheFiles=$cacheRecords
            $record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath "$backup\manifest.json" -Encoding utf8
            Remove-Item -LiteralPath $cache -Recurse -Force
            $record.CacheCleared=$true
        }
    }
    $record.Status='installed-unaccepted'
    $record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath "$backup\manifest.json" -Encoding utf8
    Write-Output "Installed isolated schema 5; verified backup: $backup; GUI/runtime acceptance pending"
} catch {
    $record.Status='failed'
    $record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath "$backup\manifest.json" -Encoding utf8
    if ($mutated) {
        if (!$priorSchema5) {
            foreach ($role in @('characters','world')) {
                [void](Query $dbNames[$role] ('source '+"$PackageDirectory\sql\$role.rollback.sql".Replace('\','/')))
            }
        }
        foreach ($entry in $records) {
            if ($entry.Existed) {Copy-Item -LiteralPath $entry.Backup -Destination $entry.Target -Force}
            elseif (Test-Path -LiteralPath $entry.Target -PathType Leaf) {Remove-Item -LiteralPath $entry.Target -Force}
        }
        foreach ($dump in $dumps) {[void](Query $dump.Database ('source '+$dump.File.Replace('\','/')))}
        Write-Warning 'Candidate failed: files and scoped SQL tables restored from F:; server remains stopped.'
    }
    throw
} finally {$env:MYSQL_PWD=$oldPassword}
