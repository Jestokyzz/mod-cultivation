"""Audit candidate data/source regressions, NOT native/GUI acceptance."""
import json
import re
import unittest
from pathlib import Path
import generate_rogue_paths as g
import dbc_string_integrity as integrity
import native_talent_metadata as metadata

ROOT = Path(__file__).resolve().parents[1]


class AuditFixes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / 'data/cultivation_rogue_spell_manifest.json').read_text('utf8'))
        cls.rows, cls.strings = g.load_dbc(ROOT / 'client_patch/staging/DBFilesClient/Spell.dbc', 234)
        cls.spells = {r[0]: r for r in cls.rows}
        cls.abilities = {a['logical_name']: a for a in cls.manifest['active_spells']}
        cls.common = (ROOT / 'src/rogue/RoguePathCommonSpells.cpp').read_text('utf8')

    def test_every_string_and_every_numeric_field(self):
        integrity.validate(self.rows, self.strings)
        server, strings = g.load_dbc(ROOT / 'generated/server/dbc/Spell.dbc', 234)
        integrity.validate(server, strings)
        self.assertEqual(g.semantic_non_string_rows(ROOT / 'client_patch/staging/DBFilesClient/Spell.dbc'),
                         g.semantic_non_string_rows(ROOT / 'generated/server/dbc/Spell.dbc'))
        self.assertEqual(integrity.repair(g, self.rows, self.strings), [])
        broken = list(self.rows[0]); broken[178] = len(self.strings)
        with self.assertRaisesRegex(ValueError, 'Dangling'):
            integrity.validate([broken], self.strings)
        foreign = list(self.spells[85000]); foreign[42] += 1
        with self.assertRaisesRegex(ValueError, 'differs'):
            integrity.repair(g, [foreign], bytearray(self.strings))

    def test_kidney_duration_before_dr_and_both_locales(self):
        a = self.abilities['kidney_shot']
        for rank in range(len(a['base_spell_chain'])):
            row = self.spells[a['sha_first'] + rank]
            self.assertEqual(row[40], 187)
            for field in (170, 178):
                text = re.sub(r'\|cff[0-9a-fA-F]{6}|\|r', '', g.read_string(self.strings, row[field]))
                self.assertNotRegex(text, r'5 (?:приемов|points): 6')
                self.assertRegex(text, r'5 (?:приемов|points): 5')
        self.assertNotIn('duration - 1000', self.common)

    def test_premeditation_single_native_retention(self):
        self.assertEqual(self.spells[86308][40], 32)
        self.assertEqual(self.spells[86108][40], 9)
        self.assertEqual(self.spells[86308][96], 148)
        after_hit = self.common.split('void AfterHitHandler()', 1)[1].split('void AfterCastHandler()', 1)[0]
        self.assertNotIn('logicalName == "premeditation"', after_hit)
        player = (ROOT / 'src/rogue/RoguePathPlayerScript.cpp').read_text('utf8')
        self.assertNotIn('premeditationExpiresAt', player)
        self.assertIn('int32(player->GetComboPoints(target)) - previous', self.common)

    def test_hemorrhage_visible_personal_charge_data(self):
        a = self.abilities['hemorrhage']
        for rank, stock in enumerate(a['base_spell_chain']):
            for path, charges, multiplier in (('celestial', 20, 1), ('sha', 5, 3)):
                row = self.spells[a[path + '_first'] + rank]
                self.assertEqual(row[71 + 2], 6)
                self.assertEqual(row[95 + 2], 4)
                self.assertTrue(row[4] & 0x04000000)
                self.assertFalse(row[4] & 0x80)
                self.assertEqual(row[40], 3)
                self.assertEqual(row[34:37], [680, 100, charges])
                self.assertEqual(row[82] + 1, (self.spells[stock][82] + 1) * multiplier)
                for field in (170, 178):
                    self.assertIn('60', g.read_string(self.strings, row[field]))
        self.assertNotIn('--state.hemorrhageCharges', self.common)
        self.assertIn('RegisterSpellAndAuraScriptPair(spell_cultivation_rogue_active,', self.common)

    def test_shadowstep_semantic_helper_roles(self):
        self.assertEqual(self.spells[44373][95], 108)
        self.assertEqual(self.spells[44373][110], 2)  # SPELLMOD_THREAT
        self.assertEqual((self.spells[44373][80] + 1) & 0xFFFFFFFF, (-50) & 0xFFFFFFFF)
        self.assertIn(108, self.spells[36563][95:98])
        self.assertTrue('player->RemoveAurasDueToSpell(36563);' in self.common)
        self.assertFalse('player->RemoveAurasDueToSpell(44373);' in self.common)
        for sid in (86105, 86305):
            self.assertEqual(self.spells[sid][97], 31)
            self.assertEqual(self.spells[sid][82], 69)

    def test_aura_registration_filters_before_load(self):
        aura = self.common.split('class spell_cultivation_rogue_active_aura', 1)[1].split('class spell_cultivation_rogue_celestial_fan', 1)[0]
        register = aura.split('void Register() override', 1)[1]
        self.assertIn('FindVariant(m_scriptSpellId)', register)
        self.assertIn('variant->logicalName != "hemorrhage"', register)
        self.assertLess(register.index('return;'), register.index('DoCheckProc +='))
        self.assertNotIn('GetId()', register)

    def test_native_dance_cost_masks_and_cleanup(self):
        for sid, amount, mask in ((86566, -20, 0x204), (86567, -15, 0x500)):
            row = self.spells[sid]
            self.assertEqual(row[95], 107)
            self.assertEqual(row[110], 14)
            self.assertEqual((row[80] + 1) & 0xFFFFFFFF, amount & 0xFFFFFFFF)
            self.assertEqual(row[122:125], [mask, 0, 0])
        self.assertNotIn('bool danceAbility', self.common)
        self.assertIn('removedVariant->logicalName == "shadow_dance"', self.common)

    def test_initial_metadata_uses_final_rows(self):
        data = metadata.metadata(self.manifest, self.rows)
        self.assertEqual(data['3:3:2']['sha'][0]['cost'], 25)
        self.assertEqual(data['3:3:2']['sha'][0]['cooldown'], 15000)
        self.assertEqual(data['3:5:2']['sha'][0]['cooldown'], 390000)
        self.assertTrue(data['3:5:2']['celestial'][0]['passive'])
        self.assertEqual(data['2:11:2']['celestial'][0]['cooldown'], 90000)
        self.assertEqual(data['3:9:2']['celestial'][0]['cooldown'], 30000)
        self.assertTrue(data['3:9:2']['celestial'][0]['preparation'])

    def test_sha_cap_sixty_is_preserved_and_explained(self):
        source = (ROOT / 'src/rogue/RoguePathSevenBalance.h').read_text('utf8')
        self.assertRegex(source, r'Sha.DirectDamageBonusCapPvE", 60,')
        descriptions = self.manifest['technical_presentation']['sha_path_passive']['descriptions']
        self.assertTrue(all('60%' in text for text in descriptions.values()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
