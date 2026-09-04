-- mod-cultivation 2.0.0 candidate, schema 6; isolated v3 only.
DELETE FROM `command` WHERE `name` IN ('roguepath','cultivation');
INSERT INTO `command` (`name`,`security`,`help`) VALUES
('cultivation',0,'Syntax: .cultivation rogue celestial|nebozhitel|небожитель|sha|ша|status|sync|reset');

UPDATE `spell_script_names` SET `ScriptName`='spell_cultivation_rogue_active'
WHERE `ScriptName`='spell_rogue_path_active';
UPDATE `spell_script_names` SET `ScriptName`='spell_cultivation_rogue_blind'
WHERE `ScriptName`='spell_rog_path_blind';
UPDATE `spell_script_names` SET `ScriptName`='spell_cultivation_rogue_celestial_fan'
WHERE `ScriptName`='spell_rog_path_celestial_fan';
UPDATE `spell_script_names` SET `ScriptName`='spell_cultivation_rogue_combat_potency'
WHERE `ScriptName`='spell_rog_path_combat_potency';
UPDATE `spell_script_names` SET `ScriptName`='spell_cultivation_rogue_evasion'
WHERE `ScriptName`='spell_rog_path_evasion';
UPDATE `spell_script_names` SET `ScriptName`='spell_cultivation_rogue_ghostly_dodge'
WHERE `ScriptName`='spell_rog_path_ghostly_dodge';
UPDATE `spell_script_names` SET `ScriptName`='spell_cultivation_rogue_sha_honor'
WHERE `ScriptName`='spell_rog_path_sha_honor';
UPDATE `spell_script_names` SET `ScriptName`='spell_cultivation_rogue_shiv'
WHERE `ScriptName`='spell_rog_path_shiv';
UPDATE `spell_script_names` SET `ScriptName`='spell_cultivation_rogue_shiv_component'
WHERE `ScriptName`='spell_rog_path_shiv_component';
UPDATE `creature_template` SET `ScriptName`='npc_cultivation_rogue_shadowstep_clone'
WHERE `entry`=900406 AND `ScriptName`='npc_rogue_path_shadowstep_clone';
