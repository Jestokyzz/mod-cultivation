[CmdletBinding()]
param([string]$Reason='Isolated candidate regression correction')
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$moduleRoot=Split-Path $PSScriptRoot
$server='C:\Solo WotLK\test-server\20260831-rogue-paths-v1'
$client='C:\Solo WotLK\test-client\20260831-rogue-paths-v1'
$archive='F:\JestokyCraft Backups\rogue-paths\failed-candidate-'+(Get-Date -Format 'yyyyMMddTHHmmss')
if(-not(Test-Path -LiteralPath 'F:\JestokyCraft Backups') -or (Get-PSDrive F).Free -lt 1GB){throw 'Backup drive unavailable'}
$running=@(Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($server+'\',[StringComparison]::OrdinalIgnoreCase) -and $_.Name -in @('worldserver.exe','authserver.exe') })
if(Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($client+'\',[StringComparison]::OrdinalIgnoreCase) }){throw 'Close the test client before updating'}
New-Item -ItemType Directory -Path $archive | Out-Null
$files=@('worldserver.exe','data\dbc\Spell.dbc','data\dbc\SkillLineAbility.dbc')
$records=@()
foreach($relative in $files){
    $source=Join-Path $server $relative
    $destination=Join-Path $archive ('server\'+$relative)
    New-Item -ItemType Directory -Force -Path (Split-Path $destination)|Out-Null
    Copy-Item -LiteralPath $source -Destination $destination
    $hash=(Get-FileHash -LiteralPath $source).Hash
    if((Get-FileHash -LiteralPath $destination).Hash-ne$hash){throw 'Backup SHA mismatch'}
    $records+=@{Source=$source;Backup=$destination;SHA256=$hash}
}
@{Kind='failed';Status='backed-up';Reason=$Reason;Files=$records} |
    ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $archive 'manifest.json') -Encoding UTF8
foreach($process in $running){Stop-Process -Id $process.ProcessId -Force}
Copy-Item -LiteralPath (Join-Path $server 'logs') -Destination $archive -Recurse
foreach($file in Get-ChildItem -LiteralPath (Join-Path $server 'logs') -File -Recurse){
    $relative=$file.FullName.Substring($server.Length+1)
    $copy=Join-Path $archive $relative
    $hash=(Get-FileHash -LiteralPath $file.FullName).Hash
    if((Get-FileHash -LiteralPath $copy).Hash-ne$hash){throw 'Log backup SHA mismatch'}
    $records+=@{Source=$file.FullName;Backup=$copy;SHA256=$hash}
}
$oldBuild=[IO.Path]::GetFullPath((Join-Path $moduleRoot 'client_patch\build'))
$expected=[IO.Path]::GetFullPath('C:\Solo WotLK\WoWBotServer\azerothcore-wotlk\modules\mod-cultivation\client_patch\build')
if($oldBuild -ne $expected -or -not $archive.StartsWith('F:\JestokyCraft Backups\rogue-paths\')){throw 'Move boundary failed'}
$archivedBuild=Join-Path $archive 'client-package'
Copy-Item -LiteralPath $oldBuild -Destination $archivedBuild -Recurse
foreach($file in Get-ChildItem -LiteralPath $oldBuild -File -Recurse){
    $relative=$file.FullName.Substring($oldBuild.Length+1)
    $copy=Join-Path $archivedBuild $relative
    $hash=(Get-FileHash -LiteralPath $file.FullName).Hash
    if((Get-FileHash -LiteralPath $copy).Hash-ne$hash){throw 'Archived client package SHA mismatch'}
    $records+=@{Source=$file.FullName;Backup=$copy;SHA256=$hash}
}
foreach($reportName in @('world_protocol_test.json','talent_protocol_test.json','restart_protocol_test.json')){
    $protocolReport=Join-Path $moduleRoot ('generated\'+$reportName)
    if(-not(Test-Path -LiteralPath $protocolReport)){continue}
    Copy-Item -LiteralPath $protocolReport -Destination $archive
    $copy=Join-Path $archive $reportName
    $hash=(Get-FileHash -LiteralPath $protocolReport).Hash
    if((Get-FileHash -LiteralPath $copy).Hash-ne$hash){throw 'Protocol evidence SHA mismatch'}
    $records+=@{Source=$protocolReport;Backup=$copy;SHA256=$hash}
}
@{Kind='failed';Status='verified';Reason=$Reason;Files=$records} |
    ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $archive 'manifest.json') -Encoding UTF8
# Exact source boundary was checked above. Cross-volume copy is verified before removal.
Remove-Item -LiteralPath $oldBuild -Recurse -Force
& (Join-Path $moduleRoot 'client_patch\build_patch.ps1')
& (Join-Path $moduleRoot 'client_patch\deploy_rogue_paths.ps1') -ClientRoot $client -ServerRoot $server -PreviousManifest (Join-Path $archive 'client-package\manifest.json')
Copy-Item -LiteralPath 'C:\Solo WotLK\WoWBotServer\build-solitary-v4-ninja\bin\worldserver.exe' -Destination (Join-Path $server 'worldserver.exe') -Force
if((Get-FileHash -LiteralPath (Join-Path $server 'worldserver.exe')).Hash -ne
    (Get-FileHash -LiteralPath 'C:\Solo WotLK\WoWBotServer\build-solitary-v4-ninja\bin\worldserver.exe').Hash){throw 'Installed worldserver SHA mismatch'}
& (Join-Path $PSScriptRoot 'test_database_query.ps1') -Database world -SqlFile (Join-Path $moduleRoot 'data\sql\world\base\cultivation_rogue_spells.sql')
& (Join-Path $PSScriptRoot 'start_test_server.ps1')
Write-Host "Replaced isolated candidate. Previous candidate and logs are recoverable at $archive"
