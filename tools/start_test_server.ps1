[CmdletBinding()]
param([string]$ServerRoot='C:\Solo WotLK\test-server\20260831-rogue-paths-v1')
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$ServerRoot=[IO.Path]::GetFullPath($ServerRoot)
if(-not $ServerRoot.StartsWith('C:\Solo WotLK\test-server\',[StringComparison]::OrdinalIgnoreCase)){throw 'Not a test-server path'}
$world=Join-Path $ServerRoot 'configs\worldserver.conf'
$auth=Join-Path $ServerRoot 'configs\authserver.conf'
$bots=Join-Path $ServerRoot 'configs\modules\playerbots.conf'
foreach($file in @($world,$auth,$bots)){
    foreach($line in Get-Content -LiteralPath $file){
        if($line -match '^(LoginDatabaseInfo|WorldDatabaseInfo|CharacterDatabaseInfo|PlayerbotsDatabaseInfo)\s*=\s*"[^"]*;([^;"]+)"'){
            if($matches[2] -notmatch '^rogue_paths_test_(auth|world|characters|playerbots)_v1$'){throw "Non-isolated database in $file"}
        }
    }
}
$worldText=Get-Content -LiteralPath $world -Raw
if($worldText -notmatch [regex]::Escape('DataDir = "'+$ServerRoot.Replace('\','/')+'/data"')){throw 'DataDir preflight failed'}
foreach($port in @(3730,8097)){
    if(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue){throw "Test port already occupied: $port"}
}
$authProcess=Start-Process -FilePath (Join-Path $ServerRoot 'authserver.exe') -ArgumentList @('-c','configs/authserver.conf') -WorkingDirectory $ServerRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $ServerRoot 'logs\auth-stdout.log') -RedirectStandardError (Join-Path $ServerRoot 'logs\auth-stderr.log')
$worldProcess=Start-Process -FilePath (Join-Path $ServerRoot 'worldserver.exe') -ArgumentList @('-c','configs/worldserver.conf') -WorkingDirectory $ServerRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $ServerRoot 'logs\world-stdout.log') -RedirectStandardError (Join-Path $ServerRoot 'logs\world-stderr.log')
@{Auth=$authProcess.Id;World=$worldProcess.Id;Root=$ServerRoot;StartedAt=(Get-Date).ToString('o')} |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $ServerRoot 'runtime-pids.json') -Encoding UTF8
Write-Host "Launched isolated server: auth PID $($authProcess.Id), world PID $($worldProcess.Id)"
