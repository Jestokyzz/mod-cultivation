"""Generate the isolated schema-4 SQL migration and its SHA-256 manifest."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/sql/migrations/1.4.0'
PREVIOUS = ROOT / 'data/sql/migrations/1.3.0'
GATE_WORLD = """DELIMITER $$
DROP PROCEDURE IF EXISTS rogue_paths_schema4_gate$$
CREATE PROCEDURE rogue_paths_schema4_gate()
BEGIN
 IF DATABASE() <> 'rogue_paths_test_world_v3' THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Wrong database: isolated Cultivation / Rogue v3 required';
 END IF;
END$$
DELIMITER ;
CALL rogue_paths_schema4_gate();
DROP PROCEDURE rogue_paths_schema4_gate;
"""
GATE_CHAR = """DELIMITER $$
DROP PROCEDURE IF EXISTS rogue_paths_schema4_gate$$
CREATE PROCEDURE rogue_paths_schema4_gate()
BEGIN
 IF DATABASE() <> 'rogue_paths_test_characters_v3' THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Wrong database: isolated Cultivation / Rogue v3 required';
 END IF;
 IF NOT ((SELECT COUNT(*) FROM characters WHERE online<>0)=0) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Stop isolated world before schema-4 migration';
 END IF;
END$$
DELIMITER ;
CALL rogue_paths_schema4_gate();
DROP PROCEDURE rogue_paths_schema4_gate;
"""


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, body):
    (OUT / name).write_text('-- mod-cultivation 1.4.0 candidate, schema 4; isolated v3 only.\n' + body, encoding='utf-8')


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for database in ('auth',):
        for phase in ('preflight', 'up', 'postflight', 'rollback'):
            write(f'{database}.{phase}.sql', '-- No auth schema changes.\nSELECT DATABASE();\n')
    write('characters.preflight.sql', GATE_CHAR + "SELECT schema_version FROM character_cultivation_rogue GROUP BY schema_version;\n")
    write('characters.up.sql', GATE_CHAR + "START TRANSACTION;\nUPDATE character_cultivation_rogue SET schema_version=4 WHERE schema_version<4;\nCOMMIT;\n")
    write('characters.postflight.sql', GATE_CHAR + "SELECT IF(COUNT(*)=0,1,0) AS schema4_ok FROM character_cultivation_rogue WHERE schema_version<>4;\n")
    write('characters.rollback.sql', GATE_CHAR + "START TRANSACTION;\nUPDATE character_cultivation_rogue SET schema_version=3 WHERE schema_version=4;\nCOMMIT;\n")
    clone = """
START TRANSACTION;
DELETE FROM creature_template_model WHERE CreatureID=900406;
DELETE FROM creature_template WHERE entry=900406;
CREATE TEMPORARY TABLE rogue_path_clone_template LIKE creature_template;
INSERT INTO rogue_path_clone_template SELECT * FROM creature_template WHERE entry=38;
UPDATE rogue_path_clone_template SET entry=900406, name='Celestial Shadowstep Clone', subname=NULL,
 minlevel=80, maxlevel=80, faction=35, npcflag=0, speed_walk=1, speed_run=10,
 DamageModifier=1, BaseAttackTime=1000, RangeAttackTime=1000, unit_flags=33554432,
 type_flags=0, lootid=0, pickpocketloot=0, skinloot=0, mingold=0, maxgold=0,
 AIName='', MovementType=0, HealthModifier=0.0001, ManaModifier=0, ArmorModifier=0,
 ExperienceModifier=0, RegenHealth=0, flags_extra=17170528,
 ScriptName='npc_rogue_path_shadowstep_clone', VerifiedBuild=12340;
INSERT INTO creature_template SELECT * FROM rogue_path_clone_template;
DROP TEMPORARY TABLE rogue_path_clone_template;
INSERT INTO creature_template_model (CreatureID,Idx,CreatureDisplayID,DisplayScale,Probability,VerifiedBuild)
 SELECT 900406,Idx,CreatureDisplayID,DisplayScale,Probability,VerifiedBuild
 FROM creature_template_model WHERE CreatureID=38;
COMMIT;
"""
    generated = (ROOT / 'data/sql/world/base/cultivation_rogue_spells.sql').read_text(encoding='utf-8')
    write('world.preflight.sql', GATE_WORLD + "SELECT IF(COUNT(*)=0,1,0) AS id_owned FROM creature_template WHERE entry=900406 AND ScriptName<>'npc_rogue_path_shadowstep_clone';\n")
    write('world.up.sql', GATE_WORLD + generated + clone)
    write('world.postflight.sql', GATE_WORLD + "SELECT IF(COUNT(*)=1,1,0) AS clone_ok FROM creature_template WHERE entry=900406 AND ScriptName='npc_rogue_path_shadowstep_clone';\n")
    rollback = (PREVIOUS / 'world.up.sql').read_text(encoding='utf-8')
    write('world.rollback.sql', GATE_WORLD + "DELETE FROM creature_template_model WHERE CreatureID=900406;\nDELETE FROM creature_template WHERE entry=900406;\n" + rollback)
    files = {p.name: digest(p) for p in sorted(OUT.glob('*.sql'))}
    manifest = {'version': '1.4.0', 'schema_version': 4, 'status': 'candidate-unaccepted',
                'database_scope': 'rogue_paths_test_*_v3 only',
                'source_manifest_sha256': digest(ROOT / 'data/cultivation_rogue_spell_manifest.json'),
                'creature_template_id': 900406, 'files': files}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('PASS schema-4 migration:', OUT)


if __name__ == '__main__':
    main()
