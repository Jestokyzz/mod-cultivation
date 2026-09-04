"""Point-replace documented DBC paths in a verified, backed-up owner MPQ copy."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(r'C:\Solo WotLK')
MODULE = Path(__file__).resolve().parents[1]
ARCHIVE = Path(r'F:\JestokyCraft Backups\rogue-paths\pre-change-seven-20260831-v2')
MPQ = ROOT / 'work/wow-patch-interface/mpqcli.exe'
OUTPUT = MODULE / 'client_patch/build/v1.1.0-candidate'


def sha(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()


def run(*args):
    result = subprocess.run([str(MPQ), *map(str, args)], capture_output=True, check=True)
    return result.stdout


def main():
    manifest = json.loads((ARCHIVE / 'manifest.json').read_text(encoding='utf-8-sig'))
    assert manifest['Status'] == 'verified'
    sources = {}
    for record in manifest['Files']:
        source = Path(record['Source'])
        if source.parent == ROOT / 'test-client/20260831-rogue-paths-v1/Data/ruRU' and source.name in ('patch-ruRU-Z.MPQ', 'patch-ruRU-A.MPQ'):
            path = Path(record['Backup'])
            assert sha(path).lower() == record['SHA256'].lower()
            sources[path.name] = path
    assert len(sources) == 2, 'Require the exact active v1 clone owners, not same-named module build artifacts'
    if OUTPUT.exists():
        raise RuntimeError('Candidate output exists; use a new version directory, never overwrite it')
    OUTPUT.mkdir(parents=True)
    baseline = sources['patch-ruRU-Z.MPQ']
    names = [p.strip() for p in run('list', baseline, '--all').decode('utf-8').splitlines()
             if p.strip() and not p.startswith('(')]
    before = {name: hashlib.sha256(run('read', name, baseline)).hexdigest() for name in names}
    destination = OUTPUT / baseline.name
    shutil.copy2(baseline, destination)
    replaced = {}
    stage = MODULE / 'client_patch/staging/DBFilesClient'
    for name in ('Spell.dbc', 'SkillLineAbility.dbc', 'SpellIcon.dbc'):
        virtual = 'DBFilesClient\\' + name
        assert virtual in before, virtual
        run('remove', destination, virtual)
        run('add', destination, stage / name, '--path', virtual, '--game', 'wow-wotlk')
        digest = sha(stage / name)
        assert hashlib.sha256(run('read', virtual, destination)).hexdigest() == digest
        replaced[virtual] = digest
    for name, digest in before.items():
        if name not in replaced:
            assert hashlib.sha256(run('read', name, destination)).hexdigest() == digest, name
    # No new artwork: the accepted A owner remains byte-identical.
    asset = sources['patch-ruRU-A.MPQ']
    shutil.copy2(asset, OUTPUT / asset.name)
    assert sha(OUTPUT / asset.name) == sha(asset)
    result = {'version': '1.1.0', 'status': 'candidate-unaccepted', 'runtime_acceptance': 'pending',
              'backup_manifest': str(ARCHIVE / 'manifest.json'), 'source_mpq_sha256': sha(baseline),
              'source_mpq': str(baseline),
              'strategy': 'verified-owner-copy, documented neutral-path replacement; no reconstruction/compact',
              'replaced_paths': replaced, 'unchanged_member_sha256': {k: v for k, v in before.items() if k not in replaced},
              'files': {p.name: sha(p) for p in OUTPUT.glob('*.MPQ')}}
    (OUTPUT / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('PASS MPQ readback and unrelated-member preservation:', OUTPUT)


if __name__ == '__main__':
    main()
