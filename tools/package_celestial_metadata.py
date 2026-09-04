"""Generate schema-2 migration without replacing historical 1.0/1.1 packages."""
from pathlib import Path
import json
import hashlib

ROOT=Path(__file__).resolve().parents[1]
VERSION='1.2.0'
DEST=ROOT/'data/sql/migrations'/VERSION
MANIFEST=json.loads((ROOT/'data/cultivation_rogue_spell_manifest.json').read_text(encoding='utf-8'))
BACKUP=Path(r'F:\JestokyCraft Backups\rogue-paths\pre-change-celestial-v3-20260831')
cfg=MANIFEST['celestial_revision']
retired=','.join(map(str,cfg['retired_auras']))
group=cfg['suppression_group']
files={
    'world.up.sql':(ROOT/'data/sql/world/base/cultivation_rogue_spells.sql').read_text(encoding='utf-8'),
    'world.preflight.sql':f'SELECT DATABASE();\nSELECT * FROM spell_group WHERE id={group};\nSELECT * FROM spell_group_stack_rules WHERE group_id={group};\n',
    'world.postflight.sql':f'SELECT * FROM spell_group WHERE id={group} ORDER BY spell_id;\nSELECT * FROM spell_group_stack_rules WHERE group_id={group};\nSELECT COUNT(*) AS ranks_expected_252 FROM spell_ranks WHERE spell_id BETWEEN 86000 AND 86999;\n',
    'characters.preflight.sql':'SELECT DATABASE();\nSELECT COUNT(*) AS online_must_be_zero FROM characters WHERE online<>0;\nSELECT schema_version,COUNT(*) FROM character_cultivation_rogue GROUP BY schema_version;\n',
    'characters.up.sql':f'START TRANSACTION;\nDELETE FROM character_aura WHERE spell IN ({retired});\nUPDATE character_cultivation_rogue SET schema_version=2 WHERE schema_version<2;\nCOMMIT;\n',
    'characters.postflight.sql':f'SELECT COUNT(*) AS stale_auras_must_be_zero FROM character_aura WHERE spell IN ({retired});\nSELECT COUNT(*) AS obsolete_schema_must_be_zero FROM character_cultivation_rogue WHERE schema_version<2;\n',
    'characters.rollback.sql':'-- Restore v2 binary/DBC/MPQ first, world stopped. Active spells, panels and cooldowns are not rewritten.\nSTART TRANSACTION;\nDELETE FROM character_aura WHERE spell IN (86597,86598,86581);\nUPDATE character_cultivation_rogue SET schema_version=1 WHERE schema_version=2;\nCOMMIT;\n',
    'auth.up.sql':'-- No authentication or RBAC change in 1.2.0.\nSELECT DATABASE();\n',
    'auth.rollback.sql':'-- No authentication or RBAC change.\nSELECT DATABASE();\n',
}
backup=json.loads((BACKUP/'manifest.json').read_text(encoding='utf-8-sig'))
assert backup['Status']=='verified'
record=next(r for r in backup['Files'] if Path(r['Source'])==ROOT/'data/sql/world/base/cultivation_rogue_spells.sql')
payload=Path(record['Backup']).read_bytes()
assert hashlib.sha256(payload).hexdigest().lower()==record['SHA256'].lower()
files['world.rollback.sql']=f'-- Restore exact v2 server/client set while stopped.\nDELETE FROM spell_group WHERE id={group};\nDELETE FROM spell_group_stack_rules WHERE group_id={group};\n'+payload.decode('utf-8-sig')
DEST.mkdir(parents=True,exist_ok=True)
for name,text in files.items():
    (DEST/name).write_text(f'-- mod-cultivation {VERSION}, candidate, schema 2; correct isolated DB only.\n'+text,encoding='utf-8')
(DEST/'manifest.json').write_text(json.dumps({'version':VERSION,'schema_version':2,'status':'candidate-unaccepted',
    'active_spell_ids_unchanged':True,'sha_balance_unchanged':True,'retired_auras':cfg['retired_auras'],
    'new_auras':[86597,86598],'backup_manifest':str(BACKUP/'manifest.json'),
    'files':{name:hashlib.sha256((DEST/name).read_bytes()).hexdigest() for name in files}},indent=2)+'\n',encoding='utf-8')
print('PASS schema-2 migration generated; historical packages and all active IDs preserved')
