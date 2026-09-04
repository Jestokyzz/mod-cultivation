-- mod-cultivation 2.0.0 candidate, schema 6; isolated v3 only.
DELIMITER $$
DROP PROCEDURE IF EXISTS cultivation_schema6_characters_up$$
CREATE PROCEDURE cultivation_schema6_characters_up()
BEGIN
 IF EXISTS (
  SELECT 1 FROM information_schema.tables
  WHERE table_schema=DATABASE() AND table_name='character_rogue_path'
 ) THEN
  RENAME TABLE `character_rogue_path` TO `character_cultivation_rogue`;
 END IF;
 IF EXISTS (
  SELECT 1 FROM information_schema.tables
  WHERE table_schema=DATABASE() AND table_name='character_rogue_path_suppressed_action'
 ) THEN
  RENAME TABLE `character_rogue_path_suppressed_action` TO `character_cultivation_rogue_suppressed_action`;
 END IF;
 IF EXISTS (
  SELECT 1 FROM information_schema.statistics
  WHERE table_schema=DATABASE() AND table_name='character_cultivation_rogue_suppressed_action'
    AND index_name='idx_rogue_path_suppressed_base'
 ) THEN
  ALTER TABLE `character_cultivation_rogue_suppressed_action`
    RENAME INDEX `idx_rogue_path_suppressed_base` TO `idx_cultivation_rogue_suppressed_base`;
 END IF;
END$$
DELIMITER ;
CALL cultivation_schema6_characters_up();
DROP PROCEDURE cultivation_schema6_characters_up;
UPDATE `character_cultivation_rogue` SET `schema_version`=6 WHERE `schema_version`<6;
