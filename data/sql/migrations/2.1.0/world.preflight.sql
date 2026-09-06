-- Target WORLD; all new ID ranges must be unused for fresh/v2.0.0 upgrade.
SELECT COUNT(*) AS require_zero FROM creature_template WHERE entry BETWEEN 900701 AND 900704;
SELECT COUNT(*) AS require_zero FROM creature WHERE guid BETWEEN 900701 AND 900704 OR id BETWEEN 900701 AND 900704;
SELECT COUNT(*) AS require_zero FROM creature_model_info WHERE DisplayID BETWEEN 60001 AND 60004;
