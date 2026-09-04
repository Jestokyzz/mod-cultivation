-- mod-cultivation 2.0.0 candidate, schema 6; isolated v3 only.
SELECT IF(COUNT(*)=1,1,0) AS cultivation_command_ok
FROM command
WHERE name='cultivation' AND security=0 AND help LIKE 'Syntax: .cultivation rogue %';
SELECT IF(COUNT(*)=0,1,0) AS legacy_command_absent FROM command WHERE name='roguepath';
SELECT IF(COUNT(*)=0,1,0) AS legacy_script_names_absent
FROM spell_script_names
WHERE ScriptName='spell_rogue_path_active' OR ScriptName LIKE 'spell_rog_path_%';
SELECT IF(COUNT(*)>0,1,0) AS cultivation_script_names_present
FROM spell_script_names WHERE ScriptName LIKE 'spell_cultivation_rogue_%';
SELECT IF(COUNT(*)=1,1,0) AS cultivation_shadowstep_clone_present
FROM creature_template
WHERE entry=900406 AND ScriptName='npc_cultivation_rogue_shadowstep_clone';
SELECT IF(COUNT(*)>0,1,0) AS cultivation_shadowstep_clone_models_present
FROM creature_template_model WHERE CreatureID=900406;
