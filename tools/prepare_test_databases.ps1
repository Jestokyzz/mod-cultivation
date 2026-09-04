[CmdletBinding()]
param([string]$BackupRoot = 'F:\JestokyCraft Backups')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$moduleRoot = Split-Path $PSScriptRoot
$mysqlRoot = 'C:\Solo WotLK\WoWBotServer\deps\mysql-8.4.10-winx64\bin'
$mysql = Join-Path $mysqlRoot 'mysql.exe'
$dumpTool = Join-Path $mysqlRoot 'mysqldump.exe'
if ([IO.Path]::GetFullPath($BackupRoot).TrimEnd('\') -ne 'F:\JestokyCraft Backups') { throw 'Invalid backup root' }
if (-not (Test-Path -LiteralPath $BackupRoot) -or (Get-PSDrive F).Free -lt 10GB) { throw 'Backup drive unavailable or full' }
$secretValues = @{}
foreach ($line in Get-Content -LiteralPath 'C:\Solo WotLK\WoWBotServer\.local-secrets') {
    if ($line -match '^([A-Z0-9_]+)=(.*)$') { $secretValues[$matches[1]]=$matches[2] }
}
$savedPassword = $env:MYSQL_PWD
function Query([string]$sql, [string]$db = '', [switch]$Admin) {
    $env:MYSQL_PWD = if ($Admin) { $secretValues['MYSQL_ROOT_PASSWORD'] } else { $secretValues['ACORE_DB_PASSWORD'] }
    $user = if ($Admin) { 'root' } else { 'acore' }
    $argsList = @('--host=127.0.0.1','--port=3306',"--user=$user",'--default-character-set=utf8mb4','--batch','--raw','--skip-column-names')
    if ($db) { $argsList += "--database=$db" }
    $result = @(& $mysql @argsList "--execute=$sql" 2>&1)
    if ($LASTEXITCODE -ne 0 -or ($result -join "`n") -match '(?m)^ERROR') { throw "Database operation failed ($db): $($result -join ' ')" }
    return $result
}
function SqlFile([string]$db, [string]$relative) {
    $file = [IO.Path]::GetFullPath((Join-Path $moduleRoot $relative)).Replace('\','/')
    [void](Query "source $file" $db)
}
$mapping = [ordered]@{
    aoe_test_auth_v1='rogue_paths_test_auth_v1'
    aoe_test_world_v1='rogue_paths_test_world_v1'
    aoe_test_characters_v1='rogue_paths_test_characters_v1'
    aoe_test_playerbots_v1='rogue_paths_test_playerbots_v1'
}
try {
    foreach ($db in $mapping.Values) {
        if (@(Query "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='$db'" -Admin).Count) { throw "Test DB already exists: $db" }
    }
    $stage = Join-Path $BackupRoot ('rogue-paths\baseline-test-databases-' + (Get-Date -Format 'yyyyMMddTHHmmss'))
    New-Item -ItemType Directory -Path $stage | Out-Null
    @{Status='in-progress';Kind='baseline';CreatedAt=(Get-Date).ToString('o')} | ConvertTo-Json |
        Set-Content -LiteralPath (Join-Path $stage 'manifest.json') -Encoding UTF8
    $records = @()
    foreach ($pair in $mapping.GetEnumerator()) {
        $dump = Join-Path $stage ($pair.Key+'.sql')
        $env:MYSQL_PWD=$secretValues['ACORE_DB_PASSWORD']
        & $dumpTool '--host=127.0.0.1' '--port=3306' '--user=acore' '--single-transaction' '--hex-blob' '--set-gtid-purged=OFF' '--no-tablespaces' "--result-file=$dump" $pair.Key
        if ($LASTEXITCODE -ne 0 -or ((Get-Content -LiteralPath $dump -Tail 8) -join "`n") -notmatch 'Dump completed on') { throw "Incomplete dump: $($pair.Key)" }
        $records += @{Source=$pair.Key;Target=$pair.Value;File=$dump;SHA256=(Get-FileHash -LiteralPath $dump).Hash;Kind='baseline'}
        @{Status='in-progress';Dumps=$records} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $stage 'manifest.json') -Encoding UTF8
        $db=$pair.Value
        [void](Query "CREATE DATABASE $db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL ON $db.* TO 'acore'@'127.0.0.1'; GRANT ALL ON $db.* TO 'acore'@'localhost';" -Admin)
        [void](Query ('source '+$dump.Replace('\','/')) $db)
        Write-Host "Cloned and verified dump: $($pair.Key) -> $db"
    }
    # A name/ID collision is a stop condition, never a reason to overwrite another module.
    if ([int](@(Query "SELECT COUNT(*) FROM rbac_permissions WHERE id=1001" 'rogue_paths_test_auth_v1')[0]) -ne 0) { throw 'RBAC 1001 collision' }
    if ([int](@(Query "SELECT COUNT(*) FROM spell_ranks WHERE spell_id BETWEEN 86000 AND 86999" 'rogue_paths_test_world_v1')[0]) -ne 0) { throw 'Spell range collision' }
    SqlFile 'rogue_paths_test_auth_v1' 'data\sql\auth\base\cultivation_rbac.sql'
    SqlFile 'rogue_paths_test_characters_v1' 'data\sql\characters\base\character_cultivation_rogue.sql'
    SqlFile 'rogue_paths_test_world_v1' 'data\sql\world\base\cultivation_rogue_spells.sql'
    SqlFile 'rogue_paths_test_world_v1' 'data\sql\world\base\cultivation_command.sql'
    [void](Query "UPDATE realmlist SET name='Cultivation / Rogue Test',address='127.0.0.1',localAddress='127.0.0.1',port=8097 WHERE id=1" 'rogue_paths_test_auth_v1')
    $ranks=[int](@(Query "SELECT COUNT(*) FROM spell_ranks WHERE spell_id BETWEEN 86000 AND 86999" 'rogue_paths_test_world_v1')[0])
    $links=[int](@(Query "SELECT COUNT(*) FROM spell_linked_spell WHERE (spell_trigger=86048 AND spell_effect=86570) OR (spell_trigger=86248 AND spell_effect=86571)" 'rogue_paths_test_world_v1')[0])
    if ($ranks -ne 220 -or $links -ne 2) { throw "Postflight mismatch: ranks=$ranks fan_links=$links" }
    @{Status='passed';Dumps=$records;RankRows=$ranks;FanLinks=$links;Migration='1.0.0';ProductionModified=$false} |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $stage 'manifest.json') -Encoding UTF8
    Write-Host "PASS: isolated databases and SQL postflight. Manifest: $stage\manifest.json"
}
finally { $env:MYSQL_PWD=$savedPassword }
