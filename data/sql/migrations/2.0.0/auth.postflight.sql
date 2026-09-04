-- mod-cultivation 2.0.0 candidate, schema 6; isolated v3 only.
SELECT IF(COUNT(*)=1,1,0) AS cultivation_rbac_ok
FROM rbac_permissions WHERE id=1001 AND name='Command: cultivation';
SELECT IF(COUNT(*)>=1,1,0) AS player_link_ok
FROM rbac_linked_permissions WHERE id=199 AND linkedId=1001;
