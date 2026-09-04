[CmdletBinding()]
param(
    [string]$ClientRoot = 'C:\Solo WotLK\test-client\20260831-rogue-paths-v3'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$moduleRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$expected = [ordered]@{
    'patch-ruRU-A.MPQ' = '6b6055e66d0944b61b7cf33ca2a0da27a6575732c2d5ffc263c5fd8e86dbc69f'
    'patch-ruRU-Z.MPQ' = '496b493c082cedd1b0f3633dcd8577b6790285ef740601d8f402c2a3dddc148c'
    'patch-ruRU-X.MPQ' = 'e80ae73b2355bd957e417b06f05b829553e07c2189585c1517e154d7dc836479'
}

$distRoot = Join-Path $moduleRoot 'dist'
New-Item -ItemType Directory -Path $distRoot -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMddTHHmmss'
$staging = Join-Path $distRoot "client-root-overlay-v2.0.0-candidate2-$stamp"
if (Test-Path -LiteralPath $staging) { throw "Immutable staging already exists: $staging" }
$localeRoot = Join-Path $staging 'Data\ruRU'
New-Item -ItemType Directory -Path $localeRoot -Force | Out-Null

$checksumLines = @()
foreach ($name in $expected.Keys) {
    $source = Join-Path $ClientRoot "Data\ruRU\$name"
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing client patch: $source" }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash.ToLowerInvariant()
    if ($actual -ne $expected[$name]) { throw "Client patch hash mismatch for $name. Expected $($expected[$name]), got $actual" }
    $target = Join-Path $localeRoot $name
    Copy-Item -LiteralPath $source -Destination $target
    $readback = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()
    if ($readback -ne $expected[$name]) { throw "Readback hash mismatch for $name" }
    $checksumLines += "$readback  Data/ruRU/$name"
}

Copy-Item -LiteralPath (Join-Path $moduleRoot 'installer\CLIENT_OVERLAY_README_RU.txt') -Destination (Join-Path $staging 'README_FIRST_RU.txt')
$checksumLines | Set-Content -LiteralPath (Join-Path $staging 'SHA256SUMS.txt') -Encoding utf8

$archive = Join-Path $distRoot "JestokyCraft-Cultivation-client-root-overlay-v2.0.0-candidate2-$stamp.zip"
Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $archive -CompressionLevel Optimal
if (-not (Test-Path -LiteralPath $archive -PathType Leaf) -or (Get-Item -LiteralPath $archive).Length -eq 0) {
    throw 'Client overlay archive was not created.'
}

[pscustomobject]@{
    archive = $archive
    bytes = (Get-Item -LiteralPath $archive).Length
    sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()
    staging = $staging
    root_layout = 'Data/ruRU/*.MPQ'
} | ConvertTo-Json -Compress
