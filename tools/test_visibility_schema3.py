import unittest
import json
from pathlib import Path
from tooltip_stock import bind_stock_fields, compose, validate_variables


class StockTooltipTests(unittest.TestCase):
    def test_repackaging_requires_a_recognized_active_owner(self):
        source = (Path(__file__).resolve().parents[1] / 'tools/package_visibility_candidate.py').read_text(encoding='utf-8')
        self.assertIn('assert recognized_owner', source)
        self.assertIn("owners[virtual] in ([], [str(active_owner)])", source)

    def test_useful_buffs_are_not_reclassified_as_internal_timers(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / 'data/cultivation_rogue_spell_manifest.json').read_text(encoding='utf-8'))
        required = ["sha_feint_discount","sha_hunger_penalty","celestial_adrenaline_max_energy","sha_adrenaline_penalty","sha_cheap_shot_mark","sha_kidney_mark","celestial_hemorrhage_charges","sha_hemorrhage_charges","sha_garrote_window","sha_vanish_window","sha_cold_blood_window","celestial_tricks_boost","sha_tricks_boost","celestial_cold_blood_window","sha_cloak_poison_penetration"]
        for logical in required:
            with self.subTest(logical=logical):
                item = manifest['technical_presentation'][logical]
                self.assertEqual(item['visibility'], 'visible')
                for locale in ('ruRU', 'enUS'):
                    self.assertTrue(item['names'][locale])
                    self.assertGreater(len(item['descriptions'][locale]), 8)

    def test_disabled_passive_group_keeps_stock_aura_source_guard(self):
        source = (Path(__file__).resolve().parents[1] / 'src/rogue/RoguePathSpellService.cpp').read_text(encoding='utf-8')
        self.assertIn('available && suppressOriginal && destination != row.baseSpell', source)
        self.assertIn('destination == row.baseSpell && !player->HasAura(row.baseSpell)', source)

    def test_successful_feint_guard_charges_calculated_cost_source_guard(self):
        source = (Path(__file__).resolve().parents[1] / 'src/rogue/RoguePathCommonSpells.cpp').read_text(encoding='utf-8')
        self.assertIn('snapshot.feintPowerBeforeCast = player->GetPower(POWER_ENERGY)', source)
        self.assertIn('!GetSpell()->IsTriggered() && !player->GetCommandStatus(CHEAT_POWER)', source)
        self.assertIn('player->ModifyPower(POWER_ENERGY, -(snapshot->powerCost - spent))', source)

    def test_modified_dummy_never_supplies_standard_numbers(self):
        self.assertEqual(bind_stock_fields('$s1% for $d; $h; $n', 51701),
                         '$51701s1% for $51701d; $51701h; $51701n')

    def test_cross_spell_duration_unchanged(self):
        self.assertEqual(bind_stock_fields('$45182d $s2', 31230), '$45182d $31230s2')

    def test_dynamic_weapon_and_ap_not_frozen(self):
        self.assertEqual(bind_stock_fields('${$m1+$AP*0.07} $rwb $RWB', 48668),
                         '${$48668m1+$AP*0.07} $rwb $RWB')

    def test_glyph_condition_and_grammar_preserved(self):
        self.assertEqual(bind_stock_fields('$?s56803[$s1][$s2] $lраз:раза;', 53),
                         '$?s56803[$53s1][$53s2] $lраз:раза;')

    def test_variable_assignments_and_scoped_value(self):
        self.assertEqual(bind_stock_fields('$bonus=$?s56807[${$m3*1.4}][${$m3}]', 16511, definitions=True),
                         '$bonus=$?s56807[${$16511m3*1.4}][${$16511m3}]')

    def test_english_plural_is_not_a_spell_field(self):
        self.assertEqual(bind_stock_fields('$s1 combo $lpoint:points;', 1776),
                         '$1776s1 combo $lpoint:points;')

    def test_unknown_tokens_fail_closed(self):
        with self.assertRaises(ValueError):
            bind_stock_fields('$unknown99', 53)

    def test_missing_variable_fails_closed(self):
        with self.assertRaises(ValueError):
            validate_variables('$<bonus>', '$other=1')

    def test_no_manual_rank_or_prefix(self):
        self.assertEqual(compose('Stock', 'Modification.', '7CEBFF'),
                         '|cffFFD200Stock|r |cff7CEBFFModification.|r')
        with self.assertRaises(ValueError):
            compose('Stock', 'Путь Небожителя: Modification.', '7CEBFF')


if __name__ == '__main__':
    unittest.main()
