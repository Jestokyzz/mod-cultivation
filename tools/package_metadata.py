"""Generate versioned migrations, rollback mappings, and the evidence matrix."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / 'data/cultivation_rogue_spell_manifest.json').read_text(encoding='utf-8'))
VERSION = '1.1.0'
version_dir = ROOT / 'data/sql/migrations' / VERSION
version_dir.mkdir(parents=True, exist_ok=True)
inputs = {
    'auth.up.sql': 'auth/base/cultivation_rbac.sql',
    'characters.up.sql': 'characters/base/character_cultivation_rogue.sql',
    'world.up.sql': 'world/base/cultivation_rogue_spells.sql',
}
for name, relative in inputs.items():
    text = (ROOT / 'data/sql' / relative).read_text(encoding='utf-8')
    if name == 'world.up.sql':
        text += '\n' + (ROOT / 'data/sql/world/base/cultivation_command.sql').read_text(encoding='utf-8')
    (version_dir / name).write_text(f'-- Cultivation / Rogue {VERSION} candidate. Select the correct isolated database first.\n' + text, encoding='utf-8')

mapping = []
for ability in manifest['active_spells'] + manifest['passive_spells']:
    if not ability.get('stock_icon'):
        continue  # extension rollback preserves the existing 39-ability system
    for rank, base in enumerate(ability['base_spell_chain']):
        for path in ('celestial', 'sha'):
            mapping.append((ability[f'{path}_first'] + rank, base))
new_ids = [a for a, _ in mapping] + [i for i in manifest['technical_spells'].values() if i >= 86575]
id_list = ','.join(map(str, new_ids))
rollback = [
    '-- Stop worldserver and verify the characters DB backup before running.',
    '-- Restores both spec masks, spell action slots and the longest cooldown.',
    'START TRANSACTION;',
    'CREATE TEMPORARY TABLE rogue_path_rollback_map (custom_id INT UNSIGNED PRIMARY KEY, base_id INT UNSIGNED NOT NULL);',
    'INSERT INTO rogue_path_rollback_map VALUES ' + ','.join(f'({a},{b})' for a, b in mapping) + ';',
    'INSERT INTO character_spell (guid,spell,specMask) SELECT s.guid,m.base_id,BIT_OR(s.specMask) FROM character_spell s JOIN rogue_path_rollback_map m ON s.spell=m.custom_id GROUP BY s.guid,m.base_id ON DUPLICATE KEY UPDATE specMask=character_spell.specMask | VALUES(specMask);',
    'UPDATE character_action a JOIN rogue_path_rollback_map m ON a.action=m.custom_id SET a.action=m.base_id WHERE a.type=0;',
    'INSERT INTO character_spell_cooldown (guid,spell,category,item,time,needSend) SELECT c.guid,m.base_id,MAX(c.category),MAX(c.item),MAX(c.time),MAX(c.needSend) FROM character_spell_cooldown c JOIN rogue_path_rollback_map m ON c.spell=m.custom_id GROUP BY c.guid,m.base_id ON DUPLICATE KEY UPDATE time=GREATEST(character_spell_cooldown.time,VALUES(time)),needSend=GREATEST(character_spell_cooldown.needSend,VALUES(needSend));',
    f'DELETE FROM character_spell WHERE spell IN ({id_list});',
    f'DELETE FROM character_spell_cooldown WHERE spell IN ({id_list});',
    f'DELETE FROM character_aura WHERE spell IN ({id_list});',
    'DROP TEMPORARY TABLE rogue_path_rollback_map;',
    'COMMIT;',
    f'SELECT COUNT(*) AS remaining_extension_spells FROM character_spell WHERE spell IN ({id_list});',
]
(version_dir / 'characters.rollback.sql').write_text('\n'.join(rollback)+'\n', encoding='utf-8')
archive = Path(r'F:\JestokyCraft Backups\rogue-paths\pre-change-seven-20260831-v2')
backup = json.loads((archive / 'manifest.json').read_text(encoding='utf-8-sig'))
assert backup['Status'] == 'verified'
record = next(r for r in backup['Files'] if r['Source'].endswith('mod-cultivation\\data\\sql\\world\\base\\cultivation_rogue_spells.sql'))
baseline_sql = Path(record['Backup']).read_bytes()
assert hashlib.sha256(baseline_sql).hexdigest().lower() == record['SHA256'].lower()
(version_dir / 'world.rollback.sql').write_text('-- Restore matching v1 binaries + all three DBC + MPQ owners with worldserver stopped.\n' +
    'DELETE FROM spell_custom_attr WHERE spell_id BETWEEN 86000 AND 86999;\n' + baseline_sql.decode('utf-8-sig'), encoding='utf-8')
(version_dir / 'auth.rollback.sql').write_text('-- 1.1.0 does not change v1 command permissions; retain RBAC 1001.\nSELECT DATABASE();\n', encoding='utf-8')
(version_dir / 'world.preflight.sql').write_text('''SELECT DATABASE() AS target_database;
SELECT * FROM command WHERE name='cultivation';
SELECT COUNT(*) AS conflicting_rank_rows FROM spell_ranks WHERE spell_id BETWEEN 86000 AND 86999;
SELECT COUNT(*) AS conflicting_script_rows FROM spell_script_names WHERE ABS(spell_id) BETWEEN 86000 AND 86999;
-- On first installation all conflict counts must be zero. Existing owned installs require the previous manifest.
''', encoding='utf-8')
(version_dir / 'auth.preflight.sql').write_text("SELECT DATABASE() AS target_database;\nSELECT * FROM rbac_permissions WHERE id=1001;\n-- Must be absent on first installation.\n", encoding='utf-8')
(version_dir / 'characters.preflight.sql').write_text("SELECT DATABASE() AS target_database;\nSELECT COUNT(*) AS online_characters FROM characters WHERE online<>0;\n-- Stop worldserver before migration or rollback.\n", encoding='utf-8')
rank_count = sum(len(a['base_spell_chain']) * 2 for a in manifest['active_spells'] + manifest['passive_spells'] if len(a['base_spell_chain']) > 1)
(version_dir / 'world.postflight.sql').write_text(f'''SELECT COUNT(*) AS rank_rows_expected_{rank_count} FROM spell_ranks WHERE spell_id BETWEEN 86000 AND 86999;
SELECT spell_trigger,spell_effect,type FROM spell_linked_spell WHERE ABS(spell_trigger) BETWEEN 86000 AND 86999 ORDER BY spell_trigger;
SELECT SpellId,Chance,ProcFlags FROM spell_proc WHERE ABS(SpellId) BETWEEN 86000 AND 86999 ORDER BY SpellId;
SELECT name,security FROM command WHERE name='cultivation';
''', encoding='utf-8')
(version_dir / 'characters.postflight.sql').write_text("SHOW CREATE TABLE character_cultivation_rogue;\nSELECT COUNT(*) AS invalid_paths FROM character_cultivation_rogue WHERE path NOT IN (0,1,2);\n", encoding='utf-8')
(version_dir / 'auth.postflight.sql').write_text("SELECT p.id,p.name,l.id AS player_role FROM rbac_permissions p JOIN rbac_linked_permissions l ON l.linkedId=p.id WHERE p.id=1001 AND l.id=199;\n", encoding='utf-8')

rows = ['# Матрица совместимости', '', 'Статус кандидата: не принят. DBC проверены автоматически; игровые проверки не заменяются проверкой исходников.', '',
        '| Способность | Base chain | Небожитель | Ша | Script | Таланты / символы | DBC | Панели / cooldown | Runtime |',
        '|---|---|---|---|---|---|---|---|---|']
for a in manifest['active_spells'] + manifest['passive_spells']:
    size = len(a['base_spell_chain'])
    chain = lambda first: str(first) if size == 1 else f'{first}–{first+size-1}'
    panel = 'Не проверено отдельно'
    runtime = 'Боевые эффекты не проверены'
    rows.append(f"| {a['logical_name']} | {', '.join(map(str,a['base_spell_chain']))} | {chain(a['celestial_first'])} | {chain(a['sha_first'])} | {a['script_name'] or 'Aura / global hooks'} | Family flags сохранены; модификаторы/символы в бою не проверены | static PASS | {panel} | {runtime} |")
(ROOT / 'docs/compatibility_matrix.md').write_text('\n'.join(rows)+'\n', encoding='utf-8')
checksums = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(version_dir.glob('*.sql'))}
(version_dir / 'manifest.json').write_text(json.dumps({'version':VERSION,'status':'candidate-unaccepted','rollback_scope':'seven-ability extension only; preserve v1 path state', 'files':checksums}, indent=2)+'\n', encoding='utf-8')
print('Generated versioned SQL, rollback and per-ability compatibility matrix')
