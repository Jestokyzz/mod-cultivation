-- Roll back only the schema-6 naming change; character state is preserved.
UPDATE `character_cultivation_rogue` SET `schema_version`=5 WHERE `schema_version`=6;
DELIMITER $$
DROP PROCEDURE IF EXISTS cultivation_schema6_characters_down$$
CREATE PROCEDURE cultivation_schema6_characters_down()
BEGIN
 IF EXISTS (
  SELECT 1 FROM information_schema.statistics
  WHERE table_schema=DATABASE() AND table_name='character_cultivation_rogue_suppressed_action'
    AND index_name='idx_cultivation_rogue_suppressed_base'
 ) THEN
  ALTER TABLE `character_cultivation_rogue_suppressed_action`
    RENAME INDEX `idx_cultivation_rogue_suppressed_base` TO `idx_rogue_path_suppressed_base`;
 END IF;
 IF EXISTS (
  SELECT 1 FROM information_schema.tables
  WHERE table_schema=DATABASE() AND table_name='character_cultivation_rogue'
 ) THEN
  RENAME TABLE `character_cultivation_rogue` TO `character_rogue_path`;
 END IF;
 IF EXISTS (
  SELECT 1 FROM information_schema.tables
  WHERE table_schema=DATABASE() AND table_name='character_cultivation_rogue_suppressed_action'
 ) THEN
  RENAME TABLE `character_cultivation_rogue_suppressed_action` TO `character_rogue_path_suppressed_action`;
 END IF;
END$$
DELIMITER ;
CALL cultivation_schema6_characters_down();
DROP PROCEDURE cultivation_schema6_characters_down;
