-- Roll back only the naming change; permission id and links are preserved.
UPDATE `rbac_permissions` SET `name`='Command: roguepath'
WHERE `id`=1001 AND `name`='Command: cultivation';
