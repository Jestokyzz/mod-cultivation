CREATE TABLE IF NOT EXISTS `character_cultivation_rogue` (
  `guid` INT UNSIGNED NOT NULL,
  `path` TINYINT UNSIGNED NOT NULL DEFAULT 0,
  `schema_version` SMALLINT UNSIGNED NOT NULL DEFAULT 6,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`guid`),
  CONSTRAINT `chk_character_cultivation_rogue_path` CHECK (`path` IN (0, 1, 2))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `character_cultivation_rogue_suppressed_action` (
  `guid` INT UNSIGNED NOT NULL,
  `spec` TINYINT UNSIGNED NOT NULL,
  `button` TINYINT UNSIGNED NOT NULL,
  `base_spell` INT UNSIGNED NOT NULL,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`guid`, `spec`, `button`),
  KEY `idx_cultivation_rogue_suppressed_base` (`guid`, `spec`, `base_spell`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
