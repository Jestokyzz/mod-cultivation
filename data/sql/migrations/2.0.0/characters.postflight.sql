-- mod-cultivation 2.0.0 candidate, schema 6; isolated v3 only.
SELECT IF(COUNT(*)=2,1,0) AS cultivation_tables_ok
FROM information_schema.tables
WHERE table_schema=DATABASE()
  AND table_name IN ('character_cultivation_rogue','character_cultivation_rogue_suppressed_action');
SELECT IF(COUNT(*)=0,1,0) AS legacy_tables_absent
FROM information_schema.tables
WHERE table_schema=DATABASE()
  AND table_name IN ('character_rogue_path','character_rogue_path_suppressed_action');
SELECT IF(COUNT(*)=0,1,0) AS schema6_ok
FROM character_cultivation_rogue WHERE schema_version<>6;
