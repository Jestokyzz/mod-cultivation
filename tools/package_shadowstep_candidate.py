"""Copy verified owner and replace only Spell.dbc; never reconstruct/compact MPQ."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import generate_rogue_paths as g

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path(r'C:\Solo WotLK')
CLIENT = Path(r'C:\Games\JestokyCraft')
BACKUP = Path(r'F:\JestokyCraft Backups\cultivation\pre-change-shadowstep-20260905')
OUT = ROOT / 'client_patch/build/v2.0.0-shadowstep-candidate3'
MPQ = PROJECT / 'work/wow-patch-interface/mpqcli.exe'
VIRTUAL = r'DBFilesClient\Spell.dbc'
OWNER = CLIENT / 'Data/ruRU/patch-ruRU-Z.MPQ'


def run(*args, required=True):
    result = subprocess.run([str(MPQ), *map(str, args)], capture_output=True)
    if required and result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace'))
    return result


def semantic_diff(old_path, new_path):
    old, os = g.load_dbc(old_path, 234)
    new, ns = g.load_dbc(new_path, 234)
    old = {r[0]: r for r in old}
    new = {r[0]: r for r in new}
    assert old.keys() == new.keys(), 'Unrelated spell IDs changed'
    strings = set(range(136, 152)) | set(range(153, 169)) | set(range(170, 186)) | set(range(187, 203))
    changes = {}
    def raw_string(block, offset):
        end = block.find(b'\0', offset)
        assert end >= offset
        return bytes(block[offset:end])
    for spell, row in old.items():
        diff = []
        for field, value in enumerate(row):
            if field in strings and value >= len(os):
                # Existing unrelated PvP records already have invalid offsets.
                # Preserve their exact bytes; do not invent replacement text.
                assert spell in (85000, 85001, 85002, 85004) and value == new[spell][field] and value >= len(ns), (spell, field)
                continue
            before = raw_string(os, value) if field in strings else value
            after = raw_string(ns, new[spell][field]) if field in strings else new[spell][field]
            if before == after:
                continue
            assert spell in (36554, 86105, 86305), ('Unrelated spell changed', spell, field)
            assert field in range(170, 186) or (spell in (86105, 86305) and field in (29, 30)), (spell, field)
            diff.append({'field': field, 'before': before.decode('utf-8') if isinstance(before, bytes) else before,
                         'after': after.decode('utf-8') if isinstance(after, bytes) else after})
        if diff:
            changes[str(spell)] = diff
    return changes


def main():
    assert not (OUT / 'manifest.json').exists() and not (OUT / OWNER.name).exists(), 'Immutable candidate already exists'
    records = json.loads((BACKUP / 'manifest.json').read_text(encoding='utf-8-sig'))
    assert records['Status'] == 'verified'
    baseline = next(r for r in records['Files'] if Path(r['Source']) == OWNER)
    source = Path(baseline['Backup'])
    assert g.sha256(source).lower() == baseline['SHA256'].lower() == g.sha256(OWNER).lower()
    archives = [p for p in (CLIENT / 'Data').rglob('*.MPQ') if re.fullmatch(r'patch(?:-ruru)?-[a-z]\.mpq', p.name, re.I)]
    inventory = {str(p): g.sha256(p) for p in archives}
    spell_owners = [str(p) for p in archives if run('read', VIRTUAL, p, required=False).returncode == 0]
    toc_owners = [str(p) for p in archives if run('read', r'Interface\FrameXML\FrameXML.toc', p, required=False).returncode == 0]
    assert spell_owners == [str(OWNER)], spell_owners
    assert len(toc_owners) == 1, toc_owners
    OUT.mkdir(parents=True, exist_ok=True)
    stage = OUT / 'staging/DBFilesClient/Spell.dbc'
    stage.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'client_patch/staging/DBFilesClient/Spell.dbc', stage)
    old = OUT / 'audit-input/Spell.dbc'
    old.parent.mkdir(exist_ok=True)
    old.write_bytes(run('read', VIRTUAL, source).stdout)
    diffs = {'client': semantic_diff(old, stage)}
    old_server = next(r for r in records['Files'] if r['Source'] == str(PROJECT / 'WoWBotServer/server/data/dbc/Spell.dbc'))
    diffs['server'] = semantic_diff(Path(old_server['Backup']), ROOT / 'generated/server/dbc/Spell.dbc')
    archive = OUT / OWNER.name
    shutil.copy2(source, archive)
    run('remove', archive, VIRTUAL)
    run('add', archive, stage, '--path', VIRTUAL, '--game', 'wow-wotlk')
    assert hashlib.sha256(run('read', VIRTUAL, archive).stdout).hexdigest() == g.sha256(stage)
    manifest = {'status': 'candidate-static-passed-client-acceptance-pending', 'candidate': 'v2.0.0-shadowstep-candidate3',
                'backup_manifest': str(BACKUP / 'manifest.json'), 'source_mpq_sha256': g.sha256(source),
                'mpq_sha256': g.sha256(archive), 'inventory': inventory, 'spell_owners': spell_owners,
                'toc_owners_unchanged': toc_owners, 'strategy': 'exact Spell.dbc replacement in verified owner copy; no compact',
                'preexisting_limitation': '28 invalid description string offsets in unrelated PvP baseline records; exact fields preserved, not a new defect or full DBC acceptance',
                'semantic_diff': diffs, 'client_spell_sha256': g.sha256(stage),
                'server_spell_sha256': g.sha256(ROOT / 'generated/server/dbc/Spell.dbc'),
                'worldserver_sha256': g.sha256(PROJECT / 'WoWBotServer/build-solitary-v4-ninja/bin/worldserver.exe')}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': manifest['status'], 'package': str(OUT), 'changed_spells': list(diffs['client'])}))


if __name__ == '__main__':
    main()
