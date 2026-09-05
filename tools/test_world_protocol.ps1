param([switch]$TalentsOnly,[switch]$RestartOnly,[switch]$V2,[switch]$V3,[switch]$CelestialOnly,[switch]$ResourcesOnly,[switch]$ShaSinisterOnly,[switch]$Sha41Only,[switch]$Schema3,[switch]$Schema5,[switch]$Schema6,[switch]$ShadowstepOnly)
$ErrorActionPreference='Stop'
$secrets=@{}
foreach($line in Get-Content -LiteralPath 'C:\Solo WotLK\WoWBotServer\.local-secrets') {
    if($line -match '^([A-Z0-9_]+)=(.*)$'){$secrets[$matches[1]]=$matches[2]}
}
$previous=$env:MYSQL_PWD
$previousEncoding=$env:PYTHONIOENCODING
try {
    $env:MYSQL_PWD=$secrets['ACORE_DB_PASSWORD']
    $env:PYTHONIOENCODING='utf-8'
    $testArguments=@((Join-Path $PSScriptRoot 'test_world_protocol.py'))
    if($V2){$testArguments+='--v2'}
    if($V3){$testArguments+='--v3'}
    if($Schema3){$testArguments+='--schema3'}
    if($Schema5){$testArguments+='--schema5'}
    if($Schema6){$testArguments+='--schema6'}
    if($ShadowstepOnly){$testArguments+='--shadowstep-only'}
    if($CelestialOnly){$testArguments+='--celestial-only'}
    if($ResourcesOnly){$testArguments+='--resources-only'}
    if($ShaSinisterOnly){$testArguments+='--sha-sinister-only'}
    if($Sha41Only){$testArguments+='--sha41-only'}
    if($TalentsOnly){$testArguments+='--talents-only'}
    if($RestartOnly){$testArguments+='--restart-only'}
    & 'C:\Users\posha\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' @testArguments
    if($LASTEXITCODE -ne 0){throw 'World protocol integration test failed; see generated/world_protocol_test.json'}
} finally {
    $env:MYSQL_PWD=$previous
    $env:PYTHONIOENCODING=$previousEncoding
}
