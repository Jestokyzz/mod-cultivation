"""Exact static contract for the user-requested Sha balance pass (candidate41)."""
import json
from pathlib import Path
import unittest

import generate_rogue_paths as g


ROOT = Path(__file__).resolve().parents[1]


class ShaCandidate41(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / 'data/cultivation_rogue_spell_manifest.json').read_text(encoding='utf-8'))
        rows, cls.strings = g.load_dbc(ROOT / 'generated/server/dbc/Spell.dbc', 234)
        cls.spells = {row[0]: row for row in rows}
        icon_rows, icon_strings = g.load_dbc(ROOT / 'generated/server/dbc/SpellIcon.dbc', 2)
        cls.icon_paths = {row[0]: g.read_string(icon_strings, row[1]) for row in icon_rows}
        duration_rows, _ = g.load_dbc(Path(r'C:\Solo WotLK\test-server\20260831-rogue-paths-v3\data\dbc\SpellDuration.dbc'), 4)
        cls.durations = {row[0]: row[1] for row in duration_rows}
        cls.abilities = {a['logical_name']: a for a in cls.manifest['active_spells'] + cls.manifest['passive_spells']}

    def sha_rows(self, name):
        ability = self.abilities[name]
        return [self.spells[ability['sha_first'] + rank] for rank in range(len(ability['base_spell_chain']))]

    def test_native_energy_cooldown_and_duration_values(self):
        for row, base in zip(self.sha_rows('backstab'), self.abilities['backstab']['base_spell_chain']):
            self.assertEqual(row[42], self.spells[base][42], 'Backstab must use standard energy')
        for row in self.sha_rows('ambush'):
            self.assertEqual(row[42], 75)
        for row in self.sha_rows('sap'):
            self.assertEqual(row[42], 65)
            self.assertEqual(row[29], 10000)
            self.assertEqual(self.durations[row[40]], 6000)
            self.assertEqual(row[12:14], [0, 0])
        for row in self.sha_rows('blind'):
            self.assertEqual(self.durations[row[40]], 5000)
        for row in self.sha_rows('evasion'):
            self.assertEqual(row[29], 120000)
            self.assertEqual(row[30], 120000)
            self.assertEqual(self.durations[row[40]], 8000)
        for row in self.sha_rows('sprint'):
            self.assertEqual(self.durations[row[40]], 8000)
        for row in self.sha_rows('ghostly_strike'):
            self.assertEqual(row[42], 25)
        self.assertEqual(self.durations[self.sha_rows('adrenaline_rush')[0][40]], 10000)
        self.assertEqual(self.durations[self.sha_rows('shadow_dance')[0][40]], 5000)
        self.assertEqual(self.sha_rows('preparation')[0][29:31], [390000, 390000])
        self.assertEqual(self.durations[self.spells[self.manifest['technical_spells']['sha_adrenaline_penalty']][40]], 4000)
        self.assertEqual(self.durations[self.spells[self.manifest['technical_spells']['sha_overkill_bonus']][40]], 8000)

    def test_expose_armor_is_native_shared_thirty_five_percent(self):
        for row in self.sha_rows('expose_armor'):
            self.assertEqual(row[80], (-36) & 0xFFFFFFFF)

    def test_vanish_energy_is_four_real_periodic_ticks(self):
        row = self.spells[self.manifest['technical_spells']['sha_vanish_energy']]
        self.assertEqual(self.durations[row[40]], 4000)
        self.assertEqual(row[71], 6)
        self.assertEqual(row[80], 9)
        self.assertEqual(row[95], 24)
        self.assertEqual(row[98], 1000)
        self.assertEqual(row[110], 3)

    def test_server_source_contains_new_authoritative_rules_only(self):
        common = (ROOT / 'src/rogue/RoguePathCommonSpells.cpp').read_text(encoding='utf-8')
        seven = (ROOT / 'src/rogue/RoguePathSevenSpells.cpp').read_text(encoding='utf-8')
        assassination = (ROOT / 'src/rogue/RoguePathAssassination.cpp').read_text(encoding='utf-8')
        subtlety = (ROOT / 'src/rogue/RoguePathSubtlety.cpp').read_text(encoding='utf-8')
        self.assertIn('player->CastSpell(player, Generated::ShaVanishEnergy, true)', common)
        self.assertNotIn('player->CastSpell(player, Generated::ShaSprintExhaustion', common)
        self.assertNotIn('Generated::ShaEvasionEnergyIcd)', common)
        self.assertNotIn('Generated::ShaEvasionHaste, true', common)
        self.assertIn('target->HasAura(Generated::ShaCheapShotMark)', common)
        self.assertIn('target->HasAura(Generated::ShaKidneyMark)', common)
        self.assertIn('ModifyIncoming(target, attacker, damage, nullptr)', common)
        self.assertIn('ModifyIncoming(target, attacker, value, spellInfo)', common)
        self.assertIn('ModifyIncoming(target, attacker, damage, spellInfo, false)', common)
        self.assertNotIn('Generated::ShaGougeProtection, true', common)
        self.assertIn('damageSpell->Dispel == DISPEL_POISON', common)
        self.assertIn('(1ULL << MECHANIC_BLEED)', common)
        self.assertIn('if (ownPeriodic || ownPoison)', common)
        self.assertIn('getMSTime() + 1000', common)
        self.assertIn('getMSTime() + 2000', common)
        self.assertNotIn('HasControl(target)', seven)
        self.assertIn('cost += c.shaBackstabCost', seven)
        self.assertIn('bonus += c.shaBackstabPvE', seven)
        self.assertIn('damage = damage * (100 + c.shaBackstabCritPvE) / 100', seven)
        self.assertNotIn('cost += 10;', common.split('if (direct && variant->path', 1)[0])
        self.assertIn('roll_chance_i(20 * rank)', common)
        self.assertIn('getMSTimeDiff(state.shaSealFateEmpoweredAt, now) >= 2000', common)
        self.assertNotIn('target->CastSpell(target, Generated::ShaOverkillPenalty', common)
        self.assertIn('Generated::ShaGhostlyStrikeArmor', seven)
        self.assertIn('Apply(rogue, target, Generated::ShaGhostlyStrikeArmor', seven)
        sap_check = seven.split('if (variant->logicalName == "sap" && variant->path == RoguePath::Sha)', 1)[1].split('void OnCalcMaxDuration', 1)[0]
        self.assertNotIn('HasStealthAura', sap_check)
        self.assertNotIn('SPELL_FAILED_ONLY_STEALTHED', sap_check)
        self.assertIn('IsDeadlyPoison(aura->GetSpellInfo())', assassination)
        self.assertIn('state.cheatEnergyTicks = 2', subtlety)

    def test_standard_active_aura_icons_and_requested_shared_icons(self):
        for ability in self.manifest['active_spells']:
            for path in ('celestial', 'sha'):
                for rank, base in enumerate(ability['base_spell_chain']):
                    row = self.spells[ability[path + '_first'] + rank]
                    self.assertEqual(row[134], self.spells[base][133], (ability['logical_name'], path, rank))
        for logical in ('sha_cheap_shot_mark', 'sha_kidney_mark', 'sha_dismantle_mark'):
            row = self.spells[self.manifest['technical_spells'][logical]]
            self.assertEqual(row[133], 6194)
        for logical in ('sha_path_passive', 'sha_blood_thrill'):
            row = self.spells[self.manifest['technical_spells'][logical]]
            self.assertEqual(row[133], 6195)
        for logical, item in self.manifest['technical_presentation'].items():
            if item['visibility'] == 'hidden' or item.get('preserve_validated_presentation'):
                continue
            row = self.spells[self.manifest['technical_spells'][logical]]
            source = self.spells[item['icon_source_spell']]
            self.assertEqual(row[133], item.get('icon_id', source[133]), logical)
            self.assertEqual(row[134], source[134], logical)

    def test_ghostly_armor_is_a_target_debuff_and_cheat_death_is_over_time(self):
        armor = self.spells[self.manifest['technical_spells']['sha_ghostly_strike_armor']]
        self.assertEqual(armor[95], 101)
        self.assertEqual(armor[86], 6)
        self.assertEqual(armor[110], 1)
        self.assertEqual(self.durations[armor[40]], 6000)
        cheat = self.spells[self.manifest['technical_spells']['sha_cheat_death_damage']]
        self.assertEqual(self.durations[cheat[40]], 2000)
        self.assertEqual(cheat[80], 24)

    def test_tooltips_contain_no_retired_sha_contract(self):
        retired = ('первые 1,5 сек.', '3 клинка за 1 сек.', 'если на нем нет другого контроля',
                   'если на ней нет другого контроля', 'против игроков){/path}',
                   'Первая специальная атака стоит на 20 ед. энергии меньше')
        for name in ('gouge', 'deadly_throw', 'cheap_shot', 'backstab', 'blind', 'sap'):
            for row in self.sha_rows(name):
                text = g.read_string(self.strings, row[178])
                for phrase in retired:
                    self.assertNotIn(phrase, text, name)
                self.assertEqual(text.count('|cff'), text.count('|r'), name)

    def test_stealth_mastery_uses_new_user_icon_ids(self):
        displays = {d['path']: d for d in self.manifest['display_passives'] if d['logical_name'] == 'stealth_mastery'}
        self.assertEqual(displays['celestial']['icon_id'], 6192)
        self.assertEqual(displays['sha']['icon_id'], 6193)
        self.assertEqual(self.spells[displays['celestial']['spell_id']][133], 6192)
        self.assertEqual(self.spells[displays['sha']['spell_id']][133], 6193)

    def test_requested_celestial_technical_aura_names_and_icons(self):
        fatal_item = self.manifest['technical_presentation']['celestial_shiv_protection']
        fatal = self.spells[self.manifest['technical_spells']['celestial_shiv_protection']]
        self.assertEqual(fatal_item['icon_source_spell'], 31226)
        self.assertEqual(fatal[133], 1960)
        self.assertEqual(self.icon_paths[fatal[133]].lower(), 'interface\\icons\\ability_creature_poison_06')

        mastery_item = self.manifest['technical_presentation']['celestial_stealth_mastery']
        mastery = self.spells[self.manifest['technical_spells']['celestial_stealth_mastery']]
        self.assertEqual(mastery_item['icon_id'], 6192)
        self.assertEqual(mastery[133], 6192)
        self.assertNotEqual(mastery[133], 6196)
        self.assertEqual(self.icon_paths[mastery[133]].lower(), 'interface\\icons\\ability_rogue_surpriseattack2_celestial')
        self.assertEqual(g.read_string(self.strings, mastery[144]), 'Мастерство незаметности')
        self.assertEqual(g.read_string(self.strings, mastery[136]), 'Stealth Mastery')


if __name__ == '__main__':
    unittest.main()
