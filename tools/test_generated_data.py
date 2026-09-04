"""Offline DBC/source contract tests. These are not runtime acceptance tests."""
import json
import re
import struct
import unittest
from pathlib import Path

import generate_rogue_paths as gen

ROOT = Path(__file__).resolve().parents[1]


class GeneratedDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / 'data/cultivation_rogue_spell_manifest.json').read_text(encoding='utf-8'))
        cls.client_rows, cls.client_strings = gen.load_dbc(ROOT / 'client_patch/staging/DBFilesClient/Spell.dbc', 234)
        cls.server_rows, cls.server_strings = gen.load_dbc(ROOT / 'generated/server/dbc/Spell.dbc', 234)
        cls.client = {r[0]: r for r in cls.client_rows}
        cls.server = {r[0]: r for r in cls.server_rows}
        cls.client_range_rows, _ = gen.load_dbc(ROOT / 'client_patch/staging/DBFilesClient/SpellRange.dbc', 40)
        cls.server_range_rows, _ = gen.load_dbc(ROOT / 'generated/server/dbc/SpellRange.dbc', 40)
        cls.client_ranges = {r[0]: r for r in cls.client_range_rows}
        cls.server_ranges = {r[0]: r for r in cls.server_range_rows}
        cls.native_talent_ranks = {
            spell_id
            for mapping in cls.manifest['talent_ui']['mappings']
            for spell_id in mapping['rank_spells']
        }

    @staticmethod
    def native_talent_branches(text):
        match = re.fullmatch(r'\$\?s86500\[([^\[\]]*)\]\[([^\[\]]*)\]', text, re.S)
        if not match:
            raise AssertionError(f'Invalid native talent conditional: {text!r}')
        return {'celestial': match.group(1), 'sha': match.group(2)}

    def test_unique_ids(self):
        self.assertEqual(len(self.client_rows), len(self.client))
        self.assertEqual(set(self.client), set(self.server))

    def test_variants_never_auto_learn_from_class_skill(self):
        rows, _ = gen.load_dbc(ROOT / 'generated/server/dbc/SkillLineAbility.dbc', 14)
        custom = [r for r in rows if 86000 <= r[2] <= 86999]
        self.assertEqual(len(custom), len(gen.expanded_entries(self.manifest)) * 2 + 2 + len(self.manifest['display_passives']))
        self.assertTrue(all(r[9] == 0 for r in custom), 'Only SpellService may grant variants')

    def test_all_custom_numeric_fields_match(self):
        client = gen.semantic_non_string_rows(ROOT / 'client_patch/staging/DBFilesClient/Spell.dbc')
        server = gen.semantic_non_string_rows(ROOT / 'generated/server/dbc/Spell.dbc')
        for spell_id in self.client:
            self.assertEqual(client[spell_id], server[spell_id], spell_id)

    def test_display_passive_runtime_icon_contract_matches_dbc(self):
        header = (ROOT / 'src/rogue/generated/RoguePathGeneratedSpells.h').read_text(encoding='utf-8')
        for item in self.manifest['display_passives']:
            icon_id = item.get('icon_id') or gen.path_icon_id(self.manifest, item['logical_name'], item['path'])
            self.assertEqual(self.server[item['spell_id']][133], icon_id, item['spell_id'])
            self.assertIn(f'"{item["logical_name"]}", {item["icon_source_spell"]}, {icon_id}}}', header)

    def test_rank_names_icons_and_families(self):
        for ability in self.manifest['active_spells'] + self.manifest['passive_spells']:
            for rank, base_id in enumerate(ability['base_spell_chain']):
                for path in ('celestial', 'sha'):
                    row = self.client[ability[f'{path}_first'] + rank]
                    base = self.client[base_id]
                    stock_feint = ability['logical_name'] == 'feint' and path == 'celestial'
                    stock_icon = ability['icon_source'] == 'stock_base_rank' or stock_feint
                    self.assertEqual(row[133], base[133] if stock_icon else gen.path_icon_id(self.manifest, ability['logical_name'], path))
                    if stock_icon:
                        self.assertEqual(row[133], base[133])
                    else:
                        self.assertNotEqual(row[133], base[133])
                    expected_family = list(base[208:212])
                    if path == 'celestial' and ability['logical_name'] in ('dismantle', 'kick', 'blade_flurry'):
                        expected_family[3] |= gen.PREPARATION_GLYPH_FAMILY_MARKER
                    self.assertEqual(row[208:212], expected_family)
                    self.assertEqual(row[38:40], base[38:40], ability['logical_name'])
                    expected_name = gen.celestial.NAMES.get(ability['logical_name']) if path == 'celestial' else None
                    self.assertEqual(gen.read_string(self.client_strings, row[144]), expected_name or gen.read_string(self.client_strings, base[144]))
                    description = gen.read_string(self.client_strings, row[178])
                    raw_source_text = gen.read_string(self.client_strings, base[178])
                    exact = ability.get('full_descriptions', {}).get('ruRU', {}).get(path)
                    addition = ability['descriptions']['ruRU'][path].replace('{rank}', str(rank + 1))
                    entry = dict(ability, rank=rank + 1)
                    if base_id in self.native_talent_ranks:
                        self.assertEqual(
                            description, self.native_talent_branches(raw_source_text)[path])
                    else:
                        self.assertEqual(description, gen.generated_path_tooltip(
                            entry, raw_source_text, addition, path, 'ruRU', self.manifest, base_spell=base_id))
                    if exact is None or '{path}' in exact:
                        self.assertIn('|cff' + self.manifest['path_icons'][path + '_color'], description)
                    self.assertTrue(description.startswith((
                        '|cffFFD200', '|cff' + self.manifest['path_icons'][path + '_color'])))
                    self.assertEqual(description.count('|cff'), description.count('|r'))
                    self.assertEqual(gen.read_string(self.client_strings, row[161]), 'Небожитель' if path == 'celestial' else 'Ша')
                    self.assertNotIn('Путь ', description)
                    self.assertTrue(description.endswith('|r'))
                    self.assertNotIn('TODO', description)

    def test_tooltip_preserves_original_in_both_locales(self):
        for data, strings, locale, russian in ((self.client, self.client_strings, 8, True),
                                               (self.server, self.server_strings, 0, False)):
            for ability in self.manifest['active_spells'] + self.manifest['passive_spells']:
                for rank, base_id in enumerate(ability['base_spell_chain']):
                    for path in ('celestial', 'sha'):
                        for field in (gen.SPELL_DESCRIPTION, gen.SPELL_TOOLTIP):
                            if ability in self.manifest['active_spells'] and field == gen.SPELL_TOOLTIP:
                                # Dedicated aura source, not the ability's full description.
                                import celestial_aura_tooltips
                                import sha_aura_tooltips
                                aura = celestial_aura_tooltips if path == 'celestial' else sha_aura_tooltips
                                actual = data[ability[path + '_first'] + rank]
                                source = gen.read_string(strings, data[base_id][field + locale])
                                template = aura.TEXT.get(ability['logical_name'])
                                expected = template[0 if russian else 1] if template else source
                                expected = gen.tooltip_stock.exact(gen.tooltip_stock.bind_stock_fields(expected, actual[0]),
                                    self.manifest['path_icons'][path + '_color']) if expected else ''
                                self.assertEqual(gen.read_string(strings, actual[field + locale]), expected)
                                continue
                            raw_base_text = gen.read_string(strings, data[base_id][field + locale])
                            base_text = gen.tooltip_stock.bind_stock_fields(raw_base_text, base_id)
                            text = gen.read_string(strings, data[ability[path + '_first'] + rank][field + locale])
                            if base_id in self.native_talent_ranks and field == gen.SPELL_DESCRIPTION:
                                self.assertEqual(text, self.native_talent_branches(raw_base_text)[path])
                                self.assertEqual(text.count('|cff'), text.count('|r'))
                                continue
                            exact = ability.get('full_descriptions', {}).get('ruRU' if russian else 'enUS', {}).get(path)
                            if not base_text and exact is None:
                                if text:
                                    self.assertEqual(text, gen.read_string(
                                        strings, data[ability[path + '_first'] + rank][gen.SPELL_DESCRIPTION + locale]))
                            else:
                                addition = ability['descriptions']['ruRU' if russian else 'enUS'][path].replace(
                                    '{rank}', str(rank + 1))
                                entry = dict(ability, rank=rank + 1)
                                self.assertEqual(text, gen.generated_path_tooltip(
                                    entry, raw_base_text if field == gen.SPELL_DESCRIPTION else base_text,
                                    addition, path, 'ruRU' if russian else 'enUS',
                                    self.manifest, base_spell=base_id if field == gen.SPELL_DESCRIPTION else None))
                                self.assertEqual(text.count('|cff'), text.count('|r'))
                            self.assertNotIn('][$?', text)

    def test_native_talent_rank_descriptions_are_path_conditional(self):
        abilities = {entry['logical_name']: entry
                     for entry in self.manifest['active_spells'] + self.manifest['passive_spells']}
        expected_ids = []
        for data, strings, locale in ((self.client, self.client_strings, 8),
                                      (self.server, self.server_strings, 0)):
            seen = []
            for mapping in self.manifest['talent_ui']['mappings']:
                ability = abilities[mapping['logical_name']]
                self.assertTrue(set(mapping['rank_spells']) <= set(ability['base_spell_chain']))
                for stock_id in mapping['rank_spells']:
                    ability_rank = ability['base_spell_chain'].index(stock_id)
                    raw = gen.read_string(strings, data[stock_id][gen.SPELL_DESCRIPTION + locale])
                    branches = self.native_talent_branches(raw)
                    self.assertEqual(
                        branches['celestial'],
                        gen.read_string(strings, data[ability['celestial_first'] + ability_rank][gen.SPELL_DESCRIPTION + locale]))
                    self.assertEqual(
                        branches['sha'],
                        gen.read_string(strings, data[ability['sha_first'] + ability_rank][gen.SPELL_DESCRIPTION + locale]))
                    self.assertIn('|cff' + self.manifest['path_icons']['celestial_color'], branches['celestial'])
                    self.assertIn('|cff' + self.manifest['path_icons']['sha_color'], branches['sha'])
                    self.assertNotIn('{rank}', raw)
                    self.assertNotIn('{rank}', branches['celestial'])
                    self.assertNotIn('{rank}', branches['sha'])
                    if locale == 8 and mapping['logical_name'] == 'combat_potency':
                        self.assertIn(f'накопить {ability_rank + 1} ед. энергии', branches['celestial'])
                    self.assertNotIn('$?s86501', raw)
                    seen.append(stock_id)
            if not expected_ids:
                expected_ids = seen
            self.assertEqual(seen, expected_ids)
            self.assertEqual(len(seen), len(set(seen)))

    def test_retired_mobility_does_not_leak_into_paths(self):
        for data in (self.client, self.server):
            self.assertFalse(set(range(80901, 80917)) & data.keys())
            for rank, base in enumerate((2983, 8696, 11305)):
                self.assertEqual((data[base][30], data[base][40], data[base][42]), (180000, 8, 0))
                for first in (86004, 86204):
                    row = data[first + rank]
                    self.assertEqual((row[30], row[42], row[97]), (180000, 0, 0))
            self.assertEqual(data[86105][86], 25, 'Friendly targeting is an explicit Celestial rule')
            self.assertEqual(data[86305][86], 6)

    def test_range_and_radius_are_not_level_or_dice(self):
        self.assertEqual(self.client[86045][46], 5)
        self.assertEqual((self.client[86305][29], self.client[86305][42], self.client[86305][46]), (15000, 20, 35))
        for spell_id, base in ((86048, 51723), (86570, 52874)):
            self.assertEqual(self.client[spell_id][92], self.manifest['celestial_revision']['radius_id'])
            self.assertEqual(self.client[spell_id][74], self.client[base][74])

    def test_technical_aura_semantics(self):
        for name, spell_id in self.manifest['technical_spells'].items():
            if spell_id in self.manifest['celestial_revision']['retired_auras']:
                self.assertEqual(self.client[spell_id][95:98], [4,0,0])
                self.assertTrue(self.client[spell_id][4] & 0x80)
                continue
            if name.startswith('celestial_damage_suppression_') or name == 'celestial_sprint_immunity':
                continue # schema-2 full effect validation below
            if name in gen.seven.WEAPON_COMPONENTS:
                row = self.client[spell_id]
                self.assertEqual(row[71:74], [0, 121, 0], name)
                self.assertTrue(row[7] & 0x10000)
                self.assertTrue(row[8] & 0x800000)
                continue
            if name in gen.DERIVED_DAMAGE_SPELLS:
                row = self.client[spell_id]
                self.assertEqual(row[71:74], [2, 0, 0], name)
                self.assertEqual(row[86], 6, name)
                self.assertEqual(row[95:98], [0, 0, 0], name)
                self.assertTrue(row[7] & 0x10000, name)
                self.assertTrue(row[8] & 0x800000, name)
                self.assertEqual(row[225], 8 if name == 'sha_envenom_detonation' else 1, name)
                continue
            if name.endswith('fan_offhand'):
                self.assertEqual(self.client[spell_id][71:74], self.client[52874][71:74])
                continue
            row = self.client[spell_id]
            aura = row[95]
            self.assertEqual(row[74], 1, name)
            self.assertEqual(row[225], 1, name)
            amount = gen.TECH_EFFECTS.get(name, (4, 1, 0))[1]
            calculated = (row[80] if row[80] < 2**31 else row[80] - 2**32) + 1
            self.assertEqual(calculated, amount, name)
            expected_target = 6 if name in gen.TARGETED_TECHNICAL else 21 if name.endswith('tricks_boost') else 1
            self.assertEqual(row[86], expected_target, name)
            if aura in (79, 87, 229):
                self.assertEqual(row[110], 127, name)
            if aura in (24, 35, 110):
                self.assertEqual(row[110], 3, name)
        for spell_id in (86539, 86540, 86541):
            self.assertEqual(self.client[spell_id][95], 280)
        for spell_id in (86509, 86523):
            self.assertEqual(self.client[spell_id][49], 3)

    def test_skill_line_coverage_and_equality(self):
        client_path = ROOT / 'client_patch/staging/DBFilesClient/SkillLineAbility.dbc'
        server_path = ROOT / 'generated/server/dbc/SkillLineAbility.dbc'
        self.assertEqual(client_path.read_bytes(), server_path.read_bytes())
        rows, _ = gen.load_dbc(client_path, gen.SKILL_LINE_ABILITY_FIELDS)
        ids = {r[2] for r in rows}
        for ability in self.manifest['active_spells'] + self.manifest['passive_spells']:
            for rank in range(len(ability['base_spell_chain'])):
                for path in ('celestial', 'sha'):
                    self.assertIn(ability[f'{path}_first'] + rank, ids)
        by_spell = {row[2]: row for row in rows}
        self.assertEqual(by_spell[86621][1], 39, 'Visible Preparation passive belongs to Subtlety')

    def test_ghostly_strike_dodge_aura_is_visible(self):
        row = self.client[86584]
        self.assertFalse(row[4] & 0x80)
        self.assertEqual(row[95], 49)
        self.assertEqual(row[80] + 1, 30)
        self.assertEqual(gen.read_string(self.client_strings, row[144]), 'Призрачный удар')
        self.assertEqual(gen.read_string(self.client_strings, row[178]),
                         'Вероятность уклонения повышена на 30%. Первое успешное уклонение восстанавливает 20 ед. энергии.')

    def test_server_english_names(self):
        for spell_id in (1752, 1784, 1329, 51723, 86000, 86200, 86051, 86251):
            self.assertTrue(gen.read_string(self.server_strings, self.server[spell_id][136]), spell_id)

    def test_linked_offhand_and_proc_metadata(self):
        sql = (ROOT / 'data/sql/world/base/cultivation_rogue_spells.sql').read_text(encoding='utf-8')
        self.assertIn('`spell_effect`=86570 WHERE `spell_trigger`=86048', sql)
        self.assertIn('`spell_effect`=86571 WHERE `spell_trigger`=86248', sql)
        self.assertIn('FROM `spell_proc` p JOIN', sql)
        self.assertIn('LEFT JOIN `rogue_path_effect_map` e', sql)
        self.assertNotIn('LEFT JOIN `rogue_path_install_map` e', sql)
        self.assertIn('SIGN(p.`SpellId`)*CAST(m.`celestial_id` AS SIGNED)', sql)
        self.assertIn('`Chance`=100 WHERE `SpellId` IN (-86409, -86429)', sql)

    def test_cloak_poison_resistance_scope(self):
        aura = self.client[86574]
        self.assertEqual(aura[95], 270)
        self.assertEqual(aura[80] + 1, 100)
        self.assertEqual(aura[110], 8)
        mask = aura[122:125]
        for spell_id in (57970, 57965, 57975, 3409, 5760, 57981, 57993, 86573):
            spell = self.client[spell_id]
            self.assertEqual(spell[2], 4)
            self.assertTrue(any(a & b for a, b in zip(mask, spell[209:212])), spell_id)
        for spell_id in (1752, 48638, 48668, 51723, 31224, 1329):
            self.assertFalse(any(a & b for a, b in zip(mask, self.client[spell_id][209:212])), spell_id)

    def test_envenom_effect_order_and_sha_honor_proc(self):
        for rank, base in enumerate((32645, 32684, 57992, 57993)):
            for field in list(range(71, 122, 3)) + [216, 231]:
                self.assertEqual(self.client[86057 + rank][field], self.client[base][field + 2])
                self.assertEqual(self.client[86057 + rank][field + 2], self.client[base][field])
            self.assertEqual(self.client[86257 + rank][71:74], [2, 0, 0])
        sql = (ROOT / 'data/sql/world/base/cultivation_rogue_spells.sql').read_text(encoding='utf-8')
        self.assertIn("(-86437, 'spell_cultivation_rogue_sha_honor')", sql)
        self.assertIn('VALUES (-86437,272,1,2,2,100)', sql)

    def test_seven_exact_rank_and_talent_contract(self):
        additions = {a['logical_name']: a for a in self.manifest['active_spells'] + self.manifest['passive_spells'] if a.get('seven_extension')}
        self.assertEqual(set(additions), set(gen.seven.DESCRIPTIONS_RU))
        self.assertEqual(additions['backstab']['base_spell_chain'], [53,2589,2590,2591,8721,11279,11280,11281,25300,26863,48656,48657])
        self.assertEqual(additions['sap']['base_spell_chain'], [6770,2070,11297,51724])
        self.assertEqual(additions['ghostly_strike']['talent_requirement'], 14278)
        self.assertIsNone(additions['safe_fall']['talent_requirement'])
        self.assertEqual(additions['safe_fall']['type'], 'common_passive')

    def test_celestial_backstab_cost_is_conditional_and_refund_is_damage_confirmed(self):
        for rank, base in enumerate((53,2589,2590,2591,8721,11279,11280,11281,25300,26863,48656,48657)):
            self.assertEqual(self.client[86110 + rank][42], self.client[base][42])
            self.assertEqual(self.server[86110 + rank][42], self.server[base][42])
            self.assertEqual(self.client[86310 + rank][42], self.client[base][42])
        seven = (ROOT / 'src/rogue/RoguePathSevenSpells.cpp').read_text(encoding='utf-8')
        self.assertIn('snapshot.ownControl = target && OwnControl(rogue, target);', seven)
        self.assertIn('cost -= c.celBackstabCost;', seven)
        self.assertIn('if (dealtDamage && variant->logicalName == "backstab" && cel)', seven)
        for aura_type in ('SPELL_AURA_MOD_STUN', 'SPELL_AURA_MOD_FEAR',
                          'SPELL_AURA_MOD_CONFUSE', 'SPELL_AURA_TRANSFORM'):
            self.assertIn(f'aura->HasEffectType({aura_type})', seven)
        common = (ROOT / 'src/rogue/RoguePathCommonSpells.cpp').read_text(encoding='utf-8')
        self.assertIn('SevenAfterHit(GetSpell(), GetHitUnit(), _miss == SPELL_MISS_NONE, GetHitDamage() > 0);', common)
        balance = (ROOT / 'src/rogue/RoguePathSevenBalance.h').read_text(encoding='utf-8')
        self.assertIn('"Celestial.Backstab.ControlCostReduction", 10,', balance)
        regression = (ROOT / 'src/rogue/RoguePathCelestialRegression.cpp').read_text(encoding='utf-8')
        self.assertIn('backstab-no-control-cost-60', regression)
        self.assertIn('backstab-own-control-cost-50-refund-10', regression)

    def test_new_cooldowns_ranges_and_ghost_aura(self):
        self.assertEqual(self.client[86322][29:31], [120000, 20000])
        self.assertEqual(self.client[86327][29:31], [15000, 0])
        self.assertEqual(self.client[86122][46], self.client[2094][46], 'Blind keeps its stock range')
        self.assertTrue(all(self.client[i][46] == self.manifest['celestial_revision']['ambush_range_id'] for i in range(86085, 86095)))
        range_id = self.manifest['celestial_revision']['ambush_range_id']
        for ranges in (self.client_ranges, self.server_ranges):
            row = ranges[range_id]
            self.assertEqual(row[5], 0, 'Eight-yard Ambush must use non-melee range validation')
            self.assertEqual(struct.unpack('<f', struct.pack('<I', row[3]))[0], 8.0)
            self.assertEqual(struct.unpack('<f', struct.pack('<I', row[4]))[0], 8.0)
        self.assertTrue(all(self.client[i][46] == 7 for i in range(86123, 86127)))
        for i in (86127, 86327):
            self.assertEqual(self.client[i][72], 0, 'No native self-dodge before enemy hit')
        self.assertEqual(self.client[86127][73], self.client[14278][73], 'Celestial Ghostly Strike retains the stock combo point')
        self.assertEqual(self.client[86584][36], 0, 'Dodge aura must not expire on first proc')
        self.assertEqual(self.client[86584][95], 49)
        self.assertEqual(self.client[86584][80] + 1, 30)
        self.assertEqual(self.client[86585][95:97], [138, 0], 'Sha self aura contains haste only')
        self.assertEqual(self.client[86801][95], 101, 'Sha target aura owns the armor reduction')
        self.assertEqual(self.client[86801][86], 6, 'Sha armor reduction targets the struck unit')
        self.assertEqual(self.client[86589][95], 110)
        self.assertEqual(self.client[86589][110], 3)
        self.assertEqual(self.client[86579][110:112], [98, 144])

    def test_shadowstep_and_preparation_native_records(self):
        shadowstep = self.client[86105]
        self.assertEqual(shadowstep[42], 0)
        self.assertEqual(shadowstep[29:31], [20000, 20000])
        self.assertEqual(shadowstep[86], 25, 'Celestial Shadowstep accepts enemy or ally')
        seven = (ROOT / 'src/rogue/RoguePathSevenSpells.cpp').read_text(encoding='utf-8')
        common = (ROOT / 'src/rogue/RoguePathCommonSpells.cpp').read_text(encoding='utf-8')
        self.assertNotIn('SummonCreature(900406', seven)
        self.assertIn('player->RemoveAurasDueToSpell(44373);', common)
        self.assertIn('player->RemoveAurasWithMechanic((1ULL << MECHANIC_ROOT) | (1ULL << MECHANIC_SNARE));', common)
        preparation = self.client[86107]
        self.assertTrue(preparation[4] & 0x40)
        self.assertTrue(preparation[4] & 0x80)
        self.assertEqual(preparation[28:31], [0, 0, 0])
        self.assertEqual(preparation[71:74], [6, 0, 0])
        self.assertEqual(preparation[95:98], [108, 0, 0])
        self.assertEqual((preparation[80] - 2**32 if preparation[80] >= 2**31 else preparation[80]) + 1, -30)
        self.assertEqual(preparation[110], 11)
        self.assertEqual(preparation[122:125], gen.PREPARATION_BASE_FAMILY_MASK)

        glyph_modifier = self.client[86599]
        self.assertEqual(glyph_modifier[40], 0)
        self.assertEqual(glyph_modifier[95:98], [108, 0, 0])
        self.assertEqual((glyph_modifier[80] - 2**32) + 1, -30)
        self.assertEqual(glyph_modifier[110], 11)
        self.assertEqual(glyph_modifier[122:125], [0, 0, gen.PREPARATION_GLYPH_FAMILY_MARKER])
        marked = []
        for ability in self.manifest['active_spells']:
            for rank in range(len(ability['base_spell_chain'])):
                for path in ('celestial', 'sha'):
                    spell_id = ability[f'{path}_first'] + rank
                    if self.client[spell_id][211] & gen.PREPARATION_GLYPH_FAMILY_MARKER:
                        marked.append((ability['logical_name'], path, rank + 1))
        expected_marked = []
        for logical_name in ('dismantle', 'kick', 'blade_flurry'):
            ability = next(item for item in self.manifest['active_spells'] if item['logical_name'] == logical_name)
            expected_marked.extend((logical_name, 'celestial', rank + 1)
                                   for rank in range(len(ability['base_spell_chain'])))
        self.assertEqual(sorted(marked), sorted(expected_marked))

        celestial_preparation = gen.read_string(self.client_strings, preparation[178])
        display_preparation = gen.read_string(self.client_strings, self.client[86621][178])
        for text in (celestial_preparation, display_preparation):
            self.assertTrue(text.startswith('|cff7CEBFFПассивно сокращает|r'), text)
            self.assertIn('|cffFFD200 время восстановления способностей «Хладнокровие», '
                          '«Шаг сквозь тень», «Исчезновение», «Ускользание» и «Спринт» |r', text)
            self.assertIn('|cff7CEBFFна 30%.|r', text)
            self.assertNotIn('При активации этой способности', text)
            self.assertNotIn('итоговое время восстановления', text)
            self.assertEqual(text.count('|cff'), text.count('|r'))
        self.assertEqual(celestial_preparation, display_preparation,
                         'Preparation must have one tooltip before and after learning')

    def test_native_framexml_path_header_contract(self):
        source = (ROOT / 'client_patch/framexml/CultivationRogueHeader.lua').read_text(encoding='utf-8')
        tabs = {tab_id: index + 1 for index, tab_id in enumerate(self.manifest['talent_ui']['tab_order'])}
        expected = {
            f'{tabs[item["tab_id"]]}:{item["tier"] + 1}:{item["column"] + 1}'
            for item in self.manifest['talent_ui']['mappings']
        }
        actual = set(re.findall(r'\["(\d+:\d+:\d+)"\] = true', source))
        self.assertEqual(actual, expected)
        self.assertIn('labels = { celestial = "Небожитель", sha = "Ша" }', source)
        for method in ('SetSpell', 'SetSpellBookItem', 'SetAction', 'SetHyperlink'):
            self.assertIn(f'"{method}"', source)
        self.assertIn('hooksecurefunc(GameTooltip, method, PresentSpellHeader)', source)
        self.assertIn('hooksecurefunc(GameTooltip, "SetTalent", PresentTalentHeader)', source)
        self.assertIn('preparationPosition = "3:5:2"', source)
        self.assertIn('HidePreparationActivationMetadata(tooltip)', source)
        self.assertGreaterEqual(source.count('tooltip:Show()'), 2)
        self.assertNotIn('RoguePathsTalentData', source)
        self.assertNotIn('SetTalent =', source)

        seven = (ROOT / 'src/rogue/RoguePathSevenSpells.cpp').read_text(encoding='utf-8')
        player = (ROOT / 'src/rogue/RoguePathPlayerScript.cpp').read_text(encoding='utf-8')
        service = (ROOT / 'src/rogue/RoguePathSpellService.cpp').read_text(encoding='utf-8')
        self.assertNotIn('void ModifyCooldown(', seven)
        self.assertNotIn('SMSG_MODIFY_COOLDOWN', seven)
        self.assertIn('void SyncCelestialPreparationGlyph(Player* player)', seven)
        self.assertIn('Mechanics::SyncCelestialPreparationGlyph(player);', player)
        self.assertIn('Mechanics::SyncCelestialPreparationGlyph(player);', service)

    def test_corrected_visible_buff_values_and_wording(self):
        adrenaline = gen.read_string(self.client_strings, self.client[86524][178])
        overkill = gen.read_string(self.client_strings, self.client[86558][178])
        self.assertIn('50', adrenaline)
        self.assertNotIn('20', adrenaline)
        self.assertEqual(overkill, 'Скорость восстановления энергии повышена на 30%.')
        self.assertEqual(self.client[86524][80] + 1, 50)
        self.assertEqual(self.client[86558][80] + 1, 30)

    def test_celestial_kidney_uses_stock_rank_duration_and_preparation_source_guards(self):
        source = (ROOT / 'src/rogue/RoguePathSevenSpells.cpp').read_text(encoding='utf-8')
        duration_hook = source.split('void BeforeDiminishing', 1)[1].split('void OnSpellCheckCast', 1)[0]
        self.assertNotIn('logicalName == "kidney_shot"', duration_hook)
        self.assertIn('HasPathPassiveRank(player, 14185)', source)
        regression = (ROOT / 'src/rogue/RoguePathCelestialRegression.cpp').read_text(encoding='utf-8')
        kidney_fixture = regression.split('for (uint8 combo = 1; combo <= 5; ++combo)', 1)[1].split('bool learnedGhostlyForFixture', 1)[0]
        self.assertIn('kidneyTarget->AddUnitState(UNIT_STATE_STUNNED);', kidney_fixture)
        range_hook = source.split('void ModifyCastRange', 1)[1].split('void BeforeDiminishing', 1)[0]
        self.assertNotIn('logicalName == "ambush"', range_hook)

    def test_celestial_sap_and_periodic_duration_contracts_match_the_new_tooltips(self):
        seven = (ROOT / 'src/rogue/RoguePathSevenSpells.cpp').read_text(encoding='utf-8')
        duration_hook = seven.split('void BeforeDiminishing', 1)[1].split('void OnSpellCheckCast', 1)[0]
        self.assertIn('variant->logicalName == "sap"', duration_hook)
        self.assertIn('if (PvP(target))', duration_hook)
        self.assertIn('bonus = 2000;', duration_hook)
        self.assertIn('duration = duration * 3 / 2;', duration_hook)
        self.assertIn('limit = limit * 3 / 2;', duration_hook)

        common = (ROOT / 'src/rogue/RoguePathCommonSpells.cpp').read_text(encoding='utf-8')
        aura_duration = common.split('void OnCalcMaxDuration', 1)[1].split('bool CanRemoveAuraOnDamage', 1)[0]
        self.assertIn('int32 amplitude = int32(aura->GetSpellInfo()->Effects[EFFECT_0].Amplitude);', aura_duration)
        self.assertIn('maxDuration = int32(std::ceil(float(ticks) * 1.4f)) * amplitude;', aura_duration)
        self.assertIn('variant->logicalName == "garrote" && variant->path == RoguePath::Celestial', aura_duration)
        self.assertIn('maxDuration += 6000;', aura_duration)

    def test_celestial_killing_spree_guard_matches_sequence(self):
        row = self.client[86526]
        self.assertEqual(row[95], 87, 'Guard must reduce damage taken')
        self.assertEqual(row[80] - 2**32 + 1, -50)
        source = (ROOT / 'src/rogue/RoguePathCommonSpells.cpp').read_text(encoding='utf-8')
        self.assertIn('player->CastSpell(player, Generated::CelestialKillingSpreeGuard, true);', source)
        self.assertIn('guard->SetMaxDuration(spree->GetMaxDuration());', source)
        self.assertIn('guard->SetDuration(spree->GetDuration());', source)
        self.assertIn('target->RemoveAurasDueToSpell(Generated::CelestialKillingSpreeGuard);', source)

    def test_safe_fall_is_single_visible_dummy_passive(self):
        for spell in (86440, 86441):
            row = self.client[spell]
            self.assertTrue(row[4] & 0x40, 'Passive flag retained')
            self.assertEqual(row[95:98], [4, 0, 0], 'No second native height reduction')
            self.assertTrue(gen.read_string(self.client_strings, row[144]))

    def test_new_script_bindings_and_stock_shiv_not_duplicated(self):
        sql = (ROOT / 'data/sql/world/base/cultivation_rogue_spells.sql').read_text(encoding='utf-8')
        for spell in (86128, 86328):
            self.assertIn(f"({spell}, 'spell_cultivation_rogue_shiv')", sql)
        for spell in (86593, 86594, 86595):
            self.assertIn(f"({spell}, 'spell_cultivation_rogue_shiv_component')", sql)
        self.assertNotRegex(sql, r"\((?:86128|86328), 'spell_rog_shiv'\)")
        self.assertIn("(86584, 'spell_cultivation_rogue_ghostly_dodge')", sql)
        self.assertIn('VALUES (86584,680,16,100)', sql)

    def test_seven_config_is_materialized_and_referenced(self):
        header = (ROOT / 'src/rogue/RoguePathSevenBalance.h').read_text(encoding='utf-8')
        config = (ROOT / 'conf/mod_cultivation.conf.dist').read_text(encoding='utf-8')
        sources = '\n'.join(p.read_text(encoding='utf-8') for p in (ROOT / 'src').rglob('*.cpp'))
        for field, key, default in re.findall(r'X\((\w+), "([^"]+)", (\d+),', header):
            self.assertIn(f'Cultivation.Rogue.{key} = {default}', config)
            self.assertRegex(sources, r'\.' + field + r'\b', field)

    def test_native_integration_guards(self):
        core = ROOT.parents[1] / 'src/server/game'
        player = (core / 'Entities/Player/Player.cpp').read_text(encoding='utf-8')
        self.assertIn('sScriptMgr->BeforeFallDamage(this, rawDamage, damage)', player)
        self.assertIn('sScriptMgr->AfterFallDamage(this, rawDamage, final_damage)', player)
        unit = (core / 'Entities/Unit/Unit.cpp').read_text(encoding='utf-8')
        self.assertIn('CanDispelAura', unit)
        auras = (core / 'Spells/Auras/SpellAuraEffects.cpp').read_text(encoding='utf-8')
        self.assertIn('CanRemoveAuraOnDamage', auras)
        self.assertIn('OnAuraDamageBreak', auras)
        source = (ROOT / 'src/rogue/RoguePathSevenSpells.cpp').read_text(encoding='utf-8')
        all_sources = '\n'.join(p.read_text(encoding='utf-8') for p in (ROOT / 'src').rglob('*.cpp'))
        self.assertNotIn('OnPlayerUpdate', source)
        self.assertIn('snapshot.openerTarget == target->GetGUID()', source)
        self.assertNotIn('RefreshOffhandPoison', all_sources, 'Celestial Shiv performs one native poison attempt without refreshing')
        self.assertIn('DISPEL_DISEASE', all_sources)
        self.assertIn('HasAura(Generated::CelestialShivProtection)', all_sources)
        component = source.split('class spell_cultivation_rogue_shiv_component', 1)[1]
        self.assertNotIn('rogue->CastSpell', component, 'Only the parent launches the two weapon components')
        self.assertIn('snapshot.shivComboAwarded', component)

    def test_packaging_uses_exact_clone_source(self):
        source = (ROOT / 'tools/package_seven_candidate.py').read_text(encoding='utf-8')
        self.assertIn("source.parent == ROOT / 'test-client/20260831-rogue-paths-v1/Data/ruRU'", source)
        self.assertIn('assert len(sources) == 2', source)
        schema5 = (ROOT / 'tools/package_visibility_candidate.py').read_text(encoding='utf-8')
        self.assertIn("CLIENT / 'Data/ruRU'", schema5)
        self.assertIn('pre-change-schema4-install-20260901T060529', schema5)
        self.assertIn("data/sql/migrations/1.5.0", schema5)

    def test_repeated_path_switch_preserves_suppressed_preparation_slot(self):
        source = (ROOT / 'src/rogue/RoguePathSpellService.cpp').read_text(encoding='utf-8')
        self.assertIn('character_cultivation_rogue_suppressed_action', source)
        self.assertIn('RememberSuppressedPreparationButton', source)
        self.assertIn('RestoreSuppressedPreparationButtons(player, PreparationShaSpell)', source)
        self.assertIn('RestoreSuppressedPreparationButtons(player, PreparationBaseSpell)', source)
        self.assertIn('CharacterDatabase.DirectExecute', source)

    def test_spellbook_sync_preserves_running_variant_cooldowns(self):
        source = (ROOT / 'src/rogue/RoguePathSpellService.cpp').read_text(encoding='utf-8')
        capture = source.index('std::vector<CooldownTransfer> capturedCooldowns;')
        mutation = source.index('std::unordered_map<uint32, uint32> actionReplacements;', capture)
        restore = source.index('RestoreCapturedCooldown(player, transfer);', mutation)
        self.assertLess(capture, mutation, 'cooldowns must be captured before spellbook mutation')
        self.assertGreater(restore, mutation, 'cooldowns must be restored after spellbook mutation')
        self.assertIn('CaptureCooldownTransfer(player, { row.baseSpell, row.celestialSpell, row.shaSpell }', source)
        sql = (ROOT / 'data/sql/migrations/2.0.0/characters.up.sql').read_text(encoding='utf-8')
        self.assertIn('character_rogue_path_suppressed_action', sql)
        self.assertIn('character_cultivation_rogue_suppressed_action', sql)
        base = (ROOT / 'data/sql/characters/base/character_cultivation_rogue.sql').read_text(encoding='utf-8')
        self.assertIn('PRIMARY KEY (`guid`, `spec`, `button`)', base)
        protocol = (ROOT / 'tools/test_world_protocol.py').read_text(encoding='utf-8')
        self.assertIn('Celestial/Sha/Celestial/Sha/Celestial/reset', protocol)

    def test_spell_script_validation_without_live_cast(self):
        source = (ROOT / 'src/rogue/RoguePathCommonSpells.cpp').read_text(encoding='utf-8')
        destructor = source.split('~spell_cultivation_rogue_active() override', 1)[1].split('private:', 1)[0]
        self.assertIn('if (_castKey && GetCaster()', destructor)
        self.assertIn('Spell const* _castKey = nullptr;', source)

    def test_final_duration_contract(self):
        source = (ROOT.parents[1] / 'src/server/game/Spells/Auras/SpellAuras.cpp').read_text(encoding='utf-8')
        body = source.split('int32 Aura::CalcMaxDuration(Unit* caster) const', 1)[1].split('void Aura::SetDuration', 1)[0]
        self.assertLess(body.index('ApplySpellMod'), body.index('OnCalcMaxDuration'))

    def test_duration_hook_does_not_read_uninitialized_aura_effects(self):
        source = (ROOT / 'src/rogue/RoguePathCommonSpells.cpp').read_text(encoding='utf-8')
        body = source.split('void OnCalcMaxDuration(Aura const* aura, int32& maxDuration) override', 1)[1]
        body = body.split('bool CanRemoveAuraOnDamage', 1)[0]
        self.assertNotIn('aura->GetEffect(', body)
        self.assertIn('aura->GetSpellInfo()->Effects[EFFECT_0].Amplitude', body)
        self.assertIn('if (amplitude <= 0)', body)

    def test_celestial_visible_effects(self):
        cfg=self.manifest['celestial_revision']
        for name in cfg['visible_auras']:
            row=self.client[self.manifest['technical_spells'][name]]
            self.assertFalse(row[4] & 0x80)
            self.assertFalse(row[9] & 0x18000400)
            self.assertNotEqual(row[133],0)
            for field in (136,153,170,187):
                for locale in (0,8):
                    self.assertTrue(gen.read_string(self.client_strings,row[field+locale]))
                self.assertEqual(row[field+16] & 0x101,0x101)
        for spell,amount in ((86597,20),(86598,15)):
            row=self.client[spell]
            self.assertEqual(row[95:98],[4,0,0], 'No native damage aura double scaling')
            self.assertEqual(row[80]-2**32+1,-amount)
            self.assertEqual(row[3],0,'No snare mechanic')
            self.assertTrue(row[4]&0x04000000)
            self.assertEqual(row[133],1904)
        self.assertEqual(self.client[86508][95:98],[38,38,0])
        self.assertEqual(self.client[86508][110:112],[26,33])
        self.assertEqual(self.client[86508][133],517)
        self.assertEqual(self.client[86561][133],self.client[1966][133])
        self.assertEqual(self.client[86561][95],229)
        self.assertEqual(self.client[86561][80]-2**32+1,-70)
        for spell in (86007,86008):
            self.assertEqual(self.client[spell][40],18)
            self.assertIn('15%',gen.read_string(self.client_strings,self.client[spell][195]))
        for spell in (86001,86002,86003):
            self.assertEqual(self.client[spell][9]&0x60008,0)
            self.assertEqual(self.client[spell][213],0)

    def test_dedicated_radius_range_preserve_baseline(self):
        baseline=Path(r'C:\Solo WotLK\test-server\20260831-rogue-paths-v2\data\dbc')
        for name,fields in (('SpellRadius',4),('SpellRange',40)):
            original,_=gen.load_dbc(baseline/(name+'.dbc'),fields)
            c,_=gen.load_dbc(ROOT/'client_patch/staging/DBFilesClient'/(name+'.dbc'),fields)
            s,_=gen.load_dbc(ROOT/'generated/server/dbc'/(name+'.dbc'),fields)
            self.assertEqual(c,s)
            lookup={r[0]:r for r in c}
            for row in original: self.assertEqual(lookup[row[0]],row)
            indices=(1,3) if name=='SpellRadius' else (3,4)
            for i in indices:
                self.assertEqual(struct.unpack('<f',struct.pack('<I',lookup[9000][i]))[0],12.0 if name=='SpellRadius' else 8.0)

    def test_sha_candidate41_explicit_native_dbc_contract(self):
        duration_rows, _ = gen.load_dbc(Path(r'C:\Solo WotLK\test-server\20260831-rogue-paths-v3\data\dbc\SpellDuration.dbc'), 4)
        durations = {row[0]: row[1] for row in duration_rows}
        for rank, base in enumerate((53,2589,2590,2591,8721,11279,11280,11281,25300,26863,48656,48657)):
            self.assertEqual(self.client[86310 + rank][42], self.client[base][42])
        for spell in range(86285, 86295):
            self.assertEqual(self.client[spell][42], 75)
        for spell in range(86323, 86327):
            self.assertEqual(self.client[spell][42], 65)
            self.assertEqual(self.client[spell][29], 10000)
            self.assertEqual(durations[self.client[spell][40]], 6000)
        self.assertEqual(self.client[86207][29:31], [120000, 120000])
        self.assertEqual(durations[self.client[86207][40]], 8000)
        self.assertEqual(durations[self.client[86322][40]], 5000)
        self.assertEqual(self.client[86279][80], (-36) & 0xffffffff)

    def test_periodic_damage_only_call_sites(self):
        source=(ROOT.parents[1]/'src/server/game/Spells/Auras/SpellAuraEffects.cpp').read_text(encoding='utf-8')
        self.assertEqual(source.count('sScriptMgr->ModifyPeriodicCombatDamage(target, caster, damage, GetSpellInfo());'),2)
        self.assertNotIn('ModifyPeriodicCombatDamage(target, caster, heal',source)
        module=(ROOT/'src/rogue/RoguePathCommonSpells.cpp').read_text(encoding='utf-8')
        self.assertIn('ModifyIncoming(target, attacker, damage, spellInfo, false)',module)


if __name__ == '__main__':
    unittest.main(verbosity=2)
