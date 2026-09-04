[CmdletBinding()]
param(
    [string]$ClientRoot = 'C:\Solo WotLK\test-client\20260831-rogue-paths-v3',
    [string]$ServerRoot = 'C:\Solo WotLK\test-server\20260904-cultivation-v1'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$moduleRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$gitSafe = 'safe.directory=' + $moduleRoot.Replace('\','/')
$expected = [ordered]@{
    'client/Data/ruRU/patch-ruRU-A.MPQ' = '6b6055e66d0944b61b7cf33ca2a0da27a6575732c2d5ffc263c5fd8e86dbc69f'
    'client/Data/ruRU/patch-ruRU-Z.MPQ' = '496b493c082cedd1b0f3633dcd8577b6790285ef740601d8f402c2a3dddc148c'
    'client/Data/ruRU/patch-ruRU-X.MPQ' = 'e80ae73b2355bd957e417b06f05b829553e07c2189585c1517e154d7dc836479'
    'server/worldserver.exe' = '682e63427f6734c9b6ee7b059a5a0c778694c3faa41573ff3abfd3356a7bfdb6'
    'server/configs/modules/mod_cultivation.conf.dist' = '93d3c3b4f0b2f41d41f9205e7a789645d3ee368a513725bc7301e21d4f1ecf96'
    'server/data/dbc/Spell.dbc' = '1312bb13ea260e4049f2c2eeb17a8fd57c1ad692c8e43cd0816cb16662e8844a'
    'server/data/dbc/SkillLineAbility.dbc' = '9b28119050646f25e5803ae94ed0057a7a8cd0c32974ba51dbd061ecdffeaa1b'
    'server/data/dbc/SpellDescriptionVariables.dbc' = 'db797fc63a1cf567c8abc5cef6ef21e143b7fd1111173dd33a37498d27cfddfe'
    'server/data/dbc/SpellIcon.dbc' = 'c4b09e7163a0cb325c4dfb08b8c04af539218a463219928f6fc2718f500b7e29'
    'server/data/dbc/SpellRadius.dbc' = '8015708e990bdf990ed34b9ce52c15ebbb26abd1ab4f92c138bddf35449a1c8e'
    'server/data/dbc/SpellRange.dbc' = '335aafe78a1cd8f60eb24c1dbd81f12788346d82ef7299a541ef9815587a4288'
}

$sources = [ordered]@{
    'client/Data/ruRU/patch-ruRU-A.MPQ' = Join-Path $ClientRoot 'Data\ruRU\patch-ruRU-A.MPQ'
    'client/Data/ruRU/patch-ruRU-Z.MPQ' = Join-Path $ClientRoot 'Data\ruRU\patch-ruRU-Z.MPQ'
    'client/Data/ruRU/patch-ruRU-X.MPQ' = Join-Path $ClientRoot 'Data\ruRU\patch-ruRU-X.MPQ'
    'server/worldserver.exe' = Join-Path $ServerRoot 'worldserver.exe'
    'server/configs/modules/mod_cultivation.conf.dist' = Join-Path $moduleRoot 'conf\mod_cultivation.conf.dist'
}
foreach ($name in @('Spell.dbc','SkillLineAbility.dbc','SpellDescriptionVariables.dbc','SpellIcon.dbc','SpellRadius.dbc','SpellRange.dbc')) {
    $sources["server/data/dbc/$name"] = Join-Path $ServerRoot "data\dbc\$name"
}

foreach ($relative in $sources.Keys) {
    $source = $sources[$relative]
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Required source is missing: $source" }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash.ToLowerInvariant()
    if ($actual -ne $expected[$relative]) {
        throw "Verified source hash mismatch for $relative. Expected $($expected[$relative]), got $actual"
    }
}

$distRoot = Join-Path $moduleRoot 'dist'
New-Item -ItemType Directory -Path $distRoot -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMddTHHmmss'
$staging = Join-Path $distRoot "staging-v2.0.0-candidate2-$stamp"
if (Test-Path -LiteralPath $staging) { throw "Immutable staging already exists: $staging" }
New-Item -ItemType Directory -Path $staging | Out-Null

foreach ($relative in $sources.Keys) {
    $target = Join-Path $staging $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    Copy-Item -LiteralPath $sources[$relative] -Destination $target
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant() -ne $expected[$relative]) {
        throw "Package readback mismatch: $relative"
    }
}

foreach ($pair in @(
    @{Source='installer';Target='installer'},
    @{Source='validation\v2.0.0-candidate2';Target='validation'},
    @{Source='data\sql\auth\base';Target='sql\fresh\auth'},
    @{Source='data\sql\world\base';Target='sql\fresh\world'},
    @{Source='data\sql\characters\base';Target='sql\fresh\characters'},
    @{Source='data\sql\migrations\2.0.0';Target='sql\upgrade-from-rogue-paths'}
)) {
    $target = Join-Path $staging $pair.Target
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $moduleRoot $pair.Source) -Destination $target -Recurse
}
Copy-Item -LiteralPath (Join-Path $moduleRoot 'README_RU.md') -Destination (Join-Path $staging 'PROJECT_README_RU.md')
Copy-Item -LiteralPath (Join-Path $moduleRoot 'LICENSE') -Destination (Join-Path $staging 'LICENSE')
Copy-Item -LiteralPath (Join-Path $moduleRoot 'docs\compatibility_matrix.md') -Destination (Join-Path $staging 'COMPATIBILITY.md')

$sourceRoot = Join-Path $staging 'source\mod-cultivation'
$tracked = @(git -c $gitSafe -C $moduleRoot ls-files --cached --others --exclude-standard)
if ($LASTEXITCODE -ne 0) { throw 'Unable to enumerate tracked module sources.' }
foreach ($relative in $tracked) {
    $source = Join-Path $moduleRoot $relative
    $target = Join-Path $sourceRoot $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination $target
}

$rows = @()
foreach ($file in Get-ChildItem -LiteralPath $staging -Recurse -File | Sort-Object FullName) {
    $relative = $file.FullName.Substring($staging.Length + 1).Replace('\','/')
    $rows += [pscustomobject]@{
        path = $relative
        bytes = $file.Length
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
    }
}
$manifest = [ordered]@{
    package = 'mod-cultivation'
    subsystem = 'rogue'
    candidate = 'v2.0.0-candidate2'
    status = 'candidate-installed-runtime-passed-client-acceptance-pending'
    created = (Get-Date).ToString('o')
    source_commit = (git -c $gitSafe -C $moduleRoot rev-parse HEAD)
    compatibility = [ordered]@{
        client = 'JestokyCraft / World of Warcraft 3.3.5a build 12340, ruRU'
        client_exe_sha256 = '8d1067f7d3391248fee97fd7426fd86ac4ef9b88c06bce1b3e65f85c75112ede'
        core_revision = '7c8ed00e7f654617a47bdf728b49707f60aa1aae'
        core_branch = 'release/solitary-1.4.5-rc1'
        platform = 'Windows x64'
    }
    install = 'installer/Install-Cultivation.ps1'
    client_mpq = @('patch-ruRU-A.MPQ','patch-ruRU-Z.MPQ','patch-ruRU-X.MPQ')
    file_count = $rows.Count
    total_bytes = ($rows | Measure-Object bytes -Sum).Sum
    files = $rows
}
$manifestPath = Join-Path $staging 'package-manifest.json'
$manifest | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath $manifestPath -Encoding utf8

$archive = Join-Path $distRoot "mod-cultivation-v2.0.0-candidate2-windows-x64-$stamp.zip"
Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $archive -CompressionLevel Optimal
if (-not (Test-Path -LiteralPath $archive -PathType Leaf) -or (Get-Item $archive).Length -eq 0) {
    throw 'Package archive was not created.'
}
[pscustomobject]@{
    archive = $archive
    bytes = (Get-Item -LiteralPath $archive).Length
    sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()
    staging = $staging
    package_files = $rows.Count + 1
} | ConvertTo-Json -Compress
