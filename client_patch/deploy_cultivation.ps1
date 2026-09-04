[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$ClientRoot='C:\Solo WotLK\test-client\20260831-rogue-paths-v3',
    [string]$ServerRoot='C:\Solo WotLK\test-server\20260831-rogue-paths-v3',
    [string]$PackageDirectory=(Join-Path $PSScriptRoot 'build\v1.3.0-candidate1'),
    [string]$WorldBinary='C:\Solo WotLK\WoWBotServer\build-solitary-v4-ninja\bin\worldserver.exe',
    [switch]$InitializeSchema,
    [switch]$ClearClientCache
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$candidateHeader=Get-Content -LiteralPath (Join-Path $PackageDirectory 'manifest.json') -Raw | ConvertFrom-Json
if ($candidateHeader.schema_version -eq 3) {
    & (Join-Path $PSScriptRoot 'deploy_visibility.ps1') -ClientRoot $ClientRoot -ServerRoot $ServerRoot -PackageDirectory $PackageDirectory -ClearClientCache:$ClearClientCache -WhatIf:$WhatIfPreference
    return
}
$ClientRoot=[IO.Path]::GetFullPath($ClientRoot)
$ServerRoot=[IO.Path]::GetFullPath($ServerRoot)
if ($ClientRoot -ne 'C:\Solo WotLK\test-client\20260831-rogue-paths-v3' -or
    $ServerRoot -ne 'C:\Solo WotLK\test-server\20260831-rogue-paths-v3') { throw 'Unaccepted candidate: only audited v3 clones allowed' }
$backupRoot='F:\JestokyCraft Backups'
if (!(Test-Path -LiteralPath $backupRoot) -or (Get-PSDrive F).Free -lt 5GB) { throw 'F: backup root unavailable/full' }
foreach ($process in Get-CimInstance Win32_Process) {
    if ($process.ExecutablePath -and ($process.ExecutablePath.StartsWith($ClientRoot+'\',[StringComparison]::OrdinalIgnoreCase) -or
        $process.ExecutablePath.StartsWith($ServerRoot+'\',[StringComparison]::OrdinalIgnoreCase))) { throw 'Close exact v3 client/server before deployment' }
}
$moduleRoot=Split-Path $PSScriptRoot
$manifest=Get-Content -LiteralPath (Join-Path $PackageDirectory 'manifest.json') -Raw | ConvertFrom-Json
if ($manifest.version -ne '1.2.0' -or $manifest.schema_version -ne 2 -or $manifest.static_validation -ne 'passed') { throw 'Wrong/unvalidated candidate' }
$migration=Join-Path $moduleRoot 'data\sql\migrations\1.2.0'
$sqlManifest=Get-Content -LiteralPath (Join-Path $migration 'manifest.json') -Raw | ConvertFrom-Json
foreach ($property in $sqlManifest.files.PSObject.Properties) {
    if ((Get-FileHash -LiteralPath (Join-Path $migration $property.Name)).Hash -ne $property.Value) { throw 'SQL hash mismatch' }
}
$transfers=@()
foreach ($property in $manifest.files.PSObject.Properties) {
    $transfers+=@{Source=(Join-Path $PackageDirectory $property.Name);Target=(Join-Path "$ClientRoot\Data\ruRU" $property.Name);Name=('client-'+$property.Name);Hash=$property.Value}
}
foreach ($property in $manifest.server_dbc.PSObject.Properties) {
    $transfers+=@{Source=(Join-Path "$moduleRoot\generated\server\dbc" $property.Name);Target=(Join-Path "$ServerRoot\data\dbc" $property.Name);Name=('server-'+$property.Name);Hash=$property.Value}
}
$transfers+=@{Source=$WorldBinary;Target="$ServerRoot\worldserver.exe";Name='worldserver.exe';Hash=(Get-FileHash -LiteralPath $WorldBinary).Hash}
foreach ($entry in $transfers) {
    if (!(Test-Path -LiteralPath $entry.Target -PathType Leaf) -or (Get-FileHash -LiteralPath $entry.Source).Hash -ne $entry.Hash) { throw 'Transfer source/target validation failed' }
}
$config=Get-Content -LiteralPath "$ClientRoot\WTF\Config.wtf" -Raw
foreach ($line in @('SET gxWindow "1"','SET gxMaximize "1"','SET gxResolution "1920x1080"')) {
    if (!$config.Contains($line)) { throw 'Clone graphics stop-condition' }
}
$secretValues=@{}
foreach ($line in Get-Content -LiteralPath 'C:\Solo WotLK\WoWBotServer\.local-secrets') {
    if ($line -match '^([A-Z0-9_]+)=(.*)$') { $secretValues[$matches[1]]=$matches[2] }
}
$mysql='C:\Solo WotLK\WoWBotServer\deps\mysql-8.4.10-winx64\bin\mysql.exe'
function Query([string]$kind,[string]$statement) {
    if ($kind -notin @('world','characters')) { throw 'Wrong database role' }
    $db='rogue_paths_test_'+$kind+'_v3'
    $result=@(& $mysql --host=127.0.0.1 --port=3306 --user=acore --default-character-set=utf8mb4 --batch --raw --skip-column-names "--database=$db" "--execute=$statement")
    if ($LASTEXITCODE -ne 0) { throw 'Isolated SQL failed' }
    return ,$result
}
$previousPassword=$env:MYSQL_PWD
$backup=$null
try {
    $env:MYSQL_PWD=$secretValues['ACORE_DB_PASSWORD']
    # Exact clone processes were verified absent above. Clear stale volatile
    # online flags left by stopping this disposable world (including bots).
    if ((Query 'characters' 'SELECT COUNT(*) FROM characters WHERE online<>0')[0] -ne '0') {
        if (!$PSCmdlet.ShouldProcess('rogue_paths_test_characters_v3','Clear stale online flags of stopped clone')) { return }
        [void](Query 'characters' 'UPDATE characters SET online=0 WHERE online<>0')
    }
    if ($InitializeSchema) {
        if ((Query 'world' 'SELECT spell_id FROM spell_group WHERE id=1900').Count) { throw 'Initial deployment requires unused group 1900' }
        $baseline=Get-Content -LiteralPath "$backupRoot\rogue-paths\baseline-celestial-databases-20260831-v3\manifest.json" -Raw | ConvertFrom-Json
        if ($baseline.Status -ne 'verified-restored') { throw 'Restored database backup required' }
        foreach ($file in $baseline.Files) {
            if ((Get-FileHash -LiteralPath $file.File).Hash -ne $file.SHA256) { throw 'Database baseline hash mismatch' }
        }
    } elseif ((Query 'world' 'SELECT COUNT(*) FROM spell_group WHERE id=1900 AND spell_id IN (86597,86598)')[0] -ne '2') { throw 'InitializeSchema required for baseline' }
    if (!$PSCmdlet.ShouldProcess("$ClientRoot and $ServerRoot",'Verified backup, versioned SQL and complete Celestial v3 installation')) { return }
    $backup=Join-Path $backupRoot ('rogue-paths\pre-change-celestial-install-'+(Get-Date -Format 'yyyyMMddTHHmmss'))
    New-Item -ItemType Directory -Path $backup,"$backup\restore-check" | Out-Null
    $records=@()
    foreach ($entry in $transfers) {
        $saved=Join-Path $backup $entry.Name
        $oldHash=(Get-FileHash -LiteralPath $entry.Target).Hash
        Copy-Item -LiteralPath $entry.Target -Destination $saved
        Copy-Item -LiteralPath $saved -Destination "$backup\restore-check\$($entry.Name)"
        if ((Get-FileHash -LiteralPath $saved).Hash -ne $oldHash -or
            (Get-FileHash -LiteralPath "$backup\restore-check\$($entry.Name)").Hash -ne $oldHash) { throw 'Backup/restore verification failed' }
        $records+=@{Target=$entry.Target;Backup=$saved;BeforeSHA256=$oldHash;AfterSHA256=$entry.Hash}
    }
    $record=@{Status='verified-backup';Kind='pre-change';Files=$records;SchemaInitialized=[bool]$InitializeSchema;Accepted=$false}
    $record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath "$backup\manifest.json" -Encoding utf8
    if ($InitializeSchema) {
        foreach ($kind in @('world','characters')) {
            [void](Query $kind ('source '+(Join-Path $migration "$kind.preflight.sql").Replace('\','/')))
            1..2 | ForEach-Object { [void](Query $kind ('source '+(Join-Path $migration "$kind.up.sql").Replace('\','/'))) }
            [void](Query $kind ('source '+(Join-Path $migration "$kind.postflight.sql").Replace('\','/')))
        }
    }
    if ((Query 'world' 'SELECT COUNT(*) FROM spell_group WHERE id=1900 AND spell_id IN (86597,86598)')[0] -ne '2' -or
        (Query 'world' 'SELECT stack_rule FROM spell_group_stack_rules WHERE group_id=1900')[0] -ne '1' -or
        (Query 'characters' 'SELECT COUNT(*) FROM character_cultivation_rogue WHERE schema_version<2')[0] -ne '0' -or
        (Query 'characters' 'SELECT COUNT(*) FROM character_aura WHERE spell IN (86513,86515,86516,86532,86569,86575)')[0] -ne '0') { throw 'Migration postflight failed' }
    foreach ($entry in $transfers) {
        Copy-Item -LiteralPath $entry.Source -Destination $entry.Target -Force
        if ((Get-FileHash -LiteralPath $entry.Target).Hash -ne $entry.Hash) { throw 'Installation readback mismatch' }
    }
    $record.Status='installed-unaccepted'
    $record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath "$backup\manifest.json" -Encoding utf8
    Write-Output "PASS: five server DBC, A/Z MPQ, worldserver, SQL schema 2. Rollback: $backup"
} catch {
    if ($backup -and (Test-Path -LiteralPath "$backup\manifest.json")) {
        $record=Get-Content -LiteralPath "$backup\manifest.json" -Raw | ConvertFrom-Json
        foreach ($entry in $record.Files) {
            Copy-Item -LiteralPath $entry.Backup -Destination $entry.Target -Force
            if ((Get-FileHash -LiteralPath $entry.Target).Hash -ne $entry.BeforeSHA256) { throw 'File rollback failed; stop all v3 use' }
        }
        if ($InitializeSchema) {
            foreach ($kind in @('world','characters')) { [void](Query $kind ('source '+(Join-Path $migration "$kind.rollback.sql").Replace('\','/'))) }
        }
        $record.Status='rolled-back-after-install-failure'
        $record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath "$backup\manifest.json" -Encoding utf8
    }
    throw
} finally { $env:MYSQL_PWD=$previousPassword }
