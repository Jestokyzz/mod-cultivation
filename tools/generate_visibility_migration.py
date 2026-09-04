"""Versioned schema-3 SQL; writes candidate artifacts only, never executes SQL."""
import json
from pathlib import Path
import generate_rogue_paths as g

ROOT = Path(__file__).resolve().parents[1]


def guard(role, condition, message):
    # source via mysql supports DELIMITER. No unbounded mutation on the wrong DB.
    return f'''DELIMITER $$
DROP PROCEDURE IF EXISTS rogue_paths_schema3_gate$$
CREATE PROCEDURE rogue_paths_schema3_gate()
BEGIN
 IF DATABASE() <> 'rogue_paths_test_{role}_v3' THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Wrong database: isolated Cultivation / Rogue v3 required';
 END IF;
 IF NOT ({condition}) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='{message}';
 END IF;
END$$
DELIMITER ;
CALL rogue_paths_schema3_gate();
DROP PROCEDURE rogue_paths_schema3_gate;
'''


def main():
    manifest = json.loads((ROOT / 'data/cultivation_rogue_spell_manifest.json').read_text(encoding='utf-8'))
    out = ROOT / 'data/sql/migrations/1.3.0'
    out.mkdir(parents=True, exist_ok=True)
    before = Path(r'F:\JestokyCraft Backups\rogue-paths\pre-change-rogue-visibility-schema3-20260831')
    backup = json.loads((before / 'manifest.json').read_text(encoding='utf-8-sig'))
    old_world = next(x for x in backup['Files'] if x['Source'].replace('\\', '/').endswith('/mod-cultivation/data/sql/world/base/cultivation_rogue_spells.sql'))
    assert g.sha256(Path(old_world['Backup'])).lower() == old_world['SHA256'].lower()
    display_ids = ','.join(str(item['spell_id']) for item in manifest['display_passives'])
    files = {
        'auth.preflight.sql': '-- No auth schema changes.\nSELECT DATABASE();\n',
        'auth.up.sql': '-- No auth schema changes.\n',
        'auth.postflight.sql': '-- No auth schema changes.\nSELECT DATABASE();\n',
        'auth.rollback.sql': '-- No auth schema changes.\n',
        'world.preflight.sql': guard('world', '(SELECT COUNT(*) FROM spell_group WHERE id=1900 AND spell_id IN (86597,86598))=2', 'Schema 2 group baseline missing'),
        'world.up.sql': guard('world', '1', 'Wrong DB') + (ROOT / 'data/sql/world/base/cultivation_rogue_spells.sql').read_text(encoding='utf-8'),
        'world.postflight.sql': guard('world', f'(SELECT COUNT(*) FROM spell_script_names WHERE ABS(spell_id) IN ({display_ids}))=0 AND (SELECT COUNT(*) FROM spell_proc WHERE ABS(SpellId) IN ({display_ids}))=0 AND (SELECT COUNT(*) FROM spell_ranks WHERE spell_id IN ({display_ids}))=0', 'Display spell acquired gameplay metadata'),
        'world.rollback.sql': guard('world', '1', 'Wrong DB') + Path(old_world['Backup']).read_text(encoding='utf-8'),
        'characters.preflight.sql': guard('characters', '(SELECT COUNT(*) FROM characters WHERE online<>0)=0 AND (SELECT COUNT(*) FROM character_cultivation_rogue WHERE schema_version>3)=0', 'Online characters or unknown schema'),
        'characters.up.sql': guard('characters', '(SELECT COUNT(*) FROM characters WHERE online<>0)=0', 'Stop isolated world before migration') + 'START TRANSACTION;\nUPDATE character_cultivation_rogue SET schema_version=3 WHERE schema_version<3;\nCOMMIT;\n',
        'characters.postflight.sql': guard('characters', '(SELECT COUNT(*) FROM character_cultivation_rogue WHERE schema_version<>3)=0', 'Character schema not migrated'),
        'characters.rollback.sql': guard('characters', '(SELECT COUNT(*) FROM characters WHERE online<>0)=0', 'Stop isolated world before rollback') + f'START TRANSACTION;\nDELETE FROM character_spell WHERE spell IN ({display_ids});\nDELETE FROM character_aura WHERE spell IN ({display_ids});\nUPDATE character_cultivation_rogue SET schema_version=2 WHERE schema_version=3;\nCOMMIT;\n',
    }
    for name, text in files.items():
        (out / name).write_text('-- mod-cultivation 1.3.0 candidate, schema 3; not production-approved.\n' + text, encoding='utf-8')
    info = {'version': '1.3.0', 'schema_version': 3, 'status': 'candidate-unaccepted',
            'source_manifest_sha256': g.sha256(ROOT / 'data/cultivation_rogue_spell_manifest.json'),
            'backup_required': 'verified fresh world/characters dumps on F: before execution',
            'files': {name: g.sha256(out / name) for name in files}}
    (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    print('Generated schema-3 versioned SQL with isolated-DB preflight/postflight/rollback; not executed')


if __name__ == '__main__':
    main()
