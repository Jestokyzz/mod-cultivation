"""Immutable audit candidate: exact replacements in verified complete owner copies."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import generate_rogue_paths as g
import dbc_string_integrity

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path(r'C:\Solo WotLK')
CLIENT = Path(r'C:\Games\JestokyCraft')
BACKUP = Path(r'F:\JestokyCraft Backups\cultivation\pre-change-audit-fixes-20260905\manifest.json')
OUT = ROOT / 'client_patch/build/v2.0.0-audit-candidate5'
MPQ = PROJECT / 'work/wow-patch-interface/mpqcli.exe'


def read(virtual, archive, required=True):
    result = subprocess.run([str(MPQ), 'read', virtual, str(archive)], capture_output=True)
    if required and result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace'))
    return result


def main():
    assert not OUT.exists(), 'Immutable candidate already exists'
    assert shutil.disk_usage(BACKUP.parent).free > 5 * 1024**3
    saved = json.loads(BACKUP.read_text('utf-8-sig'))
    assert saved['Status'] == 'verified'
    static = json.loads((ROOT / 'generated/audit-static-tests.json').read_text('utf8'))
    assert static['passed'] and static['tests'] >= 102

    def baseline(path):
        matches = [r for r in saved['Files'] if Path(r['Source']) == path]
        assert len(matches) == 1, str(path)
        record = matches[0]
        source = Path(record['Backup'])
        assert g.sha256(source).lower() == record['SHA256'].lower()
        return source

    virtual_spell = r'DBFilesClient\Spell.dbc'
    virtual_ui = r'Interface\FrameXML\CustomItemTooltips.lua'
    virtual_toc = r'Interface\FrameXML\FrameXML.toc'
    owner_z = CLIENT / 'Data/ruRU/patch-ruRU-Z.MPQ'
    owner_x = CLIENT / 'Data/ruRU/patch-ruRU-X.MPQ'
    owners = {virtual_spell: owner_z, virtual_ui: owner_x, virtual_toc: owner_x}
    archives = sorted(p for p in (CLIENT / 'Data').rglob('*.MPQ')
                      if re.fullmatch(r'patch(?:-ruru)?-[a-z]\.mpq', p.name, re.I))
    inventory = {str(p): g.sha256(p) for p in archives}
    for virtual, expected in owners.items():
        actual = [p for p in archives if read(virtual, p, False).returncode == 0]
        assert actual == [expected], (virtual, actual)
    for owner in (owner_x, owner_z):
        assert g.sha256(owner) == g.sha256(baseline(owner)), 'Live baseline changed'
    toc = read(virtual_toc, owner_x).stdout
    assert b'CustomItemTooltips.lua' in toc, 'Header entry point unreachable'
    original = read(virtual_ui, owner_x).stdout
    marker = b'-- Rogue Paths native tooltip rank header.'
    assert original.count(marker) == 1
    prefix, old_header = original.split(marker)
    old_source = baseline(ROOT / 'client_patch/framexml/CultivationRogueHeader.lua').read_text('utf8')
    expected_body = 'do\n' + old_source.split('\ndo\n', 1)[1]
    old_text = old_header.decode('utf8').replace('\r\n', '\n')
    actual_body = 'do\n' + old_text.split('\ndo\n', 1)[1]
    assert actual_body.strip() == expected_body.strip(), 'Unexplained installed header drift'
    full_ui = prefix + (ROOT / 'client_patch/framexml/CultivationRogueHeader.lua').read_bytes()
    sys.path.insert(0, str(PROJECT / 'work/rogue-paths-schema3-deps'))
    from lupa.lua51 import LuaRuntime
    compiled = LuaRuntime().eval('loadstring')(full_ui.decode('utf8'))
    assert callable(compiled), ('Full embedded Lua 5.1 syntax failure', compiled)
    rows, strings = g.load_dbc(ROOT / 'client_patch/staging/DBFilesClient/Spell.dbc', 234)
    dbc_string_integrity.validate(rows, strings)
    assert g.semantic_non_string_rows(ROOT / 'client_patch/staging/DBFilesClient/Spell.dbc') == g.semantic_non_string_rows(ROOT / 'generated/server/dbc/Spell.dbc')
    OUT.mkdir(parents=True)
    ui_stage = OUT / 'staging/Interface/FrameXML/CustomItemTooltips.lua'
    spell_stage = OUT / 'staging/DBFilesClient/Spell.dbc'
    ui_stage.parent.mkdir(parents=True)
    spell_stage.parent.mkdir(parents=True)
    ui_stage.write_bytes(full_ui)
    shutil.copy2(ROOT / 'client_patch/staging/DBFilesClient/Spell.dbc', spell_stage)
    artifacts = {}
    for owner, virtual, stage in ((owner_x, virtual_ui, ui_stage), (owner_z, virtual_spell, spell_stage)):
        archive = OUT / owner.name
        shutil.copy2(baseline(owner), archive)
        subprocess.run([str(MPQ), 'remove', str(archive), virtual], capture_output=True, check=True)
        subprocess.run([str(MPQ), 'add', str(archive), str(stage), '--path', virtual, '--game', 'wow-wotlk'], capture_output=True, check=True)
        assert hashlib.sha256(read(virtual, archive).stdout).hexdigest() == g.sha256(stage)
        artifacts[owner.name] = {'sha256': g.sha256(archive), 'source_sha256': g.sha256(owner),
                                'replacement': virtual, 'replacement_sha256': g.sha256(stage)}
    assert read(virtual_toc, OUT / owner_x.name).stdout == toc
    manifest = {'candidate': 'v2.0.0-audit-candidate5', 'status': 'packaged-client-acceptance-pending',
                'production_modified': False, 'installable_release': False, 'backup_manifest': str(BACKUP),
                'inventory': inventory, 'owners': {k: str(v) for k, v in owners.items()},
                'artifacts': artifacts, 'entry_point': 'unchanged FrameXML.toc -> CustomItemTooltips.lua',
                'unchanged_ui_prefix_sha256': hashlib.sha256(prefix).hexdigest(),
                'strategy': 'complete owner copies, exact documented replacements, readback verified, no compact/reconstruction'}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'status': manifest['status'], 'package': str(OUT), 'artifacts': artifacts}))


if __name__ == '__main__':
    main()
