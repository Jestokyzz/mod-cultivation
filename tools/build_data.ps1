[CmdletBinding()]
param(
    [string]$Python='C:\Users\posha\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe',
    [string]$ProjectRoot='C:\Solo WotLK',
    [string]$CleanBaselineRoot='C:\Solo WotLK\work\mobility-retirement-v1\clean-dbc'
)
$ErrorActionPreference='Stop'
$moduleRoot=Split-Path $PSScriptRoot
$arguments=@(
    (Join-Path $PSScriptRoot 'generate_rogue_paths.py'),
    '--manifest',(Join-Path $moduleRoot 'data\cultivation_rogue_spell_manifest.json'),
    '--client-spell-baseline',(Join-Path $CleanBaselineRoot 'client\Spell.dbc'),
    '--server-spell-baseline',(Join-Path $CleanBaselineRoot 'server\Spell.dbc'),
    '--skill-line-baseline',(Join-Path $CleanBaselineRoot 'server\SkillLineAbility.dbc'),
    '--client-spell-output',(Join-Path $moduleRoot 'client_patch\staging\DBFilesClient\Spell.dbc'),
    '--server-spell-output',(Join-Path $moduleRoot 'generated\server\dbc\Spell.dbc'),
    '--client-skill-line-output',(Join-Path $moduleRoot 'client_patch\staging\DBFilesClient\SkillLineAbility.dbc'),
    '--server-skill-line-output',(Join-Path $moduleRoot 'generated\server\dbc\SkillLineAbility.dbc'),
    '--cpp-output',(Join-Path $moduleRoot 'src\rogue\generated\RoguePathGeneratedSpells.h'),
    '--sql-output',(Join-Path $moduleRoot 'data\sql\world\base\cultivation_rogue_spells.sql'),
    '--sql-check-only',
    '--spell-map-output',(Join-Path $moduleRoot 'docs\spell_id_map.md'),
    '--report',(Join-Path $moduleRoot 'generated\generation_report.json')
)
& $Python @arguments
if($LASTEXITCODE -ne 0){throw 'DBC generation failed'}
& $Python (Join-Path $PSScriptRoot 'generate_schema6_migration.py')
if($LASTEXITCODE -ne 0){throw 'Schema 6 migration manifest generation failed'}
& $Python (Join-Path $PSScriptRoot 'build_path_icons.py')
if($LASTEXITCODE -ne 0){throw 'Approved icon generation failed'}
& $Python (Join-Path $PSScriptRoot 'test_generated_data.py')
if($LASTEXITCODE -ne 0){throw 'Offline regression failed'}
& $Python (Join-Path $PSScriptRoot 'test_shadowstep_contract.py')
if($LASTEXITCODE -ne 0){throw 'Shadowstep fresh-state contract failed'}
& $Python (Join-Path $PSScriptRoot 'test_audit_fixes.py')
if($LASTEXITCODE -ne 0){throw 'Audit source/data contract failed'}
& $Python (Join-Path $PSScriptRoot 'test_native_header.py')
if($LASTEXITCODE -ne 0){throw 'Native FrameXML Lua 5.1 contract failed'}
& $Python (Join-Path $PSScriptRoot 'test_cultivation_architecture.py')
if($LASTEXITCODE -ne 0){throw 'Cultivation architecture regression failed'}
& $Python (Join-Path $PSScriptRoot 'test_visibility_schema3.py')
if($LASTEXITCODE -ne 0){throw 'Stock tooltip binding regression failed'}
& $Python (Join-Path $PSScriptRoot 'test_seven_styled_icons.py')
if($LASTEXITCODE -ne 0){throw 'Seven styled icon regression failed'}
& $Python (Join-Path $PSScriptRoot 'test_sha_presentation.py')
if($LASTEXITCODE -ne 0){throw 'Sha presentation regression failed'}
& $Python (Join-Path $PSScriptRoot 'test_sha_candidate41.py')
if($LASTEXITCODE -ne 0){throw 'Sha candidate41 gameplay/tooltip regression failed'}
& $Python (Join-Path $PSScriptRoot 'test_tooltip_presentation.py')
if($LASTEXITCODE -ne 0){throw 'Tooltip presentation regression failed'}
& $Python (Join-Path $PSScriptRoot 'test_tooltip_stock_values.py')
if($LASTEXITCODE -ne 0){throw 'Stock tooltip numeric/variable regression failed'}
& $Python (Join-Path $PSScriptRoot 'validate_rogue_path_tooltips.py')
if($LASTEXITCODE -ne 0){throw 'Schema 3 artifact audit failed'}
& $Python (Join-Path $PSScriptRoot 'generate_release_manifest.py')
if($LASTEXITCODE -ne 0){throw 'Candidate source manifest generation failed'}
Write-Host 'PASS: DBC, mapping, SQL, ID documentation and offline regression'
