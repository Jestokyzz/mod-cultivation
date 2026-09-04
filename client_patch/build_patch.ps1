[CmdletBinding()]
param([string]$Python='C:\Users\posha\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
$ErrorActionPreference='Stop'
$moduleRoot=Split-Path $PSScriptRoot
if (!(Test-Path -LiteralPath 'F:\JestokyCraft Backups') -or (Get-PSDrive F).Free -lt 1GB) { throw 'Verified F: archive must be available' }
$report=Get-Content -LiteralPath (Join-Path $moduleRoot 'generated\generation_report.json') -Raw | ConvertFrom-Json
if ($report.status -ne 'passed') { throw 'Data generation not validated' }
& $Python (Join-Path $moduleRoot 'tools\test_generated_data.py')
if ($LASTEXITCODE -ne 0) { throw 'Static validation failed' }
& $Python (Join-Path $moduleRoot 'tools\package_seven_candidate.py')
if ($LASTEXITCODE -ne 0) { throw 'Candidate MPQ verification failed' }
Write-Output 'Candidate only; clone acceptance and explicit user approval required before main installation.'
