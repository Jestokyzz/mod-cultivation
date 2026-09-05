[CmdletBinding()]
param([Parameter(Mandatory)][string]$BackupDirectory)
$ErrorActionPreference='Stop'
$BackupDirectory=(Resolve-Path -LiteralPath $BackupDirectory).Path
$manifest=Get-Content -LiteralPath (Join-Path $BackupDirectory 'backup-manifest.json') -Raw | ConvertFrom-Json
if($manifest.package -ne 'mod-cultivation'){throw 'Not a Cultivation backup'}
$processes=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -match '^(Wow.*|worldserver|authserver)\.exe$'})
if($processes.Count){throw 'Close game/server processes before rollback'}
foreach($entry in $manifest.files){
 if(!$entry.existed){throw "New file needs an explicit removal decision before rollback: $($entry.target)"}
 $saved=Join-Path $BackupDirectory $entry.backup
 if(!( [IO.Path]::GetFullPath($saved).StartsWith($BackupDirectory+'\',[StringComparison]::OrdinalIgnoreCase))){throw 'Backup path escaped root'}
 if((Get-FileHash -LiteralPath $saved).Hash -ne $entry.before_sha256){throw 'Backup hash failed'}
 if((Get-FileHash -LiteralPath $entry.target).Hash -ne $entry.after_sha256){throw 'Target changed since installation'}
}
foreach($entry in $manifest.files){
 Copy-Item -LiteralPath (Join-Path $BackupDirectory $entry.backup) -Destination $entry.target -Force
 if((Get-FileHash -LiteralPath $entry.target).Hash -ne $entry.before_sha256){throw 'Rollback readback failed'}
}
Write-Output 'Files restored and verified. If SQL was applied, restore the checked database dumps separately before starting worldserver.'
