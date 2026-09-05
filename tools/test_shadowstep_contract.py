"""Fresh-state Shadowstep contract; no learned cache or post-cast correction."""
from pathlib import Path
import unittest
import generate_rogue_paths as g

ROOT = Path(__file__).resolve().parents[1]


class ShadowstepContract(unittest.TestCase):
    def test_both_paths_have_native_30_seconds(self):
        for relative in ('generated/server/dbc/Spell.dbc', 'client_patch/staging/DBFilesClient/Spell.dbc'):
            rows, _ = g.load_dbc(ROOT / relative, 234)
            spells = {row[0]: row for row in rows}
            for spell_id in (86105, 86305):
                with self.subTest(file=relative, spell=spell_id):
                    self.assertEqual(spells[spell_id][29], 30000)
                    self.assertIn(spells[spell_id][30], (0, 30000))

    def test_step_does_not_remove_stealth_via_speed_aura(self):
        text = (ROOT / 'src/rogue/RoguePathCommonSpells.cpp').read_text(encoding='utf-8')
        self.assertFalse('RemoveAurasByType(SPELL_AURA_MOD_DECREASE_SPEED)' in text)

    def test_self_target_rejected_for_both_paths(self):
        text = (ROOT / 'src/rogue/RoguePathCommonSpells.cpp').read_text(encoding='utf-8')
        start = text.index('void OnSpellCheckCast(')
        end = text.index('variant->logicalName != "hunger_for_blood"', start)
        gate = text[start:end]
        self.assertTrue('target == player' in gate)
        self.assertTrue('variant->logicalName == "shadowstep")' in gate)


if __name__ == '__main__':
    unittest.main(verbosity=2)
