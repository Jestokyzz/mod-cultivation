-- Roll back only the module and command naming change.
DELETE FROM `command` WHERE `name` IN ('cultivation','roguepath');
INSERT INTO `command` (`name`,`security`,`help`) VALUES
('roguepath',0,'Syntax: .roguepath celestial|nebozhitel|небожитель|sha|ша|status|sync|reset');

UPDATE `spell_script_names` SET `ScriptName`='spell_rogue_path_active'
WHERE `ScriptName`='spell_cultivation_rogue_active';
UPDATE `spell_script_names` SET `ScriptName`=REPLACE(`ScriptName`,'spell_cultivation_rogue_','spell_rog_path_')
WHERE `ScriptName` LIKE 'spell_cultivation_rogue_%';
