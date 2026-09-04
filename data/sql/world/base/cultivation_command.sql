DELETE FROM `command` WHERE `name` IN ('roguepath', 'cultivation');
INSERT INTO `command` (`name`, `security`, `help`) VALUES
('cultivation', 0, 'Syntax: .cultivation rogue celestial|nebozhitel|небожитель|sha|ша|status|sync|reset');
