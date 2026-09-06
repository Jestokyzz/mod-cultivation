-- Target WORLD; stop server first. Only fresh installation on previously empty IDs.
-- For an upgrade with prior rows, restore verified scoped backup instead.
START TRANSACTION;
DELETE FROM creature WHERE guid BETWEEN 900701 AND 900704 AND id=guid;
DELETE FROM creature_template_model WHERE CreatureID BETWEEN 900701 AND 900704;
DELETE FROM creature_model_info WHERE DisplayID BETWEEN 60001 AND 60004;
DELETE FROM creature_template WHERE entry BETWEEN 900701 AND 900704;
COMMIT;
