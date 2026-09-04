[CmdletBinding()]
param(
    [string]$ClientRoot = 'C:\Solo WotLK\test-client\20260831-rogue-paths-v1',
    [string]$ServerRoot = 'C:\Solo WotLK\test-server\20260831-rogue-paths-v1'
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
function Assert-Child([string]$path,[string]$root) {
    $resolved=[IO.Path]::GetFullPath($path)
    if (-not $resolved.StartsWith($root.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe clone path: $resolved" }
    if (Test-Path -LiteralPath $resolved) { throw "Clone already exists: $resolved" }
}
Assert-Child $ClientRoot 'C:\Solo WotLK\test-client'
Assert-Child $ServerRoot 'C:\Solo WotLK\test-server'
if (-not (Test-Path -LiteralPath 'F:\JestokyCraft Backups') -or (Get-PSDrive F).Free -lt 1GB) { throw 'Backup drive unavailable' }
$ClientRoot=[IO.Path]::GetFullPath($ClientRoot)
$ServerRoot=[IO.Path]::GetFullPath($ServerRoot)
$sourceClient='C:\Games\JestokyCraft'
$sourceServer='C:\Solo WotLK\test-server\20260828-aoe-loot-v1'
$build='C:\Solo WotLK\WoWBotServer\build-solitary-v4-ninja\bin'
$moduleRoot=Split-Path $PSScriptRoot
New-Item -ItemType Directory -Path $ClientRoot,$ServerRoot | Out-Null
# Real copies keep a later UI test from mutating production through a hardlink.
& robocopy.exe $sourceClient $ClientRoot /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL /NJH /NJS /NP /XD WTF Cache Errors Logs Screenshots
if ($LASTEXITCODE -gt 7) { throw 'Client copy failed' }
New-Item -ItemType Directory -Force -Path (Join-Path $ClientRoot 'WTF'),(Join-Path $ClientRoot 'Logs'),(Join-Path $ClientRoot 'Errors') | Out-Null
@('SET gxWindow "1"','SET gxMaximize "1"','SET gxResolution "1920x1080"','SET locale "ruRU"','SET realmList "127.0.0.1:3730"','SET checkAddonVersion "0"','SET scriptErrors "1"') |
    Set-Content -LiteralPath (Join-Path $ClientRoot 'WTF\Config.wtf') -Encoding ASCII
Get-ChildItem -LiteralPath $ClientRoot -Recurse -File -Filter realmlist.wtf | ForEach-Object {
    Set-Content -LiteralPath $_.FullName -Value 'set realmlist 127.0.0.1:3730' -Encoding ASCII
}
foreach ($file in Get-ChildItem -LiteralPath $build -File) {
    if ($file.Extension -in @('.exe','.dll')) { Copy-Item -LiteralPath $file.FullName -Destination $ServerRoot }
}
if (-not (Test-Path -LiteralPath (Join-Path $ServerRoot 'authserver.exe'))) {
    Copy-Item -LiteralPath (Join-Path $sourceServer 'authserver.exe') -Destination $ServerRoot
}
foreach ($file in Get-ChildItem -LiteralPath $sourceServer -File -Filter '*.dll') {
    if (-not (Test-Path -LiteralPath (Join-Path $ServerRoot $file.Name))) { Copy-Item -LiteralPath $file.FullName -Destination $ServerRoot }
}
Copy-Item -LiteralPath (Join-Path $sourceServer 'configs') -Destination $ServerRoot -Recurse
New-Item -ItemType Directory -Path (Join-Path $ServerRoot 'logs'),(Join-Path $ServerRoot 'data') | Out-Null
# Only immutable maps/vmaps/mmaps are hardlinked. DBCs and configs are real copies.
foreach ($file in Get-ChildItem -LiteralPath (Join-Path $sourceServer 'data') -Recurse -File) {
    $relative=[IO.Path]::GetRelativePath((Join-Path $sourceServer 'data'),$file.FullName)
    $target=Join-Path $ServerRoot ('data\'+$relative)
    New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null
    if ($file.Extension -eq '.dbc') { Copy-Item -LiteralPath $file.FullName -Destination $target }
    else { New-Item -ItemType HardLink -Path $target -Target $file.FullName | Out-Null }
}
foreach ($file in Get-ChildItem -LiteralPath (Join-Path $ServerRoot 'configs') -Recurse -File -Filter '*.conf') {
    $config=Get-Content -LiteralPath $file.FullName -Raw
    $config=$config.Replace('aoe_test_auth_v1','rogue_paths_test_auth_v1').Replace('aoe_test_world_v1','rogue_paths_test_world_v1').Replace('aoe_test_characters_v1','rogue_paths_test_characters_v1').Replace('aoe_test_playerbots_v1','rogue_paths_test_playerbots_v1')
    $config=[regex]::Replace($config,'(?m)^DataDir\s*=.*$',('DataDir = "'+$ServerRoot.Replace('\','/')+'/data"'))
    $config=[regex]::Replace($config,'(?m)^LogsDir\s*=.*$',('LogsDir = "'+$ServerRoot.Replace('\','/')+'/logs"'))
    $config=[regex]::Replace($config,'(?m)^WorldServerPort\s*=.*$','WorldServerPort = 8097')
    $config=[regex]::Replace($config,'(?m)^RealmServerPort\s*=.*$','RealmServerPort = 3730')
    $config=[regex]::Replace($config,'(?m)^SOAP.Port\s*=.*$','SOAP.Port = 7887')
    $config=[regex]::Replace($config,'(?m)^Ra.Port\s*=.*$','Ra.Port = 3457')
    $config=[regex]::Replace($config,'(?m)^Updates.EnableDatabases\s*=.*$','Updates.EnableDatabases = 0')
    $config=[regex]::Replace($config,'(?im)^AiPlayerbot.RandomBotAutologin\s*=.*$','AiPlayerbot.RandomBotAutologin = 1')
    Set-Content -LiteralPath $file.FullName -Value $config -Encoding UTF8
}
Copy-Item -LiteralPath (Join-Path $moduleRoot 'conf\mod_cultivation.conf.dist') -Destination (Join-Path $ServerRoot 'configs\modules\mod_cultivation.conf')
@{Client=$ClientRoot;Server=$ServerRoot;SourceClient=$sourceClient;SourceServer=$sourceServer;Resolution='1920x1080';Windowed=$true;Status='prepared-not-installed'} |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $moduleRoot 'generated\test-clones.json') -Encoding UTF8
Write-Host 'PASS: clean isolated clones prepared; candidate DBC/MPQ installation is a separate step.'
