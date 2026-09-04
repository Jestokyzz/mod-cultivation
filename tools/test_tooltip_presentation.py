"""Independent stock-text, percent/sign and Celestial-rework presentation gates."""
import json
from pathlib import Path
import re
import unittest

import generate_rogue_paths as g
import tooltip_stock as t
import visibility_schema3 as v

ROOT = Path(__file__).resolve().parents[1]
BEFORE = ROOT / 'client_patch/build/v1.3.0-candidate4'


def plain(text):
    return re.sub(r'\|cff[0-9A-Fa-f]{6}|\|r', '', text)


class TooltipPresentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / 'data/cultivation_rogue_spell_manifest.json').read_text(encoding='utf-8'))
        cls.rows, cls.strings = g.load_dbc(ROOT / 'client_patch/staging/DBFilesClient/Spell.dbc', 234)
        cls.client = {r[0]: r for r in cls.rows}

    def test_client_server_numeric_fields_match_and_seal_fate_is_fully_restored(self):
        self.assertEqual(g.semantic_non_string_rows(ROOT / 'client_patch/staging/DBFilesClient/Spell.dbc'),
                         g.semantic_non_string_rows(ROOT / 'generated/server/dbc/Spell.dbc'))
        for name in ('SpellIcon.dbc', 'SkillLineAbility.dbc', 'SpellDuration.dbc', 'SpellRadius.dbc',
                     'SpellRange.dbc', 'SpellDescriptionVariables.dbc'):
            client, server = ROOT / 'client_patch/staging/DBFilesClient' / name, ROOT / 'generated/server/dbc' / name
            if client.exists():
                self.assertEqual(g.sha256(client), g.sha256(server), name)
        icons, strings = g.load_dbc(ROOT / 'generated/server/dbc/SpellIcon.dbc', 2)
        icon = {row[0]: g.read_string(strings, row[1]) for row in icons}
        self.assertEqual(icon[6192], 'Interface\\Icons\\ability_rogue_surpriseattack2_celestial')
        self.assertEqual(icon[6193], 'Interface\\Icons\\ability_rogue_surpriseattack2_sha')
        for spell in range(86601, 86606):
            self.assertEqual(self.client[spell][133], 6168)
        for spell in range(86701, 86706):
            self.assertEqual(self.client[spell][133], 6169)
        self.assertNotIn('INV_Qiraj_JewelGlyphed', '\n'.join(icon.values()))
        seal = next(a for a in self.manifest['passive_spells'] if a['logical_name'] == 'seal_fate')
        self.assertIn('восстанавливают по 5 ед. энергии', seal['descriptions']['ruRU']['celestial'])
        self.assertIn('не более 10 ед. энергии в секунду', seal['descriptions']['ruRU']['celestial'])
        source = (ROOT / 'src/rogue/RoguePathCommonSpells.cpp').read_text(encoding='utf-8')
        self.assertIn('path == RoguePath::Celestial && comboOverflow', source)
        self.assertIn('std::min<uint8>(5, 10 - state.sealFateEnergyThisSecond)', source)

    def test_all_standard_descriptions_and_sources_preserved(self):
        old_rows, old_strings = g.load_dbc(BEFORE / 'staging/DBFilesClient/Spell.dbc', 234)
        old = {r[0]: r for r in old_rows}
        english_rows, english_strings = g.load_dbc(BEFORE / 'server/dbc/Spell.dbc', 234)
        english = {r[0]: r for r in english_rows}
        official, official_strings = v.source(g, self.manifest, 'spell', 234)
        native_talent_ranks = {
            spell_id
            for mapping in self.manifest['talent_ui']['mappings']
            for spell_id in mapping['rank_spells']
        }
        checked = 0
        for entry in g.expanded_entries(self.manifest):
            base = entry['base_spell']
            for locale in (0, 8):
                for field in (170, 187):
                    source = g.read_string(self.strings, self.client[base][field + locale])
                    expected_stock = (g.read_string(official_strings, official[base][field + locale])
                                      if locale == 8 else
                                      g.read_string(old_strings, old[base][field + locale]))
                    if locale == 8 and field == 170 and base in native_talent_ranks:
                        self.assertRegex(source, r'^\$\?s86500\[[^\[\]]+\]\[[^\[\]]+\]$')
                    else:
                        self.assertEqual(source, expected_stock)
                for path in ('celestial', 'sha'):
                    row = self.client[entry[path + '_spell']]
                    text = g.read_string(self.strings, row[170 + locale])
                    # Native talent rows are intentionally conditional now;
                    # custom variants still derive from the immutable stock source.
                    source = (g.read_string(official_strings, official[base][178])
                              if locale == 8 else
                              g.read_string(english_strings, english[base][170]))
                    standard = t.bind_stock_fields(source, base)
                    exact = entry.get('full_descriptions', {}).get('ruRU' if locale == 8 else 'enUS', {}).get(path)
                    locale_name = 'ruRU' if locale == 8 else 'enUS'
                    addition_text = entry['descriptions'][locale_name][path].replace('{rank}', str(entry['rank']))
                    self.assertEqual(text, g.generated_path_tooltip(
                        entry, source, addition_text, path, locale_name, self.manifest, base_spell=base))
                    addition = text
                    inline = (self.manifest.get('tooltip_inline_edits', {})
                              .get(entry['logical_name'], {}).get(locale_name, {}).get(path))
                    if exact is None and inline is None and standard:
                        self.assertIn('|cffFFD200' + standard + '|r', text)
                    if exact is None or '{path}' in exact:
                        self.assertIn('|cff' + self.manifest['path_icons'][path + '_color'], text)
                    self.assertTrue(text.startswith((
                        '|cffFFD200', '|cff' + self.manifest['path_icons'][path + '_color'])))
                    self.assertTrue(text.endswith('|r'))
                    self.assertNotIn('\r\n\r\n|cff', text)
                    self.assertEqual(text.count('|cff'), text.count('|r'))
                    self.assertNotIn('{path}', text)
                    self.assertNotIn('{/path}', text)
                    # Check every field atom independently of the binder's output.
                    for atom in t.ATOM.findall(standard):
                        parsed = t.FIELD.fullmatch(atom)
                        if parsed and atom not in t.DYNAMIC and atom not in t.GRAMMAR:
                            self.assertTrue(parsed['id'], (row[0], atom))
                    self.assertNotIn('\u2212', addition)
                    self.assertNotIn('%%', addition)
                    self.assertNotRegex(addition, r'%(?:s|d|f|u)\b')
                    self.assertNotRegex(addition, r'(?i)(?:Небожитель|Путь Ша|Celestial|Sha)\s*[\r\n:]')
                    checked += 1
        self.assertEqual(checked, 600)

    def test_percent_magnitudes_and_minus_are_preserved(self):
        for ability in self.manifest['active_spells'] + self.manifest['passive_spells']:
            for texts in ability['descriptions'].values():
                for text in texts.values():
                    normalized = t.player_text(text)
                    self.assertEqual(re.findall(r'\d+(?:[.,]\d+)?%?', text), re.findall(r'\d+(?:[.,]\d+)?%?', normalized))
                    self.assertEqual(text.count('%'), normalized.count('%'))
                    self.assertEqual(normalized.count('-'), text.count('-') + text.count('\u2212'))
        self.assertEqual(t.player_text('−10 энергии; −20%; +30%; 0,5%'), '-10 энергии; -20%; +30%; 0,5%')
        ghost = plain(g.read_string(self.strings, self.client[86127][178]))
        self.assertIn('80% стандартного урона оружия', ghost)
        self.assertIn('30% на 10 сек.', ghost)
        self.assertIn('Длина серии приемов увеличивается на 1', ghost)
        self.assertIn('20 ед. энергии', ghost)

    def test_blizzard_base_is_not_normalized_or_percent_formatted(self):
        base = '$14278s1% − stock; ${$AP*0.07} $lраз:раза;'
        result = t.compose(base, '−20%; +30%', '7CEBFF')
        self.assertEqual(result, '|cffFFD200' + base + '|r |cff7CEBFF-20%; +30%|r')

    def test_retired_celestial_copy_does_not_leak_into_tooltips(self):
        by_name = {item['logical_name']: item for item in self.manifest['active_spells'] + self.manifest['passive_spells']}
        def celestial(name):
            item = by_name[name]
            return '\n'.join(plain(g.read_string(self.strings, self.client[item['celestial_first'] + rank][178])).lower()
                             for rank in range(len(item['base_spell_chain'])))
        self.assertNotIn('защищает яды от рассеивания', celestial('shiv'))
        self.assertNotIn('2 приёма серии', celestial('shiv'))
        self.assertNotIn('10 сек. после исчезновения', celestial('hunger_for_blood'))
        self.assertNotIn('сбрасывает время восстановления', celestial('preparation'))
        self.assertNotIn('2 приёма серии', celestial('ghostly_strike'))

    def test_corrected_celestial_tooltip_contracts(self):
        by_name = {item['logical_name']: item for item in self.manifest['active_spells'] + self.manifest['passive_spells']}
        def text(name):
            item = by_name[name]
            return g.read_string(self.strings, self.client[item['celestial_first']][178])
        kidney = text('kidney_shot')
        self.assertEqual(kidney, t.exact(
            by_name['kidney_shot']['full_descriptions']['ruRU']['celestial'], '7CEBFF'))
        kick = text('kick')
        self.assertEqual(kick, t.exact(by_name['kick']['full_descriptions']['ruRU']['celestial'], '7CEBFF'))
        spree = plain(text('killing_spree'))
        self.assertIn('пока не будет совершено 5 атак', spree)
        self.assertIn('наносимый урон возрастает на 20%, а получаемый уменьшается на 50%', spree)
        self.assertIn('все атаки в первую очередь направляются в нее', spree)
        self.assertNotIn('Время восстановления сокращено', spree)
        preparation = plain(text('preparation'))
        for ability in ('Хладнокровие', 'Шаг сквозь тень', 'Исчезновение', 'Ускользание', 'Спринт'):
            self.assertIn(ability, preparation)
        for ability in ('Долой оружие', 'Пинок', 'Шквал клинков'):
            self.assertIn(ability, preparation)

    def test_inline_replacements_do_not_repeat_the_old_value_as_a_suffix(self):
        by_name = {item['logical_name']: item for item in
                   self.manifest['active_spells'] + self.manifest['passive_spells']}
        fan = g.read_string(self.strings, self.client[by_name['fan_of_knives']['celestial_first']][178])
        self.assertIn('радиусе |r|cff7CEBFF12|r|cffFFD200 м', fan)
        self.assertNotIn('Радиус действия увеличен до 12 м', plain(fan))
        self.assertNotIn('радиусе $51723a1 м', fan)
        for logical_name, locales in self.manifest['tooltip_inline_edits'].items():
            ability = by_name[logical_name]
            for locale_name, paths in locales.items():
                if locale_name != 'ruRU':
                    continue
                for path, contract in paths.items():
                    original = ability['descriptions']['ruRU'][path].replace('{rank}', '1')
                    replacement = contract.get('addition', original).replace('{rank}', '1')
                    if replacement == original or not original:
                        continue
                    integrated_values = []
                    for item in contract.get('replace', []):
                        integrated_values.extend(item.get('new_by_rank', [item.get('new', '')]))
                    integrated = ' '.join(value.replace('{path}', '').replace('{/path}', '')
                                          for value in integrated_values)
                    if original in integrated:
                        continue
                    rendered = plain(g.read_string(
                        self.strings, self.client[ability[path + '_first']][178]))
                    if rendered == original:
                        continue
                    self.assertNotIn(original, rendered, f'{logical_name}/{path} kept obsolete suffix')

    def test_requested_celestial_values_are_colored_inline_and_blocks_are_separated(self):
        by_name = {item['logical_name']: item for item in
                   self.manifest['active_spells'] + self.manifest['passive_spells']}

        def last_rank(name):
            item = by_name[name]
            spell_id = item['celestial_first'] + len(item['base_spell_chain']) - 1
            return g.read_string(self.strings, self.client[spell_id][178])

        cyan = '|cff' + self.manifest['path_icons']['celestial_color']
        kick = last_rank('kick')
        self.assertIn(cyan + '6 сек.|r', kick)
        kidney = last_rank('kidney_shot')
        for seconds in ('2 секунды', '3 секунды', '4 секунды', '5 секунд', '6 секунд'):
            self.assertIn(cyan + seconds + '|r', kidney)

        backstab = last_rank('backstab')
        self.assertIn(cyan + 'Если цель находится под вашим контролем, стоимость снижается на 10 ед. энергии.', backstab)
        self.assertIn('При успешном попадании по такой цели восстанавливается 10 ед. энергии.', plain(backstab))
        self.assertNotIn('Стоимость снижена на 15', plain(backstab))

        garrote = last_rank('garrote')
        self.assertRegex(garrote, re.escape(cyan) + r'\$\{\(\$\d+m1\+\$AP\*0\.07\)\*8\}\|r')
        self.assertNotRegex(garrote, r'\$\{\(\$\d+m1\+\$AP\*0\.07\)\*6\}')

        rupture = last_rank('rupture')
        for multiplier in (6, 7, 9, 10, 12):
            self.assertRegex(rupture, re.escape(cyan) + r'\$\?s56801\[[^]]+\]\[\$\{[^}]+\*' + str(multiplier) + r'\}\]\|r')
        self.assertIn(cyan + '$?s56801[${32}][${24}]|r', rupture)
        self.assertIn('\n|r' + cyan + 'Частота нанесения урона не меняется.|r', rupture)

        finishers = {'kidney_shot', 'rupture', 'slice_and_dice', 'eviscerate',
                     'deadly_throw', 'envenom', 'expose_armor'}
        marked = {item['logical_name'] for item in self.manifest['active_spells']
                  if item.get('tooltip_addition_separator') == '\n'}
        self.assertEqual(marked, finishers)
        for name in ('eviscerate', 'deadly_throw'):
            item = by_name[name]
            for path in ('celestial', 'sha'):
                spell_id = item[path + '_first'] + len(item['base_spell_chain']) - 1
                rendered = g.read_string(self.strings, self.client[spell_id][178])
                self.assertRegex(rendered, r'(?:\n\|r|\|r\n)\|cff' +
                                 self.manifest['path_icons'][path + '_color'])

        fan = last_rank('fan_of_knives')
        self.assertNotIn('\n|r' + cyan + 'Каждая поражённая цель', fan)

        expose = last_rank('expose_armor')
        self.assertIn('\n|r' + cyan + 'При использовании с 5 приемами серии', expose)
        envenom = last_rank('envenom')
        self.assertIn('\n|r' + cyan + 'Прямой урон уменьшается на 10%.|r', envenom)

        sap = last_rank('sap')
        self.assertIn(cyan + '90 сек. против существ или 12 сек. против игроков|r', sap)
        self.assertNotIn('62 сек.', plain(sap))


if __name__ == '__main__':
    unittest.main()
