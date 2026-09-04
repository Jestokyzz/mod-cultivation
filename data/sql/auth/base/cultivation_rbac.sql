DELETE FROM `rbac_linked_permissions` WHERE `id` = 199 AND `linkedId` = 1001;
DELETE FROM `rbac_permissions` WHERE `id` = 1001;
INSERT INTO `rbac_permissions` (`id`, `name`) VALUES (1001, 'Command: cultivation');
INSERT INTO `rbac_linked_permissions` (`id`, `linkedId`) VALUES (199, 1001);
