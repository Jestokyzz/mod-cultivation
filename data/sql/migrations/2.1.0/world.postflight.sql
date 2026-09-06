-- Target WORLD; require four rows and zero vendor goods.
SELECT c.guid,t.name,t.subname,t.npcflag,t.ScriptName,m.CreatureDisplayID FROM creature c JOIN creature_template t ON c.id=t.entry JOIN creature_template_model m ON m.CreatureID=t.entry WHERE c.guid BETWEEN 900701 AND 900704 ORDER BY c.guid;
SELECT COUNT(*) AS require_zero FROM npc_vendor WHERE entry BETWEEN 900701 AND 900704;
