[CmdletBinding()]
param([string]$ClientRoot='C:\Games\JestokyCraft',[string]$ServerRoot='C:\Solo WotLK\WoWBotServer\build\bin\RelWithDebInfo',[string]$ServerDataRoot='C:\Solo WotLK\WoWBotServer\server\data')
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$moduleRoot=Split-Path $PSScriptRoot
$audit=Get-Content -LiteralPath "$moduleRoot\audit-fixes-manifest.json" -Raw | ConvertFrom-Json
if($audit.status -ne 'user-accepted-production-installed-startup-passed'){throw 'Release not accepted'}
$owner=Get-Content -LiteralPath "$moduleRoot\client_patch\build\v2.0.0-audit-candidate5\manifest.json" -Raw | ConvertFrom-Json
function Hash([string]$path){(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
$sources=[ordered]@{}
foreach($letter in @('A','X','Z')){$sources["client/Data/ruRU/patch-ruRU-$letter.MPQ"]="$ClientRoot\Data\ruRU\patch-ruRU-$letter.MPQ"}
if((Hash $sources['client/Data/ruRU/patch-ruRU-A.MPQ']) -ne '6b6055e66d0944b61b7cf33ca2a0da27a6575732c2d5ffc263c5fd8e86dbc69f'){throw 'Icon owner mismatch'}
foreach($letter in @('X','Z')){if((Hash $sources["client/Data/ruRU/patch-ruRU-$letter.MPQ"]) -ne $owner.artifacts.PSObject.Properties["patch-ruRU-$letter.MPQ"].Value.sha256){throw 'MPQ differs from accepted candidate'}}
$sources['server/worldserver.exe']="$ServerRoot\worldserver.exe"
if((Hash $sources['server/worldserver.exe']) -ne $audit.runtime_artifacts.build_worldserver.sha256){throw 'Binary differs from accepted build'}
$sources['server/configs/modules/mod_cultivation.conf.dist']="$moduleRoot\conf\mod_cultivation.conf.dist"
foreach($name in @('Spell.dbc','SkillLineAbility.dbc','SpellDescriptionVariables.dbc','SpellIcon.dbc','SpellRadius.dbc','SpellRange.dbc')){
 $source="$ServerDataRoot\dbc\$name"
 if((Hash $source) -ne (Hash "$moduleRoot\generated\server\dbc\$name")){throw "DBC differs from generated: $name"}
 $sources["server/data/dbc/$name"]=$source
}
$stamp=Get-Date -Format 'yyyyMMddTHHmmss'
$output="$moduleRoot\dist\release-v2.0.0-$stamp"
if(Test-Path -LiteralPath $output){throw 'Immutable output already exists'}
$staging="$output\package"
New-Item -ItemType Directory -Path $staging | Out-Null
foreach($relative in $sources.Keys){
 $destination=Join-Path $staging $relative
 New-Item -ItemType Directory -Path (Split-Path $destination) -Force | Out-Null
 Copy-Item -LiteralPath $sources[$relative] -Destination $destination
 if((Hash $destination) -ne (Hash $sources[$relative])){throw 'Artifact readback mismatch'}
}
foreach($pair in @(@{Source='installer';Target='installer'},@{Source='data/sql/auth/base';Target='sql/fresh/auth'},@{Source='data/sql/world/base';Target='sql/fresh/world'},@{Source='data/sql/characters/base';Target='sql/fresh/characters'},@{Source='data/sql/migrations/2.0.0';Target='sql/upgrade-from-rogue-paths'})){
 $target=Join-Path $staging $pair.Target
 New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
 Copy-Item -LiteralPath (Join-Path $moduleRoot $pair.Source) -Destination $target -Recurse
}
foreach($pair in @(@{Source='docs/install-v2.0.0.md';Target='INSTALL_RU.md'},@{Source='docs/compatibility_matrix.md';Target='COMPATIBILITY.md'},@{Source='CHANGELOG_RU.md';Target='CHANGELOG_RU.md'},@{Source='LICENSE';Target='LICENSE'})){
 Copy-Item -LiteralPath (Join-Path $moduleRoot $pair.Source) -Destination (Join-Path $staging $pair.Target)
}
$tracked=@(git -c "safe.directory=$($moduleRoot.Replace('\','/'))" -C $moduleRoot ls-files --cached --others --exclude-standard)
if($LASTEXITCODE -ne 0){throw 'Source enumeration failed'}
foreach($relative in $tracked){
 if($relative -match '^validation/' -and $relative -notmatch '^validation/v2\.0\.0/'){continue} # no historical candidate payload
 if($relative -match '(^|/)(dist|\.git|SavedVariables|WTF|quarantine|failed)(/|$)' -or $relative -match '\.(exe|dll|MPQ|zip|log|dmp)$'){throw "Forbidden source payload: $relative"}
 $target=Join-Path $staging "source/mod-cultivation/$relative"
 New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
 Copy-Item -LiteralPath (Join-Path $moduleRoot $relative) -Destination $target
}
$validation="$staging\validation"
New-Item -ItemType Directory -Path $validation | Out-Null
Copy-Item -LiteralPath "$moduleRoot\generated\audit-static-tests.json" -Destination "$validation\audit-static-tests.json"
foreach($name in @('shadowstep_native_test.json','sha_candidate41_native_test.json','celestial_resources_native_test.json','world_protocol_test.json','celestial_native_test.json')){
 $source="$moduleRoot\generated\v2.0.0\$name"
 $expected=$audit.native_reports.PSObject.Properties[$name].Value.sha256
 if((Hash $source) -ne $expected){throw "Native evidence changed: $name"}
 # Only checks/status, never the worldserver log or account data.
 $document=Get-Content -LiteralPath $source -Raw | ConvertFrom-Json
 @{scope=$document.scope;status=$document.status;checks=$document.checks;source_sha256=$expected} | ConvertTo-Json -Depth 24 | Set-Content -LiteralPath "$validation\$name" -Encoding UTF8
}
$inventory=[ordered]@{}
foreach($entry in $owner.inventory.PSObject.Properties){$inventory[$entry.Name.Substring('C:\Games\JestokyCraft\'.Length).Replace('\','/')]=$entry.Value}
$dlls=[ordered]@{}
foreach($file in Get-ChildItem -LiteralPath $ServerRoot -Filter '*.dll' -File){$dlls[$file.Name]=Hash $file.FullName}
$rows=@(foreach($file in Get-ChildItem -LiteralPath $staging -File -Recurse | Sort-Object FullName){@{path=$file.FullName.Substring($staging.Length+1).Replace('\','/');bytes=$file.Length;sha256=Hash $file.FullName}})
$manifest=[ordered]@{package='mod-cultivation';candidate='v2.0.0';version='2.0.0';status='accepted-production-tested';source_commit=(git -c "safe.directory=$($moduleRoot.Replace('\','/'))" -C $moduleRoot rev-parse HEAD);compatibility=@{client='JestokyCraft ruRU 12340';client_exe='Wow-NWQ.exe';client_exe_sha256=(Hash "$ClientRoot\Wow-NWQ.exe");runtime_dlls=$dlls;client_inventory=$inventory;core_revision='7c8ed00e7f654617a47bdf728b49707f60aa1aae';platform='Windows x64';scope='Integrated JestokyCraft binary; not arbitrary AzerothCore'};files=$rows}
$manifest | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath "$staging\package-manifest.json" -Encoding UTF8
$archive="$output\mod-cultivation-v2.0.0-windows-x64.zip"
Compress-Archive -Path "$staging\*" -DestinationPath $archive -CompressionLevel Optimal
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip=[IO.Compression.ZipFile]::OpenRead($archive)
try{
 foreach($row in $rows){
  $entry=$zip.GetEntry($row.path)
  if(!$entry){$entry=$zip.GetEntry($row.path.Replace('/','\'))}
  if(!$entry -or $entry.Length -ne $row.bytes){throw "ZIP missing/size mismatch: $($row.path)"}
  $stream=$entry.Open();$sha=[Security.Cryptography.SHA256]::Create()
  try{$actual=[BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','').ToLowerInvariant()}finally{$stream.Dispose();$sha.Dispose()}
  if($actual -ne $row.sha256){throw 'ZIP SHA-256 mismatch'}
 }
}finally{$zip.Dispose()}
((Hash $archive)+'  '+[IO.Path]::GetFileName($archive)) | Set-Content -LiteralPath "$output\SHA256SUMS.txt" -Encoding ascii
@{Archive=$archive;SHA256=(Hash $archive);Bytes=(Get-Item -LiteralPath $archive).Length;Staging=$staging;FileCount=$rows.Count;Checksums="$output\SHA256SUMS.txt";Status='all ZIP entries verified'} | ConvertTo-Json
