"""Immutable schema-5 package; preserve unknown members of the verified MPQ owner.

Never reconstruct an archive from listfile or edit a live MPQ. All new/changed
payloads come from a fresh complete staging directory; read every replacement back.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import generate_rogue_paths as g

PROJECT = Path(r'C:\Solo WotLK')
MODULE = Path(__file__).resolve().parents[1]
CLIENT = PROJECT / 'test-client/20260831-rogue-paths-v3'
BACKUP = Path(r'F:\JestokyCraft Backups\rogue-paths\pre-change-schema4-install-20260901T060529')
MPQ = PROJECT / 'work/wow-patch-interface/mpqcli.exe'
TABLES = ('Spell.dbc', 'SkillLineAbility.dbc', 'SpellIcon.dbc', 'SpellRadius.dbc', 'SpellRange.dbc', 'SpellDescriptionVariables.dbc')


def run(*args):
    return subprocess.run([str(MPQ), *map(str, args)], capture_output=True, check=True).stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', default='v1.5.0-candidate1')
    parser.add_argument('--native-only', action='store_true',
                        help='Package only native game files; omit RoguePathsUI.')
    args = parser.parse_args()
    if not re.fullmatch(r'v1\.5\.0-candidate[1-9][0-9]*', args.name):
        raise ValueError('Explicit schema-5 candidate name required')
    out = MODULE / 'client_patch/build' / args.name
    if out.exists():
        raise ValueError('Immutable candidate already exists')
    source_manifest = MODULE / 'data/cultivation_rogue_spell_manifest.json'
    central = json.loads(source_manifest.read_text(encoding='utf-8'))
    artifact_audit = json.loads((MODULE / 'generated/schema3-audit/artifact-validation.json').read_text(encoding='utf-8'))
    assert artifact_audit['status'] == 'static-pass-runtime-pending'
    assert artifact_audit['manifest_sha256'] == g.sha256(source_manifest)
    if args.native_only:
        lua = {'status': 'not-applicable', 'reason': 'native-only package contains no AddOn', 'files': {}}
    else:
        lua = json.loads((MODULE / 'generated/schema3-audit/lua-test.json').read_text(encoding='utf-8'))
        assert lua['status'] == 'passed'
        for name, digest in lua['files'].items():
            assert g.sha256(MODULE / 'client_patch/addon/RoguePathsUI' / name) == digest, 'Stale Lua validation'
    backup = json.loads((BACKUP / 'manifest.json').read_text(encoding='utf-8-sig'))
    assert backup['Status'] == 'installed-unaccepted'
    runtime_root = str(CLIENT / 'Data/ruRU').lower()
    sources = {}
    for item in backup['Files']:
        target = Path(item.get('Target', ''))
        if str(target.parent).lower() == runtime_root and target.name in ('patch-ruRU-A.MPQ', 'patch-ruRU-Z.MPQ'):
            assert item.get('Existed') is True
            sources[target.name] = item
    assert len(sources) == 2
    for item in sources.values():
        assert g.sha256(Path(item['Backup'])).lower() == item['SHA256'].lower()
    owners = {}
    custom = [p for p in (CLIENT / 'Data').rglob('*.MPQ') if re.fullmatch(r'patch(?:-ruru)?-[a-z]\.mpq', p.name, re.I)]
    for name in TABLES:
        virtual = 'DBFilesClient\\' + name
        owners[virtual] = [str(p) for p in custom if subprocess.run([str(MPQ), 'read', virtual, str(p)], capture_output=True).returncode == 0]
        assert owners[virtual] in ([], [str(CLIENT / 'Data/ruRU/patch-ruRU-Z.MPQ')]), ('Conflicting DBC owner', virtual, owners[virtual])
    toc_owners = [str(p) for p in custom if subprocess.run([str(MPQ), 'read', 'Interface\\FrameXML\\FrameXML.toc', str(p)], capture_output=True).returncode == 0]
    assert len(toc_owners) == 1, 'FrameXML owner ambiguity'
    baseline = Path(sources['patch-ruRU-Z.MPQ']['Backup'])
    active_owner = CLIENT / 'Data/ruRU/patch-ruRU-Z.MPQ'
    active_sha = g.sha256(active_owner)
    recognized_owner = active_sha.lower() == g.sha256(baseline).lower()
    for previous in (MODULE / 'client_patch/build').glob('v1.*-candidate*/manifest.json'):
        evidence = json.loads(previous.read_text(encoding='utf-8'))
        if evidence.get('files', {}).get('patch-ruRU-Z.MPQ', '').lower() == active_sha.lower():
            recognized_owner = True
    assert recognized_owner, 'Current owner is neither pinned baseline nor a manifested schema-3 package'
    info = run('info', baseline).decode()
    assert int(re.search(r'Max files: (\d+)', info)[1]) - int(re.search(r'File count: (\d+)', info)[1]) >= 1
    known = [p.strip() for p in run('list', baseline, '--all').decode().splitlines() if p.strip() and not p.startswith('(')]
    before = {p: hashlib.sha256(run('read', p, baseline)).hexdigest() for p in known}
    out.mkdir(parents=True)
    clean = out / 'staging/DBFilesClient'
    clean.mkdir(parents=True)
    destination = out / 'patch-ruRU-Z.MPQ'
    shutil.copy2(baseline, destination)
    replacements = {}
    for name in TABLES:
        virtual = 'DBFilesClient\\' + name
        staged = clean / name
        shutil.copy2(MODULE / 'client_patch/staging/DBFilesClient' / name, staged)
        if virtual in before:
            run('remove', destination, virtual)
        else:
            assert owners[virtual] in ([], [str(active_owner)]), ('Unexplained archive addition', virtual)
        run('add', destination, staged, '--path', virtual, '--game', 'wow-wotlk')
        replacements[virtual] = g.sha256(staged)
        assert hashlib.sha256(run('read', virtual, destination)).hexdigest() == replacements[virtual]
    for virtual, digest in before.items():
        if virtual not in replacements:
            assert hashlib.sha256(run('read', virtual, destination)).hexdigest() == digest
    after = run('list', destination, '--all').decode().splitlines()
    for virtual in replacements:
        assert sum(x.lower() == virtual.lower() for x in after) == 1
    # Texture owner is built from a COMPLETE declared asset catalog, not an
    # archive's listfile. Verify the previous 78 assets against the pinned owner.
    icon_catalog = json.loads((PROJECT / 'work/mobility-retirement-v1/icons-manifest.json').read_text(encoding='utf-8'))
    icon_records = icon_catalog['files']
    icon_contract = json.loads(source_manifest.read_text(encoding='utf-8'))['path_icons']
    expected_count = icon_contract['count'] + len(icon_contract.get('shared_icons', []))
    assert len(icon_records) == expected_count
    original_assets = Path(sources['patch-ruRU-A.MPQ']['Backup'])
    asset_stage = out / 'asset-staging'
    asset_stage.mkdir()
    texture_hashes = {}
    for record in icon_records:
        virtual = record['virtual_path']
        assert virtual.startswith('Interface\\Icons\\')
        assert virtual not in texture_hashes
        payload = Path(record['blp'])
        assert g.sha256(payload) == record['blp_sha256']
        if record['icon_id'] < 6178:
            assert hashlib.sha256(run('read', virtual, original_assets)).hexdigest() == record['blp_sha256'], ('Prior icon changed', virtual)
        for archive in custom:
            found = subprocess.run([str(MPQ), 'read', virtual, str(archive)], capture_output=True)
            if found.returncode == 0:
                assert archive == CLIENT / 'Data/ruRU/patch-ruRU-A.MPQ', ('Texture owner overlap', virtual, str(archive))
        staged = asset_stage.joinpath(*virtual.split('\\'))
        staged.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(payload, staged)
        texture_hashes[virtual] = record['blp_sha256']
    assets = out / 'patch-ruRU-A.MPQ'
    run('create', asset_stage, '--output', assets, '--game', 'wow-wotlk')
    for virtual, digest in texture_hashes.items():
        assert hashlib.sha256(run('read', virtual, assets)).hexdigest() == digest
    packed_textures = [p.strip() for p in run('list', assets, '--all').decode().splitlines() if p.strip() and not p.startswith('(')]
    assert sorted(packed_textures) == sorted(texture_hashes)

    addon = out / 'Interface/AddOns/RoguePathsUI'
    if not args.native_only:
        shutil.copytree(MODULE / 'client_patch/addon/RoguePathsUI', addon)
    server = out / 'server/dbc'
    server.mkdir(parents=True)
    for name in TABLES:
        shutil.copy2(MODULE / 'generated/server/dbc' / name, server / name)
    binary = PROJECT / 'WoWBotServer/build-solitary-v4-ninja/bin/worldserver.exe'
    shutil.copy2(binary, out / 'server/worldserver.exe')
    server_config = out / 'server/configs/modules/mod_cultivation.conf'
    server_config.parent.mkdir(parents=True)
    config_text = (MODULE / 'conf/mod_cultivation.conf.dist').read_text(encoding='utf-8')
    server_config.write_text(config_text.rstrip() + '\nCultivation.Rogue.Celestial.TestHarness = 1\n', encoding='utf-8')
    retired_config_keys = (
        'PvPDamagePct', 'PvPDurationMs', 'MarkCharges', 'ArmorIgnorePct',
        'MarkDurationMs', 'FrontShadowstepDamagePct', 'RequiredControlTimeMs',
    )
    assert not any(key in config_text for key in retired_config_keys), 'Retired runtime override survived in packaged config'
    shutil.copytree(MODULE / 'data/sql/migrations/1.5.0', out / 'sql')
    source_files = [source_manifest, *sorted((MODULE / 'src').rglob('*.cpp')), *sorted((MODULE / 'src').rglob('*.h'))]
    presentation = json.loads(source_manifest.read_text(encoding='utf-8')).get('tooltip_presentation_revision')
    result = {'version': '1.5.0', 'schema_version': 5, 'status': 'candidate-unaccepted', 'static_validation': 'passed',
        'native_acceptance': 'pending', 'client_acceptance': 'pending', 'source_mpq': str(baseline),
        'source_mpq_sha256': g.sha256(baseline), 'backup_manifest': str(BACKUP / 'manifest.json'),
        'strategy': 'verified-owner copy; six complete staged DBC replacements/additions with readback; no compact or reconstruction; '
                    + ('native game files only' if args.native_only else 'loose presentation addon included'),
        'replaced_paths': replacements, 'preflight_custom_owners': owners, 'framexml_owners_unchanged': toc_owners,
        'recognized_active_owner_sha256': active_sha,
        'texture_owner': 'patch-ruRU-A.MPQ', 'texture_paths': texture_hashes,
        'texture_contract': f"{expected_count} approved BLP assets; path spells keep framed icons while active auras use standard icons; shared vulnerability/Blood Thrill icons and the three requested Stealth Mastery filenames are included",
        'tooltip_presentation': presentation,
        'sha_presentation': json.loads(source_manifest.read_text(encoding='utf-8')).get('sha_presentation_revision'),
        'lua_validation': lua,
        'presentation_sources': {str(p.relative_to(MODULE)).replace('\\', '/'): g.sha256(p) for p in
            [MODULE / 'tools/generate_rogue_paths.py', MODULE / 'tools/tooltip_stock.py',
             MODULE / 'tools/visibility_schema3.py', MODULE / 'tools/celestial_aura_tooltips.py',
             MODULE / 'tools/sha_aura_tooltips.py', MODULE / 'tools/test_sha_presentation.py',
             MODULE / 'tools/test_tooltip_presentation.py', MODULE / 'tools/test_talent_ui.py']},
        'preserved_known_paths': {k: value for k, value in before.items() if k not in replacements},
        'files': {p.name: g.sha256(p) for p in out.glob('*.MPQ')},
        'addon': {} if args.native_only else {
            p.relative_to(out).as_posix(): g.sha256(p) for p in addon.iterdir() if p.is_file()},
        'server_dbc': {name: g.sha256(server / name) for name in TABLES}, 'worldserver_sha256': g.sha256(out / 'server/worldserver.exe'),
        'server_config_sha256': g.sha256(server_config),
        'sources': {p.relative_to(MODULE).as_posix(): g.sha256(p) for p in source_files},
        'compatibility': {'client': str(CLIENT), 'server': str(PROJECT / 'test-server/20260831-rogue-paths-v3'),
            'client_exe_sha256': g.sha256(CLIENT / 'Wow-NWQ.exe'), 'core': 'AzerothCore 7c8ed00e7f65+ local integration changes',
            'production': 'not authorized; clone acceptance required', 'graphics': '1920x1080 gxWindow=1 gxMaximize=1; actual GUI pending'}}
    (out / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    contents = 'native game files only' if args.native_only else 'addon included'
    print('PASS: immutable package, 6 DBC readbacks, preserved MPQ members, '
          + contents + ', versioned SQL and built server:', out)


if __name__ == '__main__':
    main()
