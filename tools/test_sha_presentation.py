"""Candidate41: fresh native tooltips agree with the requested Sha gameplay."""
import json
from pathlib import Path
import re
import unittest
import generate_rogue_paths as g
import visibility_schema3 as visibility

ROOT = Path(__file__).resolve().parents[1]
BEFORE = ROOT / 'client_patch/build/v1.5.0-candidate37'
STRINGS = {i for start in (136, 153, 170, 187) for i in range(start, start + 16)}


class ShaPresentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = json.loads((ROOT / 'data/cultivation_rogue_spell_manifest.json').read_text(encoding='utf-8'))
        cls.rows, cls.strings = g.load_dbc(ROOT / 'client_patch/staging/DBFilesClient/Spell.dbc', 234)
        cls.by_id = {r[0]: r for r in cls.rows}
        cls.abilities = {e['logical_name']: e for e in cls.m['active_spells'] + cls.m['passive_spells']}

    def text(self, name, rank=0, field=178):
        return g.read_string(self.strings, self.by_id[self.abilities[name]['sha_first'] + rank][field])

    def test_display_uses_mechanic_in_both_locales(self):
        displays = [d for d in self.m['display_passives'] if d['path'] == 'sha' and d['talent_required']]
        self.assertTrue(displays)
        for d in displays:
            for locale in (0, 8):
                actual = g.read_string(self.strings, self.by_id[d['spell_id']][170 + locale])
                expected = g.read_string(self.strings, self.by_id[d['mechanic_spell']][170 + locale])
                expected = visibility.static_passive_text(g, expected, d['base_spell'], self.m, locale == 8)
                self.assertEqual(actual, expected, (d['spell_id'], locale))

    def test_before_first_learn_uses_same_sha_branch(self):
        marker = self.m['technical_spells']['celestial_path_passive']
        server, server_strings = g.load_dbc(ROOT / 'generated/server/dbc/Spell.dbc', 234)
        server_by_id = {r[0]: r for r in server}
        for mapping in self.m['talent_ui']['mappings']:
            a = self.abilities[mapping['logical_name']]
            for stock in mapping['rank_spells']:
                rank = a['base_spell_chain'].index(stock)
                for locale in (0, 8):
                    rows, strings = (server_by_id, server_strings) if locale == 0 else (self.by_id, self.strings)
                    old = g.read_string(strings, rows[stock][170 + locale])
                    sha = g.read_string(strings, rows[a['sha_first'] + rank][170 + locale])
                    self.assertTrue(old.startswith(f'$?s{marker}['))
                    self.assertTrue(old.endswith('][' + sha + ']'))

    def test_removed_contradictions_and_integrated_numbers(self):
        for rank in range(len(self.abilities['evasion']['base_spell_chain'])):
            text = self.text('evasion', rank)
            self.assertIn('|cffD84CFF8 сек.', text)
            self.assertNotIn('Длится 8', text)
            self.assertNotRegex(text, r'\$\d+d')
        self.assertNotIn('против игроков', self.text('shadow_dance'))
        self.assertIn('5 сек.', self.text('shadow_dance'))
        for rank in range(3):
            self.assertNotIn('вероятность критического', self.text('master_poisoner', rank))
            self.assertNotIn('не будет сниматься', self.text('master_poisoner', rank))
        self.assertIn('*1.35}', self.text('ambush'))
        self.assertNotIn('Прямой урон увеличен на 35%', self.text('ambush'))
        self.assertIn('|cffD84CFF5|r', self.text('hemorrhage'))
        self.assertIn('*3}', self.text('hemorrhage'))
        for spell in ('blind', 'gouge'):
            self.assertIn('кроме', self.text(spell))
        self.assertIn('20%', self.text('sinister_strike'))
        self.assertIn('60%', self.text('sinister_strike'))
        self.assertIn('*0.5}', self.text('deadly_throw'))
        self.assertIn('1 клинок раз в секунду в течение 3 сек.', self.text('deadly_throw'))
        self.assertIn('75 ед. энергии', self.text('ambush'))
        self.assertIn('После «Шага сквозь тень» можно атаковать спереди.', self.text('backstab'))
        self.assertNotIn('против игроков', self.text('backstab'))
        self.assertIn('на 10% больше урона из всех источников', self.text('cheap_shot'))
        self.assertIn('кроме ваших эффектов периодического урона', self.text('blind'))
        self.assertNotIn('Первая специальная атака', self.text('blind'))
        self.assertIn('Длина серии приемов увеличивается на 2.', self.text('sap'))
        self.assertNotIn('другого контроля', self.text('sap'))
        for rank in range(5):
            potency = self.text('combat_potency', rank, 170)
            self.assertIn('|cffD84CFF25%', potency)
            self.assertIn('|cffD84CFF10|r', potency)
            self.assertNotIn('$355', potency)
            seal = self.text('seal_fate', rank)
            self.assertIn(f'{(rank + 1) * 20}%', seal)
            self.assertIn('2 сек.', seal)
        self.assertNotIn('Из незаметности', self.text('sap'))
        self.assertIn('25 ед. энергии', self.text('ghostly_strike'))
        self.assertIn('броню цели', self.text('ghostly_strike'))
        self.assertNotIn('стоит на 10 энергии больше', self.text('mutilate'))
        self.assertIn('Наложение первого Смертельного яда', self.text('master_poisoner'))
        self.assertIn('100% на 8 сек.', self.text('overkill'))
        self.assertNotIn('уменьшается на 30%', self.text('overkill'))
        self.assertIn('60 ед. энергии за 2 сек.', self.text('cheat_death'))
        self.assertIn('25%', self.text('cheat_death'))

    def test_aura_never_contains_cast_table_or_old_delta(self):
        for a in self.m['active_spells']:
            for rank in range(len(a['base_spell_chain'])):
                for locale in (0, 8):
                    text = self.text(a['logical_name'], rank, 187 + locale)
                    self.assertEqual(text.count('|cff'), text.count('|r'))
                    self.assertNotRegex(text, r'\n\s*[1-5] ')
                    self.assertNotIn('{rank}', text)
                    self.assertNotIn('{path}', text)
                    self.assertNotRegex(text, r'%(?:s|d|f|u)\b')
        self.assertNotIn('уклонени', self.text('ghostly_strike', field=195))
        self.assertEqual(self.text('envenom', field=195), '')
        self.assertEqual(self.text('kidney_shot', field=195), '|cffFFD200Оглушение.|r')

    def test_celestial_numeric_and_text_fields_unchanged(self):
        for folder, output in (('staging/DBFilesClient', ROOT / 'client_patch/staging/DBFilesClient'),
                               ('server/dbc', ROOT / 'generated/server/dbc')):
            old, ss = g.load_dbc(BEFORE / folder / 'Spell.dbc', 234)
            new, ns = g.load_dbc(output / 'Spell.dbc', 234)
            by_id = {r[0]: r for r in new}
            celestial = {a['celestial_first'] + rank for a in self.abilities.values()
                         for rank in range(len(a['base_spell_chain']))}
            celestial.update(d['spell_id'] for d in self.m['display_passives'] if d['path'] == 'celestial')
            old_by_id = {r[0]: r for r in old}
            for spell_id in celestial:
                row = old_by_id[spell_id]
                actual = by_id[spell_id]
                # ActiveIconID is deliberately normalized to the stock base icon
                # so path-framed spellbook art never leaks onto a buff/debuff.
                ignored = STRINGS | {134} | ({133} if spell_id == 86620 else set())
                self.assertEqual([v for i, v in enumerate(row) if i not in ignored],
                                 [v for i, v in enumerate(actual) if i not in ignored], spell_id)
                self.assertEqual([g.read_string(ss, row[i]) for i in sorted(STRINGS)],
                                 [g.read_string(ns, actual[i]) for i in sorted(STRINGS)], spell_id)

    def test_sinister_has_one_twenty_percent_roll(self):
        text = (ROOT / 'src/rogue/RoguePathCommonSpells.cpp').read_text(encoding='utf-8')
        body = text.split('if (variant->logicalName == "sinister_strike")', 1)[1].split('if (variant->logicalName == "riposte")', 1)[0]
        self.assertEqual(body.count('roll_chance_i(20)'), 1)
        self.assertIn('GetHitDamage() > 0', body)
        self.assertIn('GetHitDamage() * 60 / 100', body)
        self.assertIn('Generated::ShaSinisterExtraAttack', body)
        derived = text.split('uint32 DealDerivedDamage(', 1)[1].split('\nnamespace Cultivation::Rogue', 1)[0]
        self.assertNotIn('roll_chance', derived)
        self.assertNotIn('SpellHitResult', derived)

    def test_native_harness_is_isolated_and_counts_real_damage(self):
        source = (ROOT / 'src/rogue/RoguePathCelestialRegression.cpp').read_text(encoding='utf-8')
        harness = source.split('bool RunShaSinisterRegression(', 1)[1].split('bool RunCelestialResourceRegression(', 1)[0]
        for gate in ('!= 8099', ';rogue_paths_test_characters_v3', 'RPTEST_', 'Cultivation.Rogue.Celestial.TestHarness'):
            self.assertIn(gate, harness)
        self.assertIn('p->CastSpell(enemy, 86274, false)', harness)
        self.assertIn('enemy->GetHealth() == enemy->GetMaxHealth()', harness)
        self.assertIn('result->hits == 2000', harness)
        self.assertIn('result->attempts == result->hits + result->avoided', harness)
        self.assertIn('state.delayedDamage.size() != before', harness)
        self.assertNotIn('roll_chance', harness)
        protocol = (ROOT / 'tools/test_world_protocol.py').read_text(encoding='utf-8')
        self.assertIn('opcode == 0x250', protocol)
        self.assertIn('len(extra) == int(procs)', protocol)
        self.assertIn('len(primary) == int(hits) == 2000', protocol)


if __name__ == '__main__':
    unittest.main()
