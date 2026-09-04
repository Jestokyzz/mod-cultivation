"""Immutable v1.2.0 candidate: verified v2 owner copy, five declared DBC paths."""
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
import generate_rogue_paths as g

ROOT=Path(r'C:\Solo WotLK')
MODULE=Path(__file__).resolve().parents[1]
ARCHIVE=Path(r'F:\JestokyCraft Backups\rogue-paths\pre-change-celestial-v3-20260831')
MPQ=ROOT/'work/wow-patch-interface/mpqcli.exe'
OUTPUT=MODULE/'client_patch/build/v1.2.0-candidate'
CLIENT=ROOT/'test-client/20260831-rogue-paths-v2'
NAMES=('Spell.dbc','SkillLineAbility.dbc','SpellIcon.dbc','SpellRadius.dbc','SpellRange.dbc')


def run(*args):
    return subprocess.run([str(MPQ),*map(str,args)],capture_output=True,check=True).stdout


def main():
    backup=json.loads((ARCHIVE/'manifest.json').read_text(encoding='utf-8-sig'))
    assert backup['Status']=='verified'
    pre=json.loads((ROOT/'work/rogue-paths-celestial-v3/pre-chain.json').read_text(encoding='utf-8-sig'))
    assert pre['status']=='passed'
    sources={Path(r['Source']).name:r for r in backup['Files'] if Path(r['Source']).parent==CLIENT/'Data/ruRU'}
    assert set(sources)=={'patch-ruRU-Z.MPQ','patch-ruRU-A.MPQ'}
    for record in sources.values():
        assert g.sha256(Path(record['Backup'])).lower()==record['SHA256'].lower()
    icons={}
    for icon in ('Ability_Rogue_Trip','INV_Relics_TotemofRage'):
        virtual='Interface\\Icons\\'+icon+'.blp'
        for archive in sorted((CLIENT/'Data').rglob('*.MPQ'),reverse=True):
            read=subprocess.run([str(MPQ),'read',virtual,str(archive)],capture_output=True)
            if not read.returncode:
                assert read.stdout[:4] in (b'BLP1',b'BLP2')
                icons[virtual]={'source':str(archive),'sha256':hashlib.sha256(read.stdout).hexdigest()}
                break
        assert virtual in icons, 'Required exact icon missing; do not substitute'
    assert not OUTPUT.exists(), 'Never overwrite an existing immutable candidate'
    OUTPUT.mkdir(parents=True)
    baseline=Path(sources['patch-ruRU-Z.MPQ']['Backup'])
    info=run('info',baseline).decode()
    assert int(re.search(r'Max files: (\d+)',info)[1])-int(re.search(r'File count: (\d+)',info)[1])>=2
    known=[s.strip() for s in run('list',baseline,'--all').decode().splitlines() if s.strip() and not s.startswith('(')]
    before={s:hashlib.sha256(run('read',s,baseline)).hexdigest() for s in known}
    destination=OUTPUT/'patch-ruRU-Z.MPQ'
    shutil.copy2(baseline,destination)
    changed={}
    clean=OUTPUT/'staging/DBFilesClient'
    clean.mkdir(parents=True)
    for name in NAMES:
        virtual='DBFilesClient\\'+name
        staged=clean/name
        shutil.copy2(MODULE/'client_patch/staging/DBFilesClient'/name,staged)
        assert g.sha256(staged)==g.sha256(MODULE/'client_patch/staging/DBFilesClient'/name)
        if virtual in before: run('remove',destination,virtual)
        else: assert name in ('SpellRadius.dbc','SpellRange.dbc') and not pre['custom_owners'][virtual]
        run('add',destination,staged,'--path',virtual,'--game','wow-wotlk')
        changed[virtual]=g.sha256(staged)
        assert hashlib.sha256(run('read',virtual,destination)).hexdigest()==changed[virtual]
    for virtual,digest in before.items():
        if virtual not in changed:
            assert hashlib.sha256(run('read',virtual,destination)).hexdigest()==digest
    after=run('list',destination,'--all').decode().splitlines()
    for virtual in changed: assert sum(p.lower()==virtual.lower() for p in after)==1
    shutil.copy2(sources['patch-ruRU-A.MPQ']['Backup'],OUTPUT/'patch-ruRU-A.MPQ')
    manifest={'version':'1.2.0','schema_version':2,'status':'candidate-unaccepted','static_validation':'passed',
              'runtime_acceptance':'pending','client_acceptance':'pending','backup_manifest':str(ARCHIVE/'manifest.json'),
              'source_mpq_sha256':g.sha256(baseline),'source_mpq':str(baseline),
              'strategy':'verified-owner-copy; three neutral replacements and two audited additions; no reconstruction or compact',
              'replaced_paths':changed,'preserved_known_paths':{k:v for k,v in before.items() if k not in changed},
              'required_stock_icons':icons,'files':{p.name:g.sha256(p) for p in OUTPUT.glob('*.MPQ')},
              'server_dbc':{name:g.sha256(MODULE/'generated/server/dbc'/name) for name in NAMES}}
    (OUTPUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('PASS five DBC readbacks, unique virtual paths, exact stock BLP icons, unchanged unrelated members:',OUTPUT)


if __name__=='__main__': main()
