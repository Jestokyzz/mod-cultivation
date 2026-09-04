-- mod-cultivation 2.0.0 candidate, schema 6; isolated v3 only.
DELIMITER $$
DROP PROCEDURE IF EXISTS cultivation_schema6_world_gate$$
CREATE PROCEDURE cultivation_schema6_world_gate()
BEGIN
 IF DATABASE() <> 'cultivation_test_world_v1' THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Wrong database: isolated Cultivation world v3 required';
 END IF;
 IF EXISTS (
  SELECT 1 FROM command
  WHERE name='cultivation' AND help NOT LIKE 'Syntax: .cultivation rogue %'
 ) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Command cultivation is owned by another feature';
 END IF;
 IF EXISTS (
  SELECT 1 FROM creature_template
  WHERE entry=900406 AND ScriptName NOT IN ('npc_rogue_path_shadowstep_clone','npc_cultivation_rogue_shadowstep_clone')
 ) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Creature template 900406 is owned by another feature';
 END IF;
END$$
DELIMITER ;
CALL cultivation_schema6_world_gate();
DROP PROCEDURE cultivation_schema6_world_gate;
SELECT name,security,help FROM command WHERE name IN ('roguepath','cultivation');
