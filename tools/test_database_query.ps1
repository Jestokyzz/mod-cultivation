[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('auth','world','characters','playerbots')][string]$Database,
    [string]$Query,
    [string]$SqlFile
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
if (([bool]$Query) -eq ([bool]$SqlFile)) { throw 'Specify exactly one Query or SqlFile' }
$secrets=@{}
foreach($line in Get-Content -LiteralPath 'C:\Solo WotLK\WoWBotServer\.local-secrets') {
    if($line -match '^([A-Z0-9_]+)=(.*)$'){$secrets[$matches[1]]=$matches[2]}
}
$oldPassword=$env:MYSQL_PWD
try {
    $env:MYSQL_PWD=$secrets['ACORE_DB_PASSWORD']
    if ($SqlFile) { $Query='source '+[IO.Path]::GetFullPath($SqlFile).Replace('\','/') }
    $output=@(& 'C:\Solo WotLK\WoWBotServer\deps\mysql-8.4.10-winx64\bin\mysql.exe' '--host=127.0.0.1' '--port=3306' '--user=acore' '--default-character-set=utf8mb4' '--batch' '--raw' "--database=rogue_paths_test_${Database}_v1" "--execute=$Query" 2>&1)
    $output | Write-Output
    if($LASTEXITCODE -ne 0 -or ($output -join "`n") -match '(?m)^ERROR'){throw 'Test database query failed'}
}
finally{$env:MYSQL_PWD=$oldPassword}
