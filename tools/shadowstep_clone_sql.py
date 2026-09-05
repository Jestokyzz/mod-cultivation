"""Fresh SQL tail: deterministic parity with the existing schema-6 migration."""
SQL = """
-- Shadowstep clone used by the Celestial seven-ability extension.
START TRANSACTION;
DELETE FROM `creature_template_model` WHERE `CreatureID`=900406;
DELETE FROM `creature_template` WHERE `entry`=900406;
CREATE TEMPORARY TABLE `cultivation_rogue_shadowstep_clone_template` LIKE `creature_template`;
INSERT INTO `cultivation_rogue_shadowstep_clone_template`
SELECT * FROM `creature_template` WHERE `entry`=38;
UPDATE `cultivation_rogue_shadowstep_clone_template`
SET `entry`=900406, `name`='Celestial Shadowstep Clone', `subname`=NULL,
    `minlevel`=80, `maxlevel`=80, `faction`=35, `npcflag`=0, `speed_walk`=1, `speed_run`=10,
    `DamageModifier`=1, `BaseAttackTime`=1000, `RangeAttackTime`=1000, `unit_flags`=33554432,
    `type_flags`=0, `lootid`=0, `pickpocketloot`=0, `skinloot`=0, `mingold`=0, `maxgold`=0,
    `AIName`='', `MovementType`=0, `HealthModifier`=0.0001, `ManaModifier`=0, `ArmorModifier`=0,
    `ExperienceModifier`=0, `RegenHealth`=0, `flags_extra`=17170528,
    `ScriptName`='npc_cultivation_rogue_shadowstep_clone', `VerifiedBuild`=12340;
INSERT INTO `creature_template` SELECT * FROM `cultivation_rogue_shadowstep_clone_template`;
DROP TEMPORARY TABLE `cultivation_rogue_shadowstep_clone_template`;
INSERT INTO `creature_template_model`
    (`CreatureID`,`Idx`,`CreatureDisplayID`,`DisplayScale`,`Probability`,`VerifiedBuild`)
SELECT 900406,`Idx`,`CreatureDisplayID`,`DisplayScale`,`Probability`,`VerifiedBuild`
FROM `creature_template_model` WHERE `CreatureID`=38;
COMMIT;
"""
