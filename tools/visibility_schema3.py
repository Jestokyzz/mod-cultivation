"""Schema-3 stock restoration, display-only records and generated TalentUI data."""
from __future__ import annotations

import json
from pathlib import Path
import re
import struct
import tooltip_stock as tooltip

ROOT = Path(__file__).resolve().parents[1]
TEXT_FIELDS = (136, 153, 170, 187)
_SOURCES = {}


def source(g, manifest, key, fields):
    info = manifest['stock_sources'][key]
    path = ROOT / info['path']
    key = (str(path), info['sha256'], fields)
    if key in _SOURCES:
        return _SOURCES[key]
    if g.sha256(path) != info['sha256']:
        raise ValueError(f'Stock source hash changed: {key}')
    rows, strings = g.load_dbc(path, fields)
    _SOURCES[key] = ({row[0]: row for row in rows}, strings)
    return _SOURCES[key]


def restore_stock(g, records, strings, manifest):
    """Restore only module-owned source IDs and their explicit tooltip references.

    Official ruRU provides numeric fields and Russian strings. The pre-existing
    clean server baseline supplies enUS (ruRU official archives have no enUS text).
    All other project records remain byte-for-byte semantically unchanged.
    """
    stock, ss = source(g, manifest, 'spell', 234)
    scoped = {base for a in manifest['active_spells'] + manifest['passive_spells'] for base in a['base_spell_chain']}
    for base in tuple(scoped):
        for field in TEXT_FIELDS:
            scoped.update(int(i) for i in re.findall(r'\$(\d+)[A-Za-z]', g.read_string(ss, stock[base][field + 8])))
    original = {row[0]: row for row in records}
    audit = []
    for spell in sorted(scoped):
        if spell not in stock or spell not in original:
            raise ValueError(f'Missing stock tooltip dependency {spell}')
        target, clean = original[spell], stock[spell]
        before = list(target)
        for index, value in enumerate(clean):
            if not any(f <= index < f + 17 for f in TEXT_FIELDS):
                target[index] = value
        for field in TEXT_FIELDS:
            value = g.read_string(ss, clean[field + 8])
            if g.read_string(strings, target[field + 8]) != value:
                g.set_string(target, strings, field + 8, value)
            target[field + 16] |= 0x101
        fields = [i for i, (old, new) in enumerate(zip(before, target)) if old != new]
        if fields:
            audit.append({'spell_id': spell, 'restored_fields': fields})
    return audit


def static_passive_text(g, text, base_id, manifest, russian):
    """Resolve only audited constant passive fields; refuse dynamic expressions."""
    stock, _ = source(g, manifest, 'spell', 234)
    durations, _ = source(g, manifest, 'duration', 4)
    bound = tooltip.bind_stock_fields(text, base_id)
    def replace(match):
        parsed = tooltip.FIELD.fullmatch(match.group(0))
        if not parsed or not parsed['id']:
            raise ValueError(f'Non-constant passive token {match.group(0)}')
        row = stock[int(parsed['id'])]
        field = parsed['field']
        if field.lower().startswith(('s', 'm')) and field[1:].isdigit():
            index = int(field[1:]) - 1
            if index not in range(3) or row[77 + index] or row[104 + index]:
                raise ValueError('Level/combo-dependent passive must not be flattened')
            amount = struct.unpack('<i', struct.pack('<I', row[80 + index]))[0]
            return str(abs(amount + (1 if row[74 + index] else 0)))
        if field.lower() == 'h':
            return str(row[35])
        if field.lower() == 'n':
            return str(row[36])
        if field.lower() == 'd':
            duration = durations[row[40]][1]
            if duration >= 0x80000000:
                raise ValueError('Infinite passive duration cannot be formatted as seconds')
            return f'{duration / 1000:g} ' + ('сек' if russian else 'sec')
        raise ValueError(f'Unsupported constant passive token {match.group(0)}')
    result = tooltip.ATOM.sub(replace, bound)
    if '$' in result:
        raise ValueError(f'Unresolved passive syntax: {result}')
    return result


def patch_display_records(g, records, strings, manifest, russian):
    by_id = {row[0]: row for row in records}
    locale, locale_id = ('ruRU', 8) if russian else ('enUS', 0)
    abilities = {a['logical_name']: a for a in manifest['active_spells'] + manifest['passive_spells']}
    generated = []
    for item in manifest['display_passives']:
        base = by_id[item['base_spell']]
        if item['spell_id'] in by_id:
            raise ValueError('Duplicate display ID')
        row = list(base)
        row[0] = item['spell_id']
        # Preserve compatible stock record schema, but no aura/proc/damage survives.
        for index in range(3):
            g.clear_effect(row, index)
        row[4] = (row[4] | 0x40) & ~0x80
        row[9] &= ~0x18000400
        for index in (1, 2, 3, 28, 29, 30, 34, 35, 36, 39, 40, 41, 42, 43, 44, 45,
                      49, 131, 132, 204, 205, 206, 208, 209, 210, 211, 212, 213, 232):
            row[index] = 0
        row[68], row[69], row[70] = 0xFFFFFFFF, 0, 0
        row[133:135] = by_id[item['icon_source_spell']][133:135]
        icon_id = item.get('icon_id')
        if not icon_id and item['logical_name'] in abilities:
            icon_id = g.path_icon_id(manifest, item['logical_name'], item['path'])
        if icon_id:
            row[133] = icon_id
        if item['talent_required']:
            name = g.read_string(strings, base[136 + locale_id])
            if item.get('copy_description_from_mechanic') or item['path'] == 'sha':
                mechanic = by_id.get(item['mechanic_spell'])
                if not mechanic:
                    raise ValueError(f'Missing display tooltip mechanic {item["mechanic_spell"]}')
                text = g.read_string(strings, mechanic[170 + locale_id])
                if not text:
                    raise ValueError(f'Empty display tooltip mechanic {item["mechanic_spell"]}/{locale}')
                if item['path'] == 'sha':
                    # Display rows have no effect fields. Resolve the already
                    # selected mechanic's audited stock references, not stock+delta.
                    text = static_passive_text(g, text, item['base_spell'], manifest, russian)
            else:
                standard = static_passive_text(g, g.read_string(strings, base[170 + locale_id]), base[0], manifest, russian)
                addition = abilities[item['logical_name']]['descriptions'][locale][item['path']]
                addition = addition.replace('{rank}', str(item['rank'])).replace('{chance}', str(item['rank'] * 20))
                text = tooltip.compose(standard, addition, manifest['path_icons'][item['path'] + '_color'])
        else:
            name, text = item['names'][locale], tooltip.player_text(item['descriptions'][locale])
        for field, value in ((136, name), (153, g.rank_text('', 1, 1, item['path'], russian)), (170, text), (187, text)):
            g.set_string(row, strings, field + locale_id, value)
            row[field + 16] |= 0x101
        records.append(row)
        by_id[row[0]] = row
        generated.append({**item, 'section': 'display_passives', 'visible': True, 'icon_id': row[133],
                          'spell_family_name': row[208], 'spell_family_flags': row[209:212], 'script_name': ''})
    return generated


def patch_display_skill(g, records, manifest):
    by_spell = {row[2]: row for row in records}
    used = {row[0] for row in records}
    added = []
    next_id = max(row[0] for row in records if 31000 <= row[0] < 32000) + 1
    for item in manifest['display_passives']:
        if item['spell_id'] in by_spell:
            raise ValueError('Display SkillLineAbility duplicate')
        row = list(by_spell[item['base_spell']])
        if next_id in used or next_id >= 32000:
            raise ValueError('Display SkillLineAbility collision')
        row[0], row[1], row[2] = next_id, item['skill_line'], item['spell_id']
        row[3:14] = [0, 8, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        records.append(row)
        added.append({'id': next_id, 'spell_id': row[2], 'skill_line': row[1]})
        next_id += 1
    return added


def merge_locales(g, client, cs, server, ss, manifest):
    c = {row[0]: row for row in client}
    s = {row[0]: row for row in server}
    for spell in c:
        if not manifest['spell_id_range']['first'] <= spell <= manifest['spell_id_range']['last']:
            continue
        for field in TEXT_FIELDS:
            g.set_string(c[spell], cs, field, g.read_string(ss, s[spell][field]))
            g.set_string(s[spell], ss, field + 8, g.read_string(cs, c[spell][field + 8]))
            c[spell][field + 16] |= 0x101
            s[spell][field + 16] |= 0x101


def technical_presentation(g, row, logical, strings, by_id, manifest, russian):
    item = manifest['technical_presentation'][logical]
    if item['visibility'] == 'hidden':
        row[4] |= 0x80
        return
    row[4] &= ~0x80
    row[9] &= ~0x18000400
    if item.get('preserve_validated_presentation'):
        return
    locale, index = ('ruRU', 8) if russian else ('enUS', 0)
    base = by_id[item['icon_source_spell']]
    row[133:135] = base[133:135]
    if item.get('icon_id'):
        row[133] = item['icon_id']
    name = item['names'][locale] or g.read_string(strings, base[136 + index])
    if not name:
        raise ValueError(f'Missing visible technical name: {logical}/{locale}')
    text = tooltip.player_text(item['descriptions'][locale])
    for field, value in ((136, name), (153, g.rank_text('', 1, 1, item['path'], russian)), (170, text), (187, text)):
        g.set_string(row, strings, field + index, value)
        row[field + 16] |= 0x101
    if logical == 'sha_combat_potency_haste':
        values = manifest['balance']['combat_potency']
        g.set_effect(row, 0, 138, values['sha_haste_percent'])
        row[49] = values['sha_max_stacks']
        durations, _ = source(g, manifest, 'duration', 4)
        if durations[row[40]][1] != values['sha_haste_duration_ms']:
            raise ValueError('Combat Potency duration differs from manifest')


def generate_variables(g, manifest, destinations):
    stock, ss = source(g, manifest, 'spell', 234)
    variables, strings = source(g, manifest, 'variables', 2)
    strings = bytearray(strings)
    rows = list(variables.values())
    for base_id, variable_id in manifest['stock_scoped_variables'].items():
        if variable_id in variables:
            raise ValueError('DescriptionVariables collision')
        text = g.read_string(strings, variables[stock[int(base_id)][232]][1])
        text = tooltip.bind_stock_fields(text, int(base_id), definitions=True)
        tooltip.validate_variables('', text)
        rows.append([variable_id, g.add_string(strings, text)])
    for dest in destinations:
        g.write_dbc(dest / 'SpellDescriptionVariables.dbc', sorted(rows), strings)


def _path_fragment(text, color):
    """Turn source-only path markers into an inline yellow/path-color fragment."""
    clean = tooltip.player_text(text.strip())
    if clean.count(tooltip.PATH_OPEN) != clean.count(tooltip.PATH_CLOSE):
        raise ValueError(f'Unbalanced TalentUI path markers: {text!r}')
    return clean.replace(tooltip.PATH_OPEN, f'|r|cff{color}').replace(
        tooltip.PATH_CLOSE, f'|r|cff{tooltip.STOCK_COLOR}')


def _talent_fallback_patch(g, manifest, ability, base_id, path, locale):
    """Build a cache-independent patch over the native rendered stock line.

    Most talent descriptions can be fully resolved at build time.  The few
    descriptions containing native variables/plural grammar retain the stock
    line rendered by the client and apply only audited constant replacements
    plus the path addition.
    """
    color = manifest['path_icons'][path + '_color']
    inline = (manifest.get('tooltip_inline_edits', {})
              .get(ability['logical_name'], {}).get(locale, {}).get(path))
    replacements = []
    if inline and inline.get('native_only'):
        # Damage formulas/variables belong to the native DBC formatter. A legacy
        # Lua fallback cannot safely reproduce them: keep the already-generated
        # native talent description and explicitly omit its text transformation.
        return {'replacements': [], 'addition': '', 'separator': ' ', 'native_only': True}
    if inline:
        for replacement in inline.get('replace', []):
            if replacement.get('regex', False):
                raise ValueError(
                    f'Unresolved TalentUI description cannot use a regex patch: '
                    f'{ability["logical_name"]}/{locale}/{path}/{base_id}')
            new = replacement.get('new')
            if 'new_by_rank' in replacement:
                choices = replacement['new_by_rank']
                rank = ability['base_spell_chain'].index(base_id)
                new = choices[rank]
            if new is None:
                raise ValueError('TalentUI replacement has no output')
            old = static_passive_text(g, replacement['old'], base_id, manifest, locale == 'ruRU')
            replacements.append({'old': old, 'new': _path_fragment(new, color)})
        addition = inline.get('addition', ability['descriptions'][locale][path])
        rank = ability['base_spell_chain'].index(base_id) + 1
        addition = addition.replace('{rank}', str(rank)).replace('{chance}', str(rank * 20))
        separator = inline.get('addition_separator', ability.get('tooltip_addition_separator', ' '))
    else:
        rank = ability['base_spell_chain'].index(base_id) + 1
        addition = ability['descriptions'][locale][path]
        addition = addition.replace('{rank}', str(rank)).replace('{chance}', str(rank * 20))
        separator = ability.get('tooltip_addition_separator', ' ')
    if separator not in (' ', '\n'):
        raise ValueError(f'Invalid TalentUI addition separator: {separator!r}')
    return {'replacements': replacements,
            'addition': tooltip.player_text(addition.strip()), 'separator': separator}


def write_ui_data(g, manifest, generated_spell_rows, generated_spell_strings):
    def lua(value):
        if isinstance(value, str):
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, bool):
            return 'true' if value else 'false'
        if isinstance(value, (float, int)):
            return str(value)
        if isinstance(value, list):
            return '{' + ','.join(lua(i) for i in value) + '}'
        if isinstance(value, dict):
            return '{' + ','.join('[' + lua(k) + ']=' + lua(v) for k, v in value.items()) + '}'
        raise ValueError('Unsupported Lua data')
    abilities = {a['logical_name']: a for a in manifest['active_spells'] + manifest['passive_spells']}
    by_spell = {row[0]: row for row in generated_spell_rows}
    spell_paths = {}
    logical_by_spell = {}
    metadata_highlights = {}
    path_probes = {'celestial': [], 'sha': []}
    for ability in manifest['active_spells']:
        for path in ('celestial', 'sha'):
            path_probes[path].extend(ability[path + '_first'] + rank
                                     for rank in range(len(ability['base_spell_chain'])))
    for ability in abilities.values():
        for path in ('celestial', 'sha'):
            for rank in range(len(ability['base_spell_chain'])):
                spell_id = ability[path + '_first'] + rank
                spell_paths[spell_id] = path
                logical_by_spell[spell_id] = ability['logical_name']
                if ability in manifest['active_spells']:
                    base = by_spell[ability['base_spell_chain'][rank]]
                    custom = by_spell[spell_id]
                    changed = {}
                    if custom[42] != base[42]:
                        changed['energy'] = True
                    if custom[29:31] != base[29:31]:
                        changed['cooldown'] = True
                    if custom[46] != base[46]:
                        changed['range'] = True
                    if changed:
                        metadata_highlights[spell_id] = changed
    for item in manifest['display_passives']:
        spell_paths[item['spell_id']] = item['path']
    for logical, item in manifest['technical_presentation'].items():
        if item['visibility'] == 'visible':
            spell_paths[manifest['technical_spells'][logical]] = item['path']
    talent_data = {}
    talent_positions = {}
    talent_tabs = {tab_id: index + 1 for index, tab_id in enumerate(manifest['talent_ui']['tab_order'])}
    for item in manifest['talent_ui']['mappings']:
        tab_index = talent_tabs[item['tab_id']]
        position = f"{tab_index}:{item['tier'] + 1}:{item['column'] + 1}"
        if position in talent_positions:
            raise ValueError(f'Duplicate talent position {position}')
        talent_positions[position] = item['talent_id']
        ability = abilities[item['logical_name']]
        descriptions = ability['descriptions']
        icons = {path: 'Interface\\Icons\\JC_RoguePaths\\' + path + '_' + item['logical_name']
                 for path in ('celestial', 'sha')}
        variants = {path: [ability[path + '_first'] + rank for rank in range(len(item['rank_spells']))]
                    for path in ('celestial', 'sha')}
        tooltips = {locale: {path: [] for path in ('celestial', 'sha')}
                    for locale in ('ruRU', 'enUS')}
        tooltip_patches = {locale: {path: [] for path in ('celestial', 'sha')}
                           for locale in ('ruRU', 'enUS')}
        for locale, locale_index, russian in (('ruRU', 8, True), ('enUS', 0, False)):
            for path in ('celestial', 'sha'):
                for rank, base_id in enumerate(item['rank_spells']):
                    custom_id = variants[path][rank]
                    custom = g.read_string(generated_spell_strings,
                                           by_spell[custom_id][170 + locale_index])
                    try:
                        resolved = static_passive_text(g, custom, base_id, manifest, russian)
                        tooltips[locale][path].append(resolved)
                        tooltip_patches[locale][path].append(False)
                    except ValueError:
                        tooltips[locale][path].append(False)
                        tooltip_patches[locale][path].append(
                            _talent_fallback_patch(g, manifest, ability, base_id, path, locale))
        talent_data[item['talent_id']] = {**item, 'tab_index': tab_index,
            'icons': icons, 'variants': variants, 'descriptions': {
            locale: {path: tooltip.player_text(text) for path, text in texts.items()}
            for locale, texts in descriptions.items()}, 'tooltips': tooltips,
            'tooltip_patches': tooltip_patches}
    by_name = {a['logical_name']: a for a in manifest['active_spells']}
    rogue_control_auras = set()
    for logical in ('cheap_shot', 'kidney_shot', 'sap', 'blind', 'gouge'):
        ability = by_name[logical]
        rogue_control_auras.update(ability['base_spell_chain'])
        for path in ('celestial', 'sha'):
            rogue_control_auras.update(ability[path + '_first'] + rank
                                       for rank in range(len(ability['base_spell_chain'])))
    dynamic = {
        'celestial_preparation': by_name['preparation']['celestial_first'],
        'celestial_shadow_dance': by_name['shadow_dance']['celestial_first'],
        'preparation_base': ['cold_blood', 'shadowstep', 'vanish', 'evasion', 'sprint'],
        'preparation_glyph': ['dismantle', 'kick', 'blade_flurry'],
        'preparation_glyph_aura': 56819,
        'deadly_poison_auras': [2818, 2819, 11353, 11354, 25349, 26968, 27187, 57969, 57970],
        'rogue_control_auras': sorted(rogue_control_auras),
    }
    data = {'schema': manifest['schema_version'], 'presentation': 6, 'spell_paths': spell_paths,
            'logical_by_spell': logical_by_spell, 'metadata_highlights': metadata_highlights,
            'path_probes': path_probes,
            'dynamic': dynamic,
            'markers': {'celestial': manifest['technical_spells']['celestial_path_passive'],
            'sha': manifest['technical_spells']['sha_path_passive']}, 'colors': {p: manifest['path_icons'][p + '_color'] for p in ('celestial', 'sha')},
            'talent_positions': talent_positions, 'talents': talent_data}
    output = ROOT / 'client_patch/addon/RoguePathsUI/RoguePathsTalentData.lua'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('-- Generated from cultivation_rogue_spell_manifest.json; do not edit.\nRoguePathsTalentData = ' + lua(data) + '\n', encoding='utf-8')
