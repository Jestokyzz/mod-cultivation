"""Independent icon-only delta checks against the installed pre-icon schema-3 candidate."""
import json
from pathlib import Path
import unittest

import generate_rogue_paths as g

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path(r'C:\Solo WotLK')
BEFORE = ROOT / 'client_patch/build/v1.3.0-candidate3'
ICON_REVISION = ROOT / 'client_patch/build/v1.3.0-candidate4'
EXPECTED = {'cheap_shot': 6178, 'backstab': 6180, 'blind': 6182, 'safe_fall': 6184,
            'sap': 6186, 'ghostly_strike': 6188, 'shiv': 6190}


class SevenStyledIcons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / 'data/cultivation_rogue_spell_manifest.json').read_text(encoding='utf-8'))

    def test_exact_fourteen_allocations_and_all_rank_assignments(self):
        rows, _ = g.load_dbc(ROOT / 'generated/server/dbc/Spell.dbc', 234)
        spells = {r[0]: r for r in rows}
        abilities = self.manifest['active_spells'] + self.manifest['passive_spells']
        selected = [a for a in abilities if a.get('seven_extension')]
        self.assertEqual({a['logical_name'] for a in selected}, set(EXPECTED))
        for a in selected:
            self.assertEqual(a['icon_source'], 'approved_path_frame')
            for path, offset in (('celestial', 0), ('sha', 1)):
                expected = EXPECTED[a['logical_name']] + offset
                self.assertEqual(a['custom_icon_ids'][path], expected)
                for rank, base in enumerate(a['base_spell_chain']):
                    row = spells[a[path + '_first'] + rank]
                    self.assertEqual(row[133], expected)
                    self.assertEqual(row[134], spells[base][133])

    def test_only_seven_variant_icon_fields_change(self):
        allowed = set()
        for a in self.manifest['active_spells'] + self.manifest['passive_spells']:
            if a['logical_name'] in EXPECTED:
                for path in ('celestial', 'sha'):
                    allowed.update(range(a[path + '_first'], a[path + '_first'] + len(a['base_spell_chain'])))
        # Pin the historical icon-only revision. Later presentation revisions
        # are separately required to preserve its complete numeric/icon fields.
        for old, new in ((BEFORE / 'server/dbc/Spell.dbc', ICON_REVISION / 'server/dbc/Spell.dbc'),
                         (BEFORE / 'staging/DBFilesClient/Spell.dbc', ICON_REVISION / 'staging/DBFilesClient/Spell.dbc')):
            before, bs = g.load_dbc(old, 234)
            after, ns = g.load_dbc(new, 234)
            self.assertEqual(bs, ns, 'No tooltip or other string edits in icon-only task')
            self.assertEqual(len(before), len(after))
            changed = set()
            for b, n in zip(before, after):
                if b != n:
                    self.assertIn(b[0], allowed)
                    self.assertEqual([i for i in range(234) if b[i] != n[i]], [133])
                    changed.add(b[0])
            self.assertEqual(changed, allowed)

    def test_other_dbc_and_old_icon_records_unchanged(self):
        old, os = g.load_dbc(BEFORE / 'server/dbc/SpellIcon.dbc', 2)
        new, ns = g.load_dbc(ROOT / 'generated/server/dbc/SpellIcon.dbc', 2)
        before = {r[0]: g.read_string(os, r[1]) for r in old}
        after = {r[0]: g.read_string(ns, r[1]) for r in new}
        self.assertEqual(set(after) - set(before), set(range(6178, 6197)))
        self.assertEqual(after[6192], 'Interface\\Icons\\ability_rogue_surpriseattack2_celestial')
        self.assertEqual(after[6193], 'Interface\\Icons\\ability_rogue_surpriseattack2_sha')
        self.assertEqual(after[6194], 'Interface\\Icons\\ability_deathknight_hemorrhagicfever')
        self.assertEqual(after[6195], 'Interface\\Icons\\sha_ability_rogue_bloodyeye_nightmare')
        self.assertEqual(after[6196], 'Interface\\Icons\\ability_rogue_surpriseattack2')
        for icon, path in before.items():
            self.assertEqual(after[icon], path)

    def test_content_lock_and_exact_prior_style(self):
        folder = PROJECT / 'artifacts/rogue_pw_icons/content_locked_seven_v1/reports'
        report = json.loads((folder / 'generation_manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(len(report['files']), 14)
        self.assertEqual(report['unchanged_previous_assets'], 78)
        self.assertEqual(len(report['style_verification']), 4)
        self.assertTrue(all(r['byte_identical'] for r in report['style_verification']))
        for row in report['files']:
            self.assertEqual(g.sha256(PROJECT / row['output']).upper(), row['sha256'])
        qa = json.loads((folder / 'qa_report.json').read_text(encoding='utf-8'))
        for slug in EXPECTED:
            for path in ('sage', 'demon'):
                self.assertEqual(qa[slug][path]['content_lock']['status'], 'CONTENT_LOCK_PASS')
                self.assertEqual(qa[slug][path]['filter_only']['status'], 'FILTER_ONLY_PASS')

    def test_user_supplied_stealth_mastery_icon_has_both_path_versions(self):
        folder = PROJECT / 'artifacts/rogue_pw_icons/content_locked_stealth_mastery_v1/reports'
        report = json.loads((folder / 'generation_manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(len(report['files']), 2)
        self.assertEqual({r['profile'] for r in report['files']}, {'sage', 'demon'})
        qa = json.loads((folder / 'qa_report.json').read_text(encoding='utf-8'))['stealth_mastery']
        for profile in ('sage', 'demon'):
            self.assertEqual(qa[profile]['content_lock']['status'], 'CONTENT_LOCK_PASS')
            self.assertEqual(qa[profile]['filter_only']['status'], 'FILTER_ONLY_PASS')


if __name__ == '__main__':
    unittest.main()
