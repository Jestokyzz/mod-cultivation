-- mod-cultivation 2.0.0 candidate, schema 6; isolated v3 only.
DELETE FROM `rbac_permissions` WHERE `id`=1001 AND `name`='Command: roguepath';
INSERT INTO `rbac_permissions` (`id`,`name`) VALUES (1001,'Command: cultivation')
ON DUPLICATE KEY UPDATE `name`=VALUES(`name`);
INSERT IGNORE INTO `rbac_linked_permissions` (`id`,`linkedId`) VALUES (199,1001);
