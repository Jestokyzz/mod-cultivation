-- mod-cultivation 2.0.0 candidate, schema 6; isolated v3 only.
DELIMITER $$
DROP PROCEDURE IF EXISTS cultivation_schema6_auth_gate$$
CREATE PROCEDURE cultivation_schema6_auth_gate()
BEGIN
 IF DATABASE() <> 'cultivation_test_auth_v1' THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Wrong database: isolated Cultivation auth v3 required';
 END IF;
 IF EXISTS (
  SELECT 1 FROM rbac_permissions
  WHERE id=1001 AND name NOT IN ('Command: roguepath', 'Command: cultivation')
 ) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='RBAC 1001 is owned by another feature';
 END IF;
END$$
DELIMITER ;
CALL cultivation_schema6_auth_gate();
DROP PROCEDURE cultivation_schema6_auth_gate;
SELECT id,name FROM rbac_permissions WHERE id=1001;
