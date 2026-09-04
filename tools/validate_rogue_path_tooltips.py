"""Independent artifact gates and explicit static-vs-runtime audit reports."""
from __future__ import annotations

import json
from pathlib import Path
import re
import generate_rogue_paths as g
import tooltip_stock
import visibility_schema3 as v

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest_path = ROOT / 'data/cultivation_rogue_spell_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    rows, strings = g.load_dbc(ROOT / 'client_patch/staging/DBFilesClient/Spell.dbc', 234)
    client = {row[0]: row for row in rows}
    icons, icon_strings = g.load_dbc(ROOT / 'client_patch/staging/DBFilesClient/SpellIcon.dbc', 2)
    icons = {row[0]: row for row in icons}
    stock, stock_strings = v.source(g, manifest, 'spell', 234)
    stock_icons, stock_icon_strings = v.source(g, manifest, 'icon', 2)
    variables, vs = g.load_dbc(ROOT / 'client_patch/staging/DBFilesClient/SpellDescriptionVariables.dbc', 2)
    variables = {row[0]: row for row in variables}
    sla, _ = g.load_dbc(ROOT / 'client_patch/staging/DBFilesClient/SkillLineAbility.dbc', 14)
    abilities = {a['logical_name']: a for a in manifest['active_spells'] + manifest['passive_spells']}
    audit = json.loads((ROOT / 'generated/schema3-audit/visibility-audit.json').read_text(encoding='utf-8'))
    textures = json.loads((Path(r'C:\Solo WotLK\work\mobility-retirement-v1\icons-manifest.json')).read_text(encoding='utf-8'))
    texture_by_id = {r['icon_id']: r for r in textures['files']}
    errors, tooltips, icon_report, passive_report = [], [], [], []

    def check(condition, message):
        if not condition:
            errors.append(message)

    def stock_icon(row, base, label):
        check(row[133] == stock[base][133] and row[134] == stock[base][133],
              f'{label}: wrong exact-rank icon IDs')
        icon = icons.get(row[133])
        expected = g.read_string(stock_icon_strings, stock_icons[stock[base][133]][1])
        actual = g.read_string(icon_strings, icon[1]) if icon else None
        check(actual == expected, f'{label}: wrong icon path')
        resource = audit['icon_resources'].get(expected + '.blp')
        check(bool(resource), f'{label}: stock BLP not proven in audited official chain')
        icon_report.append({'spell': row[0], 'base': base, 'icon': row[133], 'active_icon': row[134],
                            'path': actual, 'stock_resource': resource, 'gui': 'not-tested'})

    for entry in g.expanded_entries(manifest):
        base = entry['base_spell']
        for path in ('celestial', 'sha'):
            row = client[entry[path + '_spell']]
            label = f'{entry["logical_name"]}/{path}/{entry["rank"]}'
            ru_name = g.read_string(strings, row[144])
            expected_name = g.celestial.NAMES.get(entry['logical_name']) if path == 'celestial' else None
            check(ru_name == (expected_name or g.read_string(stock_strings, stock[base][144])), f'{label}: non-stock Russian name')
            for locale, index in (('ruRU', 8), ('enUS', 0)):
                text = g.read_string(strings, row[170 + index])
                rank = g.read_string(strings, row[153 + index])
                exact = entry.get('full_descriptions', {}).get(locale, {}).get(path)
                check(rank == g.rank_text('', 1, 1, path, locale == 'ruRU'), f'{label}/{locale}: rank label')
                # Russian source is independent of the generated stock row.
                if locale == 'ruRU':
                    standard = g.read_string(stock_strings, stock[base][178])
                    addition = entry['descriptions'][locale][path].replace('{rank}', str(entry['rank']))
                    expected = g.generated_path_tooltip(
                        entry, standard, addition, path, locale, manifest, base_spell=base)
                    check(text == expected, f'{label}/{locale}: inline stock edit or separator changed')
                check('Путь Небожителя' not in text and 'Путь Ша' not in text, f'{label}: forbidden prefix')
                allowed_starts = ('|cffFFD200', '|cff' + manifest['path_icons'][path + '_color'])
                check(text.startswith(allowed_starts), f'{label}/{locale}: invalid initial tooltip color')
                check(text.endswith('|r'), f'{label}/{locale}: tooltip color is not closed')
                check(text.count('|cff') == text.count('|r'), f'{label}/{locale}: broken color pairs')
                needs_path_color = exact is None or '{path}' in exact
                if needs_path_color:
                    check('|cff' + manifest['path_icons'][path + '_color'] in text,
                          f'{label}/{locale}: path change color missing')
                check('{path}' not in text and '{/path}' not in text, f'{label}/{locale}: source marker leaked')
                check('\r\n\r\n|cff' not in text, f'{label}/{locale}: obsolete separate path block')
                definition = g.read_string(vs, variables[row[232]][1]) if row[232] in variables else ''
                try:
                    tooltip_stock.validate_variables(text, definition)
                except ValueError as error:
                    errors.append(f'{label}: {error}')
                tooltips.append({'spell': row[0], 'base': base, 'locale': locale, 'rank': rank,
                                 'text': text, 'native_formatter_gui': 'not-tested'})
            if entry['icon_source'] == 'stock_base_rank' or (entry['logical_name'] == 'feint' and path == 'celestial'):
                stock_icon(row, base, label)
            else:
                expected_id = g.path_icon_id(manifest, entry['logical_name'], path)
                check(row[133] == expected_id and row[134] == stock[base][133], f'{label}: custom icon mapping')
                icon = icons.get(expected_id)
                resource = texture_by_id.get(expected_id)
                actual = g.read_string(icon_strings, icon[1]) if icon else ''
                check(bool(resource) and actual + '.blp' == resource['virtual_path'], f'{label}: custom BLP path')
                if resource:
                    check(g.sha256(Path(resource['blp'])) == resource['blp_sha256'], f'{label}: BLP SHA mismatch')
                    check(resource['mip_levels'] == 7 and resource['dimensions'] == [64, 64], f'{label}: BLP dimensions/mips')
                icon_report.append({'spell': row[0], 'base': base, 'icon': row[133], 'active_icon': row[134],
                                    'path': actual, 'custom_resource': resource, 'gui': 'not-tested'})

    for item in manifest['display_passives']:
        row = client[item['spell_id']]
        label = f'display/{row[0]}'
        check(row[4] & 0x40 and not row[4] & 0x80, f'{label}: passive/hidden flags')
        check(row[71:74] == [0, 0, 0] and row[95:98] == [0, 0, 0] and not any(row[116:119]), f'{label}: mechanic effect leaked into display')
        check(not any(row[i] for i in (28, 29, 30, 34, 35, 36, 41, 42, 43, 44, 45, 204, 205, 206)), f'{label}: cost/GCD/CD/proc')
        matches = [r for r in sla if r[2] == row[0]]
        check(len(matches) == 1 and matches[0][1] == item['skill_line'] and matches[0][9] == 0, f'{label}: SkillLineAbility ownership')
        check(item['mechanic_spell'] in client, f'{label}: missing mechanic')
        expected_id = item.get('icon_id')
        ability = abilities.get(item['logical_name'])
        if expected_id is None and ability and ability.get('icon_source') == 'approved_path_frame':
            expected_id = g.path_icon_id(manifest, item['logical_name'], item['path'])
        if expected_id is None:
            stock_icon(row, item['icon_source_spell'], label)
        else:
            check(row[133] == expected_id and row[134] == stock[item['icon_source_spell']][134], f'{label}: wrong custom icon IDs')
            icon = icons.get(expected_id)
            resource = texture_by_id.get(expected_id)
            actual = g.read_string(icon_strings, icon[1]) if icon else ''
            check(bool(resource) and actual + '.blp' == resource['virtual_path'], f'{label}: wrong custom icon path')
            icon_report.append({'spell': row[0], 'base': item['icon_source_spell'], 'icon': row[133],
                                'active_icon': row[134], 'path': actual, 'custom_resource': resource, 'gui': 'not-tested'})
        for locale, index in (('ruRU', 8), ('enUS', 0)):
            text = g.read_string(strings, row[170 + index])
            check(bool(g.read_string(strings, row[136 + index])), f'{label}/{locale}: empty name')
            check('$' not in text and bool(text), f'{label}/{locale}: unresolved display-only tooltip')
        if item['talent_required']:
            check(client[item['mechanic_spell']][4] & 0x80, f'{label}: mechanic also visible')
        passive_report.append({**item, 'name': g.read_string(strings, row[144]),
                               'text': g.read_string(strings, row[178]), 'static_effect_free': True, 'runtime_sync': 'not-tested'})

    for logical, spell in manifest['technical_spells'].items():
        row = client[spell]
        item = manifest['technical_presentation'][logical]
        check(bool(row[4] & 0x80) == (item['visibility'] == 'hidden'), f'{logical}: presentation visibility mismatch')
        if item['visibility'] == 'hidden':
            continue
        if not item.get('preserve_validated_presentation'):
            source_row = stock[item['icon_source_spell']]
            expected_icon = item.get('icon_id', source_row[133])
            check(row[133] == expected_icon and row[134] == source_row[134],
                  f'{logical}: buff/debuff icon is not the requested standard/shared icon')
        for locale, index in (('ruRU', 8), ('enUS', 0)):
            name, text = (g.read_string(strings, row[f + index]) for f in (136, 170))
            check(bool(name) and bool(text) and len(text) > 8, f'{logical}/{locale}: empty/placeholder text')
            if locale == 'ruRU':
                check(bool(re.search('[А-Яа-яЁё]', name)), f'{logical}: technical English name')
            check(row[133] in icons, f'{logical}: missing icon record')
    talent_ids = {item['talent_id'] for item in manifest['talent_ui']['mappings']}
    check(len(talent_ids) == len(manifest['talent_ui']['mappings']), 'Duplicate TalentUI node')
    for ability in manifest['passive_spells']:
        if ability['type'] == 'common_passive':
            continue
        check(any(x['logical_name'] == ability['logical_name'] for x in manifest['talent_ui']['mappings']), 'Talent UI missing ' + ability['logical_name'])
    # The explicit HAT standard rank must never use the dummy mechanic's 1%.
    check('100%' in g.read_string(strings, client[86619][178]).split('\r\n\r\n')[0], 'HAT rank 3 is not stock 100%')
    check(client[86620][133] == 6192 and client[86720][133] == 6193,
          'Stealth Mastery does not use the approved user-supplied path-framed icons')
    output = ROOT / 'generated/schema3-audit/artifact-validation.json'
    report = {'status': 'failed' if errors else 'static-pass-runtime-pending', 'manifest_sha256': g.sha256(manifest_path),
              'errors': errors, 'tooltips': tooltips, 'icons': icon_report, 'display_passives': passive_report,
              'talent_nodes': len(talent_ids), 'gui_screenshots': 0, 'native_combat_acceptance': 'not-run-for-schema3'}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    docs = {
        'tooltip_audit.md': ('Аудит тултипов', ['Стандартный ruRU текст — официальный Spell.dbc точного ранга.',
            'Поля активных навыков квалифицированы stock ID; AP/оружие/символы остаются динамическими.',
            'DescriptionVariables клонированы по исходному рангу, исходные записи сохранены.',
            'Числа display-only пассивок разрешены заранее; пустые Effects не читаются.',
            'enUS берётся из прежнего clean server baseline: независимый официальный enUS MPQ здесь отсутствует.',
            f'Проверено локализованных записей: {len(tooltips)}. GUI/нативный форматтер: НЕ ПРОВЕРЕНЫ.']),
        'icon_audit_report.md': ('Аудит иконок', [f'Проверено сопоставлений иконок: {len(icon_report)}.',
            'По уточнению пользователя семь навыков используют 14 отдельных Sage/Demon BLP: исходные stock-рисунки, тот же утверждённый reskin и рамка +2 px. Каждый ранг имеет правильный custom SpellIconID; ActiveIconID у активных вариантов указывает на стандартный рисунок базового навыка.',
            'Пассивные таланты: утверждённые рамки пути поверх исходного центра; Мастерство незаметности: ability_rogue_surpriseattack2 с отдельными суффиксами _sha и _celestial.',
            'ID 6100–6177 и прежние 78 BLP сохранены; 6178–6196 — новые варианты и общие иконки. Четыре контрольные старые иконки воспроизведены генератором побайтово.',
            'Ранее для семи навыков были назначены stock-only иконки; отдельные варианты путей отсутствовали.',
            'GUI: НЕ ПРОВЕРЕН. Наличие ресурса не считается визуальным acceptance.']),
        'passive_talent_audit_report.md': ('Аудит пассивных талантов', [f'Display-only записей: {len(passive_report)}; TalentUI узлов: {len(talent_ids)}.',
            'Бойня, Печать судьбы, Мастер ядов, Боевой потенциал, Обман смерти, Воровская честь — каждый ранг и оба пути.',
            'Активные талантовые способности включены в карту Talent.dbc для дополнения штатного tooltip.',
            'Механические ауры отделены от видимых записей; новых proc/effect у display нет.',
            'SyncVisibleTalentPassives: active spec / exact highest rank / selected path; отдельные циклы удаления и изучения.',
            'Сброс талантов, dual spec, relog, смена пути и отсутствие двойного эффекта в игре: НЕ ПРОВЕРЕНЫ для schema 3.']),
    }
    for name, (title, lines) in docs.items():
        (ROOT / 'docs' / name).write_text('# ' + title + '\n\nСтатус: ' + report['status'] + '\n\n' +
            '\n'.join('- ' + line for line in lines) + '\n\nПолная построчная проверка: `generated/schema3-audit/artifact-validation.json`.\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'errors': errors, 'tooltip_records': len(tooltips),
                      'icon_mappings': len(icon_report), 'display_records': len(passive_report), 'talent_nodes': len(talent_ids)}, ensure_ascii=True))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
