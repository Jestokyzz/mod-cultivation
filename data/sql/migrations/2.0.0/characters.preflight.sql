-- mod-cultivation 2.0.0 candidate, schema 6; isolated v3 only.
DELIMITER $$
DROP PROCEDURE IF EXISTS cultivation_schema6_characters_gate$$
CREATE PROCEDURE cultivation_schema6_characters_gate()
BEGIN
 IF DATABASE() <> 'cultivation_test_characters_v1' THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Wrong database: isolated Cultivation characters v3 required';
 END IF;
 IF EXISTS (SELECT 1 FROM characters WHERE online<>0) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Stop isolated world before Cultivation schema-6 migration';
 END IF;
 IF (
  SELECT COUNT(*) FROM information_schema.tables
  WHERE table_schema=DATABASE() AND table_name IN ('character_rogue_path','character_cultivation_rogue')
 ) <> 1 THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Expected exactly one rogue path state table';
 END IF;
 IF (
  SELECT COUNT(*) FROM information_schema.tables
  WHERE table_schema=DATABASE() AND table_name IN ('character_rogue_path_suppressed_action','character_cultivation_rogue_suppressed_action')
 ) <> 1 THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Expected exactly one suppressed-action table';
 END IF;
END$$
DELIMITER ;
CALL cultivation_schema6_characters_gate();
DROP PROCEDURE cultivation_schema6_characters_gate;
