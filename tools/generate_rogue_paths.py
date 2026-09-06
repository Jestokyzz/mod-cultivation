from __future__ import annotations

import argparse
import hashlib
import json
from path_descriptions_en import DESCRIPTIONS as PATH_DESCRIPTIONS_EN
import re
import struct
import seven_spell_data as seven
import celestial_spell_data as celestial
import celestial_aura_tooltips
import sha_aura_tooltips
import visibility_schema3 as visibility
import tooltip_stock
import sys
from shadowstep_clone_sql import SQL as SHADOWSTEP_CLONE_SQL
from pathlib import Path
from typing import Any


HEADER = struct.Struct("<4s4I")
SPELL_FIELDS = 234
SKILL_LINE_ABILITY_FIELDS = 14
SPELL_NAME = 136
SPELL_RANK = 153
SPELL_DESCRIPTION = 170
SPELL_TOOLTIP = 187

# SpellFamilyFlags word 2 is unused by every stock/custom Rogue spell in the
# validated 3.3.5a baseline.  Mark only the three Celestial glyph additions so
# their conditional Preparation spell modifier cannot also match Ghostly Strike
# through Blade Flurry's shared word-0 family bit.
PREPARATION_GLYPH_FAMILY_MARKER = 0x00000001
PREPARATION_BASE_FAMILY_MASK = [0x00000860, 0x00000240, 0]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_dbc(path: Path, expected_fields: int) -> tuple[list[list[int]], bytearray]:
    data = path.read_bytes()
    magic, count, fields, record_size, string_size = HEADER.unpack_from(data)
    if magic != b"WDBC" or fields != expected_fields or record_size != fields * 4:
        raise ValueError(f"Unexpected DBC schema: {path}")
    records = [
        list(struct.unpack_from(f"<{fields}I", data, HEADER.size + index * record_size))
        for index in range(count)
    ]
    string_start = HEADER.size + count * record_size
    strings = bytearray(data[string_start:string_start + string_size])
    if len(strings) != string_size or not strings.endswith(b"\0"):
        raise ValueError(f"Invalid string block: {path}")
    return records, strings


def write_dbc(path: Path, records: list[list[int]], strings: bytearray) -> None:
    if not records:
        raise ValueError(f"Refusing to write empty DBC: {path}")
    fields = len(records[0])
    if any(len(row) != fields for row in records):
        raise ValueError(f"Inconsistent record width: {path}")
    body = b"".join(struct.pack(f"<{fields}I", *row) for row in records)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(HEADER.pack(b"WDBC", len(records), fields, fields * 4, len(strings)) + body + strings)


def read_string(strings: bytearray, offset: int) -> str:
    if offset == 0:
        return ""
    end = strings.find(b"\0", offset)
    if end < 0:
        raise ValueError(f"Invalid string offset: {offset}")
    return bytes(strings[offset:end]).decode("utf-8")


def add_string(strings: bytearray, value: str) -> int:
    offset = len(strings)
    strings.extend(value.encode("utf-8") + b"\0")
    return offset


def set_string(row: list[int], strings: bytearray, field: int, value: str) -> None:
    row[field] = add_string(strings, value)


def signed(value: int) -> int:
    return value & 0xFFFFFFFF


def set_effect(row: list[int], index: int, aura: int, amount: int, target: int = 1, amplitude: int = 0) -> None:
    row[71 + index] = 6  # SPELL_EFFECT_APPLY_AURA
    row[74 + index] = 1  # CalcValue adds one; BasePoints stores amount - 1.
    row[77 + index] = 0
    row[80 + index] = signed(amount - 1)
    row[83 + index] = 0
    row[86 + index] = target
    row[89 + index] = 0
    row[92 + index] = 0
    row[95 + index] = aura
    row[98 + index] = amplitude
    row[101 + index] = 0
    row[104 + index] = 0
    row[107 + index] = 0
    row[110 + index] = 0
    row[113 + index] = 0
    row[116 + index] = 0
    row[119 + index] = 0
    row[122 + index * 3:125 + index * 3] = [0, 0, 0]


def clear_effect(row: list[int], index: int) -> None:
    row[71 + index] = 0
    row[74 + index] = 0
    row[77 + index] = 0
    row[80 + index] = 0
    row[83 + index] = 0
    row[86 + index] = 0
    row[89 + index] = 0
    row[92 + index] = 0
    row[95 + index] = 0
    row[98 + index] = 0
    row[101 + index] = 0
    row[104 + index] = 0
    row[107 + index] = 0
    row[110 + index] = 0
    row[113 + index] = 0
    row[116 + index] = 0
    row[119 + index] = 0
    row[122 + index * 3:125 + index * 3] = [0, 0, 0]


def expanded_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for section in ("active_spells", "passive_spells"):
        for ability in manifest[section]:
            bases = ability["base_spell_chain"]
            for rank, base_spell in enumerate(bases, 1):
                expanded.append({
                    **ability,
                    "section": section,
                    "rank": rank,
                    "base_spell": base_spell,
                    "celestial_spell": ability["celestial_first"] + rank - 1,
                    "sha_spell": ability["sha_first"] + rank - 1,
                })
    # Keep all v1 SkillLineAbility IDs stable when new active chains precede old passives in the manifest.
    expanded.sort(key=lambda entry: bool(entry.get('seven_extension')))
    return expanded


def validate_manifest(manifest: dict[str, Any], spell_ids: set[int], skill_rows: list[list[int]]) -> list[dict[str, Any]]:
    entries = expanded_entries(manifest)
    allocated: dict[int, str] = {}
    first = manifest["spell_id_range"]["first"]
    last = manifest["spell_id_range"]["last"]
    for entry in entries:
        if entry["base_spell"] not in spell_ids:
            raise ValueError(f"Missing base spell {entry['base_spell']} for {entry['logical_name']}")
        for path_key in ("celestial_spell", "sha_spell"):
            spell_id = entry[path_key]
            if not first <= spell_id <= last:
                raise ValueError(f"Spell ID outside reserved range: {spell_id}")
            if spell_id in spell_ids:
                raise ValueError(f"Spell ID collides with baseline: {spell_id}")
            if spell_id in allocated:
                raise ValueError(f"Duplicate spell ID {spell_id}: {allocated[spell_id]} and {entry['logical_name']}")
            allocated[spell_id] = entry["logical_name"]

    for logical_name, spell_id in manifest["technical_spells"].items():
        if not first <= spell_id <= last:
            raise ValueError(f"Technical Spell ID outside reserved range: {logical_name}={spell_id}")
        if spell_id in spell_ids or spell_id in allocated:
            raise ValueError(f"Technical Spell ID collision: {logical_name}={spell_id}")
        allocated[spell_id] = logical_name

    skill_spells = {row[2] for row in skill_rows}
    missing_skill = sorted({entry["base_spell"] for entry in entries if entry["visible"] and entry["base_spell"] not in skill_spells})
    if missing_skill:
        raise ValueError(f"Visible base spells missing from SkillLineAbility: {missing_skill}")
    return entries


def rank_text(base_rank: str, rank: int, rank_count: int, path: str, russian: bool) -> str:
    label = "Небожитель" if path == "celestial" and russian else "Ша" if russian else "Celestial" if path == "celestial" else "Sha"
    return label


def path_prefix(path: str, russian: bool) -> str:
    return rank_text('', 1, 1, path, russian)


def path_icon_id(manifest: dict[str, Any], logical_name: str, path: str) -> int:
    all_abilities = manifest['active_spells'] + manifest['passive_spells']
    ability = next(a for a in all_abilities if a['logical_name'] == logical_name)
    if 'custom_icon_ids' in ability:
        return ability['custom_icon_ids'][path]
    if ability['icon_source'] == 'stock_base_rank':
        return ability['icon_id']
    raise ValueError('Explicit custom icon allocation required: ' + logical_name)


def composed_path_tooltip(base_text: str, addition: str, path: str, russian: bool,
                          manifest: dict[str, Any], separator: str = ' ') -> str:
    color = manifest['path_icons'][path + '_color']
    return tooltip_stock.compose(base_text, addition, color, separator)


def generated_path_tooltip(entry: dict[str, Any], base_text: str, addition: str,
                           path: str, locale: str, manifest: dict[str, Any],
                           *, base_spell: int | None = None) -> str:
    exact = entry.get('full_descriptions', {}).get(locale, {}).get(path)
    if exact is not None:
        return tooltip_stock.exact(exact.replace('{rank}', str(entry['rank'])).replace('{chance}', str(entry['rank'] * 20)),
                                   manifest['path_icons'][path + '_color'])
    inline = (manifest.get('tooltip_inline_edits', {})
              .get(entry['logical_name'], {}).get(locale, {}).get(path))
    if inline is not None and base_spell is not None:
        edited = tooltip_stock.unbind_own_fields(base_text, base_spell)
        matched_any = False
        fallback_additions: list[str] = []
        for replacement in inline.get('replace', []):
            old = replacement['old']
            new = replacement.get('new')
            if 'new_by_rank' in replacement:
                choices = replacement['new_by_rank']
                rank_count = len(entry['base_spell_chain'])
                if len(choices) != rank_count:
                    raise ValueError(
                        f'Inline tooltip rank map changed for {entry["logical_name"]}/{locale}/{path}: '
                        f'expected {rank_count}, found {len(choices)}')
                new = choices[entry['rank'] - 1]
            if new is None:
                raise ValueError(f'Inline tooltip replacement has no output for {entry["logical_name"]}/{locale}/{path}')
            # Inline replacements are part of the final player-facing text too.
            # Resolve per-rank placeholders here, before re.subn/str.replace;
            # otherwise the literal token is copied into both the custom spell
            # and the native 0/N talent branch that uses it as its source.
            new = new.replace('{rank}', str(entry['rank'])).replace('{chance}', str(entry['rank'] * 20))
            expected = replacement.get('count', 1)
            if replacement.get('regex', False):
                replaced, actual = re.subn(old, new, edited)
            else:
                actual = edited.count(old)
                replaced = edited.replace(old, new)
            if actual == 0 and replacement.get('optional', False):
                if replacement.get('fallback_addition'):
                    fallback_additions.append(replacement['fallback_addition'])
                continue
            if actual != expected:
                raise ValueError(
                    f'Inline tooltip source changed for {entry["logical_name"]}/{locale}/{path}/stock-{base_spell}: '
                    f'{old!r} expected {expected}, found {actual}; source={edited!r}')
            edited = replaced
            matched_any = True
        edited = tooltip_stock.bind_stock_fields(edited, base_spell)
        delta_source = inline.get('addition', addition)
        if not matched_any and 'addition_when_unmatched' in inline:
            delta_source = inline['addition_when_unmatched']
        if fallback_additions:
            delta_source = ' '.join([*fallback_additions, delta_source]).strip()
        delta = delta_source.replace('{rank}', str(entry['rank'])).replace('{chance}', str(entry['rank'] * 20)).strip()
        if delta:
            separator = inline.get('addition_separator', entry.get('tooltip_addition_separator', ' '))
            if separator not in (' ', '\n'):
                raise ValueError(f'Invalid tooltip addition separator: {separator!r}')
            edited = edited.rstrip() + separator + '{path}' + delta + '{/path}'
        return tooltip_stock.exact(edited, manifest['path_icons'][path + '_color'])
    if base_spell is not None:
        base_text = tooltip_stock.bind_stock_fields(base_text, base_spell)
    return composed_path_tooltip(base_text, addition, path, locale == 'ruRU', manifest,
                                 entry.get('tooltip_addition_separator', ' '))


def patch_active_fields(row: list[int], logical_name: str, path: str) -> None:
    seven.patch_active(sys.modules[__name__], row, logical_name, path)
    celestial = path == "celestial"
    if celestial and logical_name in ("dismantle", "kick", "blade_flurry"):
        row[211] |= PREPARATION_GLYPH_FAMILY_MARKER
    if logical_name == "vanish" and not celestial:
        row[29] = max(0, row[29] - 45000)
        row[30] = max(0, row[30] - 45000)
    elif logical_name == "sprint" and not celestial:
        row[40] = 31
        row[80] = 99
    elif logical_name == "evasion":
        row[40] = 18 if celestial else 31
        if not celestial:
            row[29] = 120000
            row[30] = 120000
    elif logical_name == "cloak_of_shadows":
        row[40] = 35 if celestial else 27
        if celestial:
            row[80] = signed(-101)
        if not celestial:
            row[29] = 60000
            row[30] = 60000
    elif logical_name == "feint":
        row[42] = 20 if celestial else 0
        row[40] = 31 if celestial else 27
        for index in range(3):
            if row[95 + index] == 229:
                clear_effect(row, index)  # The path guard replaces, never stacks with, stock AoE avoidance.
    elif logical_name == "kick" and celestial:
        row[40] = 32
    elif logical_name == "gouge":
        if celestial:
            row[4] |= 0x00200000
        else:
            row[40] = 66
    elif logical_name == "expose_armor" and not celestial:
        row[80] = signed(-36)  # CalcValue adds one: -35% armor.
    elif logical_name == "rupture" and not celestial:
        row[98] = 1200
    elif logical_name == "slice_and_dice" and not celestial:
        row[81] = 59
    elif logical_name == "deadly_throw" and celestial:
        row[46] = 5  # SpellRange: 40 yards, not BaseLevel
    elif logical_name == "fan_of_knives" and celestial:
        row[92] = 32  # EffectRadiusIndex: 12 yards, not EffectDieSides
    elif logical_name == "fan_of_knives" and not celestial:
        row[42] = 70
    elif logical_name == "dismantle" and not celestial:
        row[40] = 32
    elif logical_name == "hunger_for_blood":
        row[42] = 0 if celestial else 30
        row[40] = 4 if celestial else 29
        if not celestial:
            row[29] = 30000
            row[30] = 30000
            row[80] = 11
    elif logical_name == "cold_blood":
        clear_effect(row, 0)
        set_effect(row, 0, 4, 1)
        row[40] = 0
    elif logical_name == "envenom":
        if not celestial:
            clear_effect(row, 1)
            clear_effect(row, 2)
        else:
            # SpellMgr swaps stock Envenom's effects 0/2 before processing
            # doses. Custom IDs need the same ordering in the generated DBC.
            for field in range(71, 122, 3):
                row[field], row[field + 2] = row[field + 2], row[field]
            row[122:125], row[128:131] = row[128:131], row[122:125]
            row[216], row[218] = row[218], row[216]
            row[231], row[233] = row[233], row[231]
    elif logical_name == "blade_flurry":
        row[40] = 18 if celestial else 31
        row[80] = 29 if celestial else 49
    elif logical_name == "adrenaline_rush":
        row[40] = 18 if celestial else 1
        row[80] = 99 if celestial else 199
    elif logical_name == "killing_spree":
        if celestial:
            row[29] = max(0, row[29] - 30000)
            row[30] = max(0, row[30] - 30000)
        else:
            row[40] = 551
            row[4] |= 0x80000000
    elif logical_name == "riposte":
        if celestial:
            row[81] = signed(-31)
        else:
            clear_effect(row, 1)
    elif logical_name == "hemorrhage":
        # Visible caster-owned charges; the script supplies the physical bonus
        # without native MOD_DAMAGE_TAKEN stacking across different rogues.
        row[95 + 2] = 4  # DUMMY, retain the base-rank amount in effect 2.
        row[4] |= 0x04000000  # Explicit negative aura; DUMMY alone is not negative.
        if not celestial:
            row[82] = (row[82] + 1) * 3 - 1
        row[40] = 3  # 60 seconds.
        row[34] = 0x8 | 0x20 | 0x80 | 0x200  # taken melee/ranged auto/spell hits
        row[35] = 100
        row[36] = 20 if celestial else 5
    elif logical_name == "kidney_shot" and not celestial:
        row[40] = 187  # Native 0..5 seconds interpolated by CP, before DR.
    elif logical_name == "ambush" and not celestial:
        row[42] += 15
    elif logical_name == "garrote" and not celestial:
        row[98] = 1500
    elif logical_name == "shadowstep":
        row[42] = 0 if celestial else 20
        row[29] = 30000
        row[30] = 30000
        if celestial:
            # TARGET_UNIT_TARGET_ANY keeps the native unit-target teleport and
            # safety/LoS checks while permitting both friendly and hostile units.
            row[86] = 25
        else:
            row[46] = 35
    elif logical_name == "preparation" and not celestial:
        row[29] = 390000
        row[30] = 390000
    elif logical_name == "preparation" and celestial:
        # A real native percentage spell modifier is required here.  Both the
        # client tooltip and the server calculate the reduced base cooldown
        # before the spell is cast; an after-cast cooldown packet is not the
        # Preparation mechanic.
        row[4] |= 0x000000C0
        for index in (28, 29, 30, 34, 40, 42):
            row[index] = 0
        for index in range(3):
            clear_effect(row, index)
        set_effect(row, 0, 108, -30)  # SPELL_AURA_ADD_PCT_MODIFIER
        row[110] = 11  # SPELLMOD_COOLDOWN
        row[122:125] = PREPARATION_BASE_FAMILY_MASK
    elif logical_name == "shadow_dance":
        row[40] = 1 if celestial else 28
    elif logical_name == "premeditation" and celestial:
        row[80] = 2
        row[81] = 2  # RETAIN_COMBO_POINTS removes the same three points on expiry.
        row[40] = 9  # Native 30-second duration, shared by client and server.
    elif logical_name == "premeditation":
        row[40] = 32  # One native six-second retention, never a second timer.


TECH_DURATIONS = {
    "celestial_preparation_glyph_cooldown": 0,
    "celestial_finisher_regen": 39,
    "celestial_finisher_guard": 32,
    "sha_blood_thrill": 32,
    "sha_blood_thrill_icd": 18,
    "sha_vanish_exposure": 32,
    "sha_sprint_exhaustion": 27,
    "celestial_sprint_immunity": 35,
    "sha_evasion_haste": 27,
    "celestial_cloak_guard": 35,
    "sha_feint_discount": 27,
    "sha_kick_mark": 32,
    "celestial_kidney_guard": 35,
    "sha_kidney_mark": 32,
    "celestial_fan_guard": 35,
    "celestial_dismantle_guard": 32,
    "sha_dismantle_mark": 32,
    "sha_hunger_penalty": 32,
    "sha_overkill_bonus": 31,
    "sha_overkill_penalty": 35,
    "sha_cold_blood_exposure": 32,
    "sha_master_poisoner_window": 35,
    "sha_combat_potency_haste": 35,
    "celestial_adrenaline_max_energy": 18,
    "sha_adrenaline_penalty": 35,
    "celestial_killing_spree_guard": 28,
    "sha_killing_spree_exposure": 35,
    "sha_riposte_haste": 32,
    "sha_expose_armor_mark": 1,
    "celestial_hemorrhage_charges": 3,
    "sha_hemorrhage_charges": 3,
    "celestial_ambush_guard": 32,
    "sha_garrote_window": 32,
    "sha_shadowstep_damage": 1,
    "celestial_cheat_death_guard": 35,
    "celestial_cheat_death_heal": 35,
    "sha_cheat_death_damage": 39,
    "sha_honor_rate_limit": 36,
    "celestial_eviscerate_armor": 36,
    "sha_garrote_eviscerate_armor": 32,
    "sha_expose_armor_ignore": 1,
    "celestial_stealth_mastery": 21,
    "sha_stealth_window": 27,
    "sha_vanish_window": 27,
    "celestial_gouge_protection": 65,
    "sha_gouge_protection": 65,
    "celestial_deadly_throw_lockout": 27,
    "sha_deadly_throw_blade": 36,
    "sha_fan_extra_attack": 36,
    "celestial_blade_flurry_copy": 36,
    "sha_sinister_extra_attack": 36,
    "celestial_premeditation_timer": 9,
    "sha_premeditation_timer": 32,
    "sha_cold_blood_window": 21,
    "celestial_tricks_boost": 1,
    "sha_tricks_boost": 35,
    "sha_hunger_buff": 29,
    "celestial_overkill_bonus": 9,
    "celestial_cold_blood_window": 21,
    "celestial_riposte_disarm": 27,
    "celestial_feint_guard": 31,
    "sha_feint_guard": 27,
    "celestial_hunger_grace": 1,
    "sha_evasion_energy_icd": 36,
    "sha_ambush_cost_marker": 21,
    "sha_shadow_dance_cost_marker": 21,
    "celestial_shadow_dance_cost_marker": 21,
    "sha_dismantle_haste": 32,
    "celestial_vanish_dot_protection": 27,
    "sha_cloak_poison_penetration": 27,
    "sha_vanish_energy": 35,
}


TECH_EFFECTS = {
    "sha_shadow_dance_cost_marker": (107, -20, 0),
    "celestial_shadow_dance_cost_marker": (107, -15, 0),
    "celestial_preparation_glyph_cooldown": (108, -30, 0),
    "celestial_finisher_regen": (24, 5, 1000),
    "celestial_finisher_guard": (87, -5, 0),
    "sha_blood_thrill": (110, 20, 0),
    "sha_sprint_exhaustion": (33, -30, 0),
    "sha_evasion_haste": (138, 5, 0),
    "sha_combat_potency_haste": (138, 5, 0),
    "celestial_adrenaline_max_energy": (35, 50, 0),
    "sha_adrenaline_penalty": (110, -50, 0),
    "celestial_killing_spree_guard": (87, -50, 0),
    "sha_killing_spree_exposure": (87, 20, 0),
    "sha_riposte_haste": (138, 25, 0),
    "celestial_cheat_death_guard": (87, -90, 0),
    "sha_cheat_death_damage": (4, 25, 0),
    "celestial_eviscerate_armor": (280, 25, 0),
    "sha_garrote_eviscerate_armor": (280, 30, 0),
    "sha_expose_armor_ignore": (280, 15, 0),
    "celestial_tricks_boost": (79, 10, 0),
    "sha_tricks_boost": (79, 25, 0),
    "sha_hunger_buff": (4, 12, 0),
    "sha_hunger_penalty": (79, -5, 0),
    "sha_overkill_bonus": (110, 100, 0),
    "sha_overkill_penalty": (110, -30, 0),
    "celestial_stealth_mastery": (154, 1, 0),
    "celestial_overkill_bonus": (110, 30, 0),
    "celestial_cold_blood_window": (4, 1, 0),
    "celestial_riposte_disarm": (67, 1, 0),
    "celestial_feint_guard": (229, -70, 0),
    "sha_feint_guard": (229, -30, 0),
    "sha_dismantle_haste": (138, 20, 0),
    "sha_cloak_poison_penetration": (270, 100, 0),
    "sha_vanish_energy": (24, 10, 1000),
}


TECH_RU_NAMES = {
    "celestial_path_passive": "Безупречный расчёт",
    "sha_path_passive": "Кровавый азарт",
    "celestial_finisher_regen": "Безупречный расчёт: энергия",
    "celestial_finisher_guard": "Безупречный расчёт: защита",
    "sha_blood_thrill": "Кровавый азарт",
    "sha_blood_thrill_icd": "Кровавый азарт: восстановление",
    "sha_deadly_throw_blade": "Смертельный бросок: дополнительный клинок",
    "sha_fan_extra_attack": "Веер клинков: дополнительный удар",
    "celestial_blade_flurry_copy": "Шквал клинков Небожителя",
    "sha_blade_flurry_copy": "Шквал клинков Ша",
    "sha_sinister_extra_attack": "Коварный удар: дополнительный удар",
    "sha_envenom_detonation": "Отравление: детонация Ша",
    "sha_cloak_poison_penetration": "Плащ Теней: неотвратимые яды",
    "sha_vanish_energy": "Исчезновение: восстановление энергии",
}

TARGETED_TECHNICAL = {
    "sha_kick_mark", "celestial_kidney_guard", "sha_kidney_mark", "celestial_fan_guard",
    "celestial_dismantle_guard", "sha_dismantle_mark", "sha_master_poisoner_window",
    "sha_expose_armor_mark", "celestial_hemorrhage_charges", "sha_hemorrhage_charges",
    "celestial_ambush_guard", "sha_garrote_window", "celestial_gouge_protection",
    "sha_gouge_protection", "celestial_deadly_throw_lockout", "celestial_riposte_disarm",
}

DERIVED_DAMAGE_SPELLS = {
    'sha_deadly_throw_blade', 'sha_fan_extra_attack', 'celestial_blade_flurry_copy',
    'sha_blade_flurry_copy', 'sha_sinister_extra_attack', 'sha_envenom_detonation',
}


# Player-facing text describes the replacement mechanics instead of inheriting
# the stock tooltip, which would be false for many path abilities.
PATH_DESCRIPTIONS_RU = {
    "stealth": ("После 3 сек. незаметности штраф скорости снимается, а уровень незаметности повышается на 1.", "Первая специальная прямая атака из незаметности или в течение 3 сек. после выхода стоит на 20 энергии меньше и наносит на 10% больше прямого урона."),
    "vanish": ("Снимает замедления, обездвиживания и одно вражеское кровотечение с наибольшей оставшейся длительностью. Вражеские DoT 3 сек. не нарушают незаметность.", "Перезарядка короче на 45 сек. Восстанавливает 40 ед. энергии за 4 сек. Первый специальный удар из незаметности получает +30% итогового критического урона, после чего разбойник 6 сек. получает на 10% больше урона."),
    "sprint": ("Снимает замедления и обездвиживания и даёт иммунитет к ним на 4 сек.; стандартные скорость и длительность сохраняются.", "Повышает скорость на 100% на 8 сек."),
    "evasion": ("Длится 20 сек.; физический урон от попавших атак уменьшается на 15%.", "Длится 8 сек., перезарядка 2 мин. Уклонение восстанавливает 5 ед. энергии."),
    "cloak_of_shadows": ("Даёт 100% избегание враждебных заклинаний на 4 сек., затем на 4 сек. уменьшает получаемый магический урон на 20%.", "Длится 3 сек., перезарядка 60 сек. Собственные яды наносят на 20% больше урона и не могут промахнуться или быть сопротивлены."),
    "feint": ("Стоит 20 энергии и на 8 сек. уменьшает получаемый AoE-урон на 70%.", "Стоит 0 энергии и на 3 сек. уменьшает AoE-урон на 30%; следующая специальная прямая атака стоит на 15 энергии меньше."),
    "kick": ("Успешное прерывание возвращает фактически потраченную энергию и продлевает блокировку школы на 1 сек.", "Успешное прерывание на 6 сек. увеличивает прямой урон этого разбойника по цели на 10%."),
    "gouge": ("Не может быть уклонён, парирован или заблокирован; длительность увеличена на 0,5 сек.", "Длится 2,5 сек. и создаёт 2 приёма серии; собственные яды и кровотечения не снимают эффект."),
    "kidney_shot": ("При 5 приёмах серии после окончания оглушения возвращает 1 приём и на 4 сек. уменьшает урон цели по разбойнику на 20%.", "Максимум 5 сек. Во время оглушения цель получает на 15% больше урона из всех источников."),
    "rupture": ("Итоговая длительность и число полноценных тиков увеличены на 40%.", "Полный стандартный урон наносится за 60% стандартной длительности при сохранении числа тиков."),
    "slice_and_dice": ("Стандартная скорость атаки; итоговая длительность увеличена на 50%.", "Скорость атаки +60%; итоговая длительность уменьшена вдвое."),
    "eviscerate": ("При 5 приёмах серии игнорирует 25% брони и после попадания восстанавливает 10 энергии.", "Может потратить до 30 дополнительной текущей энергии, повышая итоговый урон на 1% за единицу."),
    "deadly_throw": ("Дальность 40 м. При 5 приёмах серии прерывает заклинание и блокирует школу на 3 сек.", "Не прерывает. Выпускает 1 клинок раз в секунду в течение 3 сек.; каждый наносит 50% рассчитанного урона, ресурс тратится один раз."),
    "fan_of_knives": ("Радиус 12 м. Каждая поражённая цель 4 сек. наносит разбойнику на 10% меньше урона.", "Стоит 70 энергии. Каждое оружие наносит по 2 удара силой 65%; каждый удар отдельно может активировать яд."),
    "dismantle": ("После стандартного разоружения цель ещё 6 сек. наносит разбойнику на 20% меньше физического урона.", "Разоружает на 6 сек.; в это время разбойник наносит цели на 15% больше урона и получает +20% скорости атаки."),
    "tricks_of_the_trade": ("Стандартно перенаправляет угрозу; союзник получает +10% урона на 10 сек.", "Стандартно перенаправляет угрозу; союзник получает +25% урона на 4 сек."),
    "mutilate": ("Возвращает 10 ед. энергии после успешного попадания, если в начале применения на цели было 5 доз собственного Deadly Poison.", "При менее чем 5 дозах собственного Deadly Poison наносит на 20% больше прямого урона и добавляет до 2 доз после попадания. Стоимость стандартная."),
    "envenom": ("Прямой урон ниже на 10%, а стандартное окно повышения частоты наложения ядов длится вдвое дольше.", "Не создаёт стандартное окно ядов; мгновенно наносит 40% оставшегося урона собственного Deadly Poison и удаляет его дозы."),
    "hunger_for_blood": ("Стоит 10 энергии и длится 2 мин. Требует кровотечение; после исчезновения последнего кровотечения сохраняется ещё 10 сек.", "Стоит 30 энергии, перезарядка 30 сек. Требует кровотечение; даёт +12% урона на 12 сек., затем −5% урона на 6 сек."),
    "cold_blood": ("Следующий завершающий приём с 5 приёмами серии гарантированно критический и после попадания возвращает 20 энергии.", "Следующая специальная прямая атака гарантированно критическая и получает +40% итогового критического урона; затем разбойник 6 сек. получает на 10% больше урона."),
    "sinister_strike": ("Каждый третий успешный удар возвращает 10 энергии и создаёт дополнительный приём серии.", "Успешный удар с вероятностью 20% наносит дополнительный удар силой 60%, способный активировать яд."),
    "blade_flurry": ("Стандартный эффект длится на 5 сек. дольше и даёт ещё +10 процентных пунктов скорости атаки. Полный урон исходного события распределяется поровну между максимум 4 дополнительными целями.", "Длится 8 сек., даёт +50% скорости атаки, копирует 100% урона в одну цель и повышает стоимость атакующих способностей на 20%."),
    "adrenaline_rush": ("Стандартный эффект длится на 5 сек. дольше и повышает максимум энергии на 50. После окончания лишняя энергия обрезается.", "Даёт +200% восстановления энергии на 10 сек., затем -50% восстановления на 4 сек."),
    "killing_spree": ("Время восстановления стандартной способности уменьшено на 30 сек.; число атак, урон и выбор целей не изменены.", "Выполняет 7 атак с бонусом урона 30%; во время серии и 4 сек. после неё получаемый урон выше на 20%."),
    "riposte": ("Замедляет скорость атаки цели на 30% и разоружает её на 3 сек.", "Не замедляет и не разоружает; восстанавливает 20 энергии и даёт +25% скорости атаки на 6 сек."),
    "expose_armor": ("Длится 12 сек. за приём серии, до 60 сек.; при 5 приёмах после попадания возвращает 10 энергии.", "Снижает броню на 35%. Длится 2 сек. за приём серии, до 10 сек."),
    "hemorrhage": ("Прямой урон ниже на 10%; создаёт 20 персональных зарядов стандартного дополнительного урона на 60 сек.", "Прямой урон выше на 20%; создаёт 5 персональных зарядов с утроенным дополнительным уроном."),
    "ambush": ("Дальность применения увеличена на 8 м, а успешное попадание создаёт 1 дополнительный приём серии.", "Стоимость 75 ед. энергии. Наносит на 35% больше прямого урона; итоговый критический урон дополнительно усилен на 20%."),
    "garrote": ("Молчание длится на 1 сек. дольше, кровотечение — на 6 сек. дольше с дополнительными полными тиками.", "Молчание длится 1 сек.; полный урон кровотечения наносится за 9 сек. Следующий Eviscerate за 6 сек. игнорирует 30% брони."),
    "shadowstep": ("Можно применять к противнику или союзнику, кроме себя, без затрат энергии. Сохраняет незаметность и снимает эффекты замедления и сковывания.", "Только противник, дальность 35 м, перезарядка 30 сек., стоимость 20 энергии. Следующая специальная атака наносит на 40% больше прямого урона."),
    "shadow_dance": ("Длится 10 сек. Stealth-способности наносят на 20% меньше урона; Cheap Shot и Garrote стоят на 15 энергии меньше.", "Длится 5 сек.; Cheap Shot недоступен. Ambush и Backstab стоят на 20 энергии меньше и наносят на 30% больше урона."),
    "preparation": ("Пассивно уменьшает на 30% итоговое время восстановления " + "Хладнокровия, Шага сквозь тень, Исчезновения, Ускользания и Спринта. Символ подготовки также добавляет Разоружение, Пинок и Шквал клинков.", "Сбрасывает кастомные Shadow Dance, Shadowstep, Kick и Dismantle и восстанавливает 40 энергии."),
    "premeditation": ("Создаёт 3 приёма серии, сохраняющиеся 30 сек.", "Создаёт 2 приёма серии и восстанавливает 40 энергии; созданные приёмы исчезают через 6 сек., если не использованы."),
    "overkill": ("Стандартный бонус восстановления энергии после незаметности длится 30 сек.", "После незаметности даёт +100% восстановления энергии на 8 сек."),
    "seal_fate": ("Каждый приём серии, который должен был появиться сверх максимума, восстанавливает 5 ед. энергии. Не более 10 ед. энергии в секунду.", "Стандартное срабатывание получает 20% шанса за каждый изученный уровень создать 2 дополнительных приёма вместо 1; внутренний интервал усиления 2 сек."),
    "master_poisoner": ("Итоговая длительность собственных ядов увеличена на 50%.", "Собственные яды длятся вдвое меньше и накладываются на 20 процентных пунктов чаще; первое наложение Смертельного яда создаёт 4-секундное окно усиления ядов."),
    "combat_potency": ("Каждый подходящий успешный удар оружием в левой руке гарантированно восстанавливает от 1 до 5 энергии в зависимости от ранга таланта.", "Каждый подходящий успешный удар левой рукой даёт +5% скорости атаки на 4 сек., до 3 стаков, и независимо с шансом 25% восстанавливает 10 энергии."),
    "cheat_death": ("После предотвращения смерти на 4 сек. уменьшает получаемый урон на 90%, лечит 10% здоровья и уменьшает наносимый урон на 20%.", "После предотвращения смерти на 2 сек. уменьшает получаемый урон на 80%, восстанавливает 60 энергии за 2 сек., сбрасывает Shadowstep и даёт +25% урона."),
    "honor_among_thieves": ("До 2 приёмов серии сверх максимума сохраняются для той же цели и возвращаются после следующего завершающего приёма.", "Криты союзников отключены; собственная подходящая прямая критическая атака с шансом 50% создаёт приём серии, максимум 2 в секунду."),
}


TECH_DURATIONS.update(seven.DURATIONS)
TECH_EFFECTS.update(seven.EFFECTS)
TARGETED_TECHNICAL.update(seven.TARGETED)
PATH_DESCRIPTIONS_RU.update(seven.DESCRIPTIONS_RU)
PATH_DESCRIPTIONS_EN.update(seven.DESCRIPTIONS_EN)


def create_technical_spell(template: list[int], spell_id: int, logical_name: str, strings: bytearray,
                           locale_index: int, russian: bool) -> list[int]:
    row = list(template)
    row[0] = spell_id
    row[1] = 0
    row[2] = 0
    row[3] = 0
    row[29] = 0
    row[30] = 0
    row[34] = 0
    row[35] = 0
    row[36] = 0
    row[37] = 0
    row[38] = 0
    row[39] = 0
    row[40] = TECH_DURATIONS.get(logical_name, 21)
    row[41] = 0
    row[42] = 0
    row[49] = 3 if logical_name in ("sha_evasion_haste", "sha_combat_potency_haste") else 1
    row[68] = signed(-1)
    row[69] = 0
    row[70] = 0
    clear_effect(row, 0)
    clear_effect(row, 1)
    clear_effect(row, 2)
    aura, amount, amplitude = TECH_EFFECTS.get(logical_name, (4, 1, 0))
    target = 6 if logical_name in TARGETED_TECHNICAL else 21 if logical_name.endswith("tricks_boost") else 1
    set_effect(row, 0, aura, amount, target, amplitude)
    if target != 1:
        row[46] = 13  # anywhere: hidden triggered application inherits its validated parent's target
    if aura in (79, 87, 229):
        row[110] = 127  # all spell schools
    elif aura in (24, 35, 110):
        row[110] = 3  # POWER_ENERGY
    elif logical_name == 'celestial_preparation_glyph_cooldown':
        row[110] = 11  # SPELLMOD_COOLDOWN
        row[122:125] = [0, 0, PREPARATION_GLYPH_FAMILY_MARKER]
    row[131] = 0
    row[132] = 0
    row[134] = 0
    row[204] = 0
    row[205] = 0
    row[206] = 0
    row[208] = 8
    row[209:212] = [0, 0, 0]
    row[212] = 0
    row[213] = 0
    row[214] = 0
    row[225] = 1  # SchoolMask; aura stack cap is field 49.
    if logical_name == 'sha_cloak_poison_penetration':
        row[110] = 8  # Nature; never affects physical armor.
        # All player weapon poisons, Anesthetic Poison and Envenom; no
        # non-poison family bits. This removes partial damage resistance too.
        row[122:125] = [0x1001E000, 0x80018, 0]
    if logical_name in DERIVED_DAMAGE_SPELLS:
        clear_effect(row, 0)
        row[71] = 2  # SPELL_EFFECT_SCHOOL_DAMAGE, no aura and no secondary trigger.
        row[74] = 1
        row[86] = 6  # TARGET_UNIT_TARGET_ENEMY
        row[46] = 13
        row[40] = 0
        row[7] |= 0x00010000  # suppress caster procs
        row[8] |= 0x00800000  # suppress weapon procs; allowed poisons are dispatched explicitly
        if logical_name == 'sha_envenom_detonation':
            row[2] = 4  # DISPEL_POISON
            row[225] = 8  # SCHOOL_NATURE
            row[209:212] = [0x10000, 0x80000, 0]  # Own Deadly Poison-derived damage.
    if logical_name in ("celestial_path_passive", "sha_path_passive"):
        row[4] |= 0x00000040
    name = TECH_RU_NAMES.get(logical_name, logical_name.replace("_", " ").title()) if russian else logical_name.replace("_", " ").title()
    set_string(row, strings, SPELL_NAME + locale_index, name)
    set_string(row, strings, SPELL_RANK + locale_index, "")
    set_string(row, strings, SPELL_DESCRIPTION + locale_index, path_prefix("celestial" if logical_name.startswith("celestial") else "sha", russian))
    set_string(row, strings, SPELL_TOOLTIP + locale_index, name)
    seven.patch_technical(sys.modules[__name__], row, logical_name)
    if logical_name in ('sha_shadow_dance_cost_marker', 'celestial_shadow_dance_cost_marker'):
        sha = logical_name.startswith('sha_')
        set_effect(row, 0, 107, -20 if sha else -15)  # Flat native SPELLMOD_COST.
        row[110] = 14
        row[122:125] = [0x204 if sha else 0x500, 0, 0]  # Backstab/Ambush or Garrote/Cheap Shot.
    return row


def patch_spells(records: list[list[int]], strings: bytearray, entries: list[dict[str, Any]],
                 manifest: dict[str, Any], locale_index: int, russian: bool) -> list[dict[str, Any]]:
    by_id = {row[0]: row for row in records}
    generated: list[dict[str, Any]] = []
    for entry in entries:
        base = by_id[entry["base_spell"]]
        base_rank_text = read_string(strings, base[SPELL_RANK + locale_index])
        base_name = read_string(strings, base[SPELL_NAME + locale_index])
        base_description = read_string(strings, base[SPELL_DESCRIPTION + locale_index])
        rank_count = len(entry["base_spell_chain"])
        for path in ("celestial", "sha"):
            spell_id = entry[f"{path}_spell"]
            row = list(base)
            row[0] = spell_id
            if entry["section"] == "active_spells":
                patch_active_fields(row, entry["logical_name"], path)
            else:
                if entry['type'] != 'common_passive':
                    row[4] |= 0x80  # Real mechanic remains hidden; separate effect-free display below.
                if entry["logical_name"] not in ("cheat_death", "combat_potency") and not (
                    entry["logical_name"] == "seal_fate" and path == "celestial"):
                    clear_effect(row, 0)
                    clear_effect(row, 1)
                    clear_effect(row, 2)
                    set_effect(row, 0, 4, 1)
                row[34] = 0
                row[35] = 0
                row[36] = 0
            set_string(row, strings, SPELL_NAME + locale_index, base_name)
            set_string(row, strings, SPELL_RANK + locale_index,
                       rank_text(base_rank_text, entry["rank"], rank_count, path, russian))
            description = entry['descriptions']['ruRU' if russian else 'enUS'][path]
            description = description.replace('{rank}', str(entry['rank'])).replace('{chance}', str(entry['rank'] * 20))
            locale = 'ruRU' if russian else 'enUS'
            set_string(row, strings, SPELL_DESCRIPTION + locale_index,
                       generated_path_tooltip(entry, base_description, description, path, locale, manifest,
                                              base_spell=base[0]))
            base_aura = tooltip_stock.bind_stock_fields(read_string(strings, base[SPELL_TOOLTIP + locale_index]), base[0])
            has_exact = path in entry.get('full_descriptions', {}).get(locale, {})
            if base_aura or has_exact:
                set_string(row, strings, SPELL_TOOLTIP + locale_index,
                           generated_path_tooltip(entry, base_aura, description, path, locale, manifest))
            row[133] = base[133] if entry['icon_source'] == 'stock_base_rank' else path_icon_id(manifest, entry['logical_name'], path)
            # The spellbook/talent icon identifies the chosen path. ActiveIconID
            # deliberately points at the stock icon so buffs/debuffs use the
            # familiar unframed art while retaining the path-specific aura text.
            row[134] = base[133]
            if str(base[0]) in manifest['stock_scoped_variables']:
                row[232] = manifest['stock_scoped_variables'][str(base[0])]
            if path == 'celestial':
                celestial.active(sys.modules[__name__], row, base, entry['logical_name'], strings, manifest, russian)
                celestial_aura_tooltips.active(sys.modules[__name__], row, base, entry, strings, manifest, locale_index)
            else:
                sha_aura_tooltips.active(sys.modules[__name__], row, base, entry, strings, manifest, locale_index)
            records.append(row)
            generated.append({
                "logical_name": entry["logical_name"],
                "section": entry["section"],
                "rank": entry["rank"],
                "base_spell": entry["base_spell"],
                "path": path,
                "spell_id": spell_id,
                "icon_id": row[133],
                "spell_family_name": row[208],
                "spell_family_flags": row[209:212],
                "visible": entry["visible"] and not (entry['section'] == 'passive_spells' and entry['type'] != 'common_passive'),
                "script_name": entry["script_name"],
            })
            by_id[spell_id] = row

    technical_template = by_id[64128]
    for logical_name, spell_id in manifest["technical_spells"].items():
        if logical_name in seven.WEAPON_COMPONENTS:
            row = seven.weapon_component(sys.modules[__name__], by_id[5940], spell_id, logical_name)
        elif logical_name.endswith("fan_offhand"):
            row = list(by_id[52874])
            row[0] = spell_id
            if logical_name.startswith("celestial"):
                row[92] = manifest['celestial_revision']['radius_id']
        else:
            row = create_technical_spell(technical_template, spell_id, logical_name, strings, locale_index, russian)
            celestial.technical(sys.modules[__name__], row, logical_name, strings, manifest)
        visibility.technical_presentation(sys.modules[__name__], row, logical_name, strings, by_id, manifest, russian)
        celestial_aura_tooltips.technical(sys.modules[__name__], row, logical_name, strings, manifest, locale_index)
        records.append(row)
        by_id[spell_id] = row
        generated.append({
            "logical_name": logical_name,
            "section": "technical_spells",
            "rank": 1,
            "base_spell": 52874 if logical_name.endswith("fan_offhand") else 64128,
            "path": "celestial" if logical_name.startswith("celestial") else "sha",
            "spell_id": spell_id,
            "icon_id": row[133],
            "spell_family_name": row[208],
            "spell_family_flags": row[209:212],
            "visible": manifest['technical_presentation'][logical_name]['visibility'] == 'visible',
            "script_name": "",
        })
    generated.extend(visibility.patch_display_records(sys.modules[__name__], records, strings, manifest, russian))
    records.sort(key=lambda row: row[0])
    return generated


def patch_native_talent_descriptions(records: list[list[int]], strings: bytearray,
                                     manifest: dict[str, Any], locale_index: int) -> list[int]:
    """Make the stock talent-rank tooltip path-aware without TalentUI Lua.

    Blizzard_TalentUI renders an unlearned ``0/N`` talent from the stock rank
    Spell.dbc row. Referencing a custom rank therefore cannot work until that
    custom spell has entered the client cache. The selected path is already a
    persistent learned spell, and the native 3.3.5 formatter supports the same
    ``$?s<spell>[known][otherwise]`` branch used by Blizzard glyph tooltips.

    Cultivation / Rogue always grants exactly one of the two path passives. A single
    binary branch avoids nested formatter conditionals, which this client does
    not parse safely. Both branches are copied from the already generated and
    validated custom rank descriptions, so the initial and learned tooltips
    have one source of truth.
    """
    by_id = {row[0]: row for row in records}
    abilities = {entry['logical_name']: entry
                 for entry in manifest['active_spells'] + manifest['passive_spells']}
    celestial_marker = manifest['technical_spells']['celestial_path_passive']
    changed: list[int] = []
    for mapping in manifest['talent_ui']['mappings']:
        ability = abilities[mapping['logical_name']]
        stock_ranks = mapping['rank_spells']
        if not stock_ranks or any(stock_id not in ability['base_spell_chain'] for stock_id in stock_ranks):
            raise ValueError(
                f'Native talent rank map is not a subset of {mapping["logical_name"]}: '
                f'{stock_ranks!r} vs {ability["base_spell_chain"]!r}')
        for talent_rank, stock_id in enumerate(stock_ranks, 1):
            ability_rank = ability['base_spell_chain'].index(stock_id)
            celestial_id = ability['celestial_first'] + ability_rank
            sha_id = ability['sha_first'] + ability_rank
            try:
                celestial_text = read_string(
                    strings, by_id[celestial_id][SPELL_DESCRIPTION + locale_index])
                sha_text = read_string(
                    strings, by_id[sha_id][SPELL_DESCRIPTION + locale_index])
            except KeyError as error:
                raise ValueError(
                    f'Missing generated talent branch for {mapping["logical_name"]} rank {talent_rank}') from error
            if not celestial_text or not sha_text:
                raise ValueError(
                    f'Empty native talent branch for {mapping["logical_name"]} rank {talent_rank}')
            if any(token in celestial_text or token in sha_text for token in ('[', ']')):
                raise ValueError(
                    f'Nested native formatter branch forbidden for {mapping["logical_name"]} rank {talent_rank}')
            conditional = f'$?s{celestial_marker}[{celestial_text}][{sha_text}]'
            set_string(by_id[stock_id], strings, SPELL_DESCRIPTION + locale_index, conditional)
            changed.append(stock_id)
    if len(changed) != len(set(changed)):
        raise ValueError('A stock talent rank was patched more than once')
    return changed


def patch_skill_line(records: list[list[int]], entries: list[dict[str, Any]], manifest: dict[str, Any]) -> list[dict[str, int]]:
    by_spell: dict[int, list[int]] = {}
    for row in records:
        by_spell.setdefault(row[2], row)
    existing_ids = {row[0] for row in records}
    next_id = manifest["skill_line_ability_id_first"]
    added: list[dict[str, int]] = []
    for entry in entries:
        if not entry["visible"]:
            continue
        template = by_spell[entry["base_spell"]]
        for spell_id in (entry["celestial_spell"], entry["sha_spell"]):
            while next_id in existing_ids:
                next_id += 1
            row = list(template)
            row[0] = next_id
            row[2] = spell_id
            row[8] = 0
            # Variant ownership belongs exclusively to SpellService. Inheriting
            # auto-learn makes rank-one variants temporary all-spec skill spells;
            # removing one spec then blocks _addSpell from restoring that rank.
            row[9] = 0
            records.append(row)
            existing_ids.add(next_id)
            added.append({"id": next_id, "spell_id": spell_id, "skill_line": row[1]})
            next_id += 1
    for logical_name in ("celestial_path_passive", "sha_path_passive"):
        spell_id = manifest["technical_spells"][logical_name]
        template = by_spell[1784]
        while next_id in existing_ids:
            next_id += 1
        row = list(template)
        row[0] = next_id
        row[1] = manifest["skill_line"]
        row[2] = spell_id
        row[8] = 0
        row[9] = 0
        records.append(row)
        existing_ids.add(next_id)
        added.append({"id": next_id, "spell_id": spell_id, "skill_line": row[1]})
        next_id += 1
    added.extend(visibility.patch_display_skill(sys.modules[__name__], records, manifest))
    records.sort(key=lambda row: row[0])
    return added


def cpp_name(value: str) -> str:
    return "".join(part.capitalize() for part in value.split("_"))


def write_cpp_mapping(path: Path, manifest: dict[str, Any], entries: list[dict[str, Any]]) -> None:
    lines = [
        "// Generated by tools/generate_rogue_paths.py. Do not edit.",
        "#ifndef MOD_ROGUE_PATHS_GENERATED_SPELLS_H",
        "#define MOD_ROGUE_PATHS_GENERATED_SPELLS_H",
        "",
        "#include \"Define.h\"",
        "#include <array>",
        "#include <string_view>",
        "",
        "namespace Cultivation::Rogue::Generated",
        "{",
        "struct SpellVariantRow",
        "{",
        "    uint32 baseSpell;",
        "    uint32 celestialSpell;",
        "    uint32 shaSpell;",
        "    std::string_view logicalName;",
        "    uint8 rank;",
        "    bool passive;",
        "    bool talentGated;",
        "};",
        "",
        f"inline constexpr std::array<SpellVariantRow, {len(entries)}> SpellVariants = {{{{",
    ]
    for entry in entries:
        lines.append(
            f"    {{{entry['base_spell']}, {entry['celestial_spell']}, {entry['sha_spell']}, "
            f"\"{entry['logical_name']}\", {entry['rank']}, "
            f"{'true' if entry['section'] == 'passive_spells' else 'false'}, "
            f"{'true' if (entry['section'] == 'passive_spells' and entry['type'] != 'common_passive') or entry['type'].endswith('_talent') else 'false'}}},"
        )
    lines.extend(["}};", "", "enum TechnicalSpell : uint32", "{"])
    for logical_name, spell_id in manifest["technical_spells"].items():
        lines.append(f"    {cpp_name(logical_name)} = {spell_id},")
    celestial_technical = [spell_id for name, spell_id in manifest["technical_spells"].items() if name.startswith("celestial")]
    sha_technical = [spell_id for name, spell_id in manifest["technical_spells"].items() if name.startswith("sha")]
    lines.extend(["};", ""])
    lines.append(f"inline constexpr uint16 SynchronizationSchemaVersion = {manifest['schema_version']};")
    lines.extend(['struct DisplayPassiveRow { uint32 spell; uint32 base; uint32 mechanic; uint8 path; uint8 rank; bool talentRequired; std::string_view logicalName; uint32 iconSource; uint32 iconId; };',
                  f"inline constexpr std::array<DisplayPassiveRow, {len(manifest['display_passives'])}> DisplayPassives = {{{{"])
    for item in manifest['display_passives']:
        icon_id = item.get('icon_id') or path_icon_id(manifest, item['logical_name'], item['path'])
        lines.append(f"    {{{item['spell_id']}, {item['base_spell']}, {item['mechanic_spell']}, {1 if item['path'] == 'celestial' else 2}, {item['rank']}, {'true' if item['talent_required'] else 'false'}, \"{item['logical_name']}\", {item['icon_source_spell']}, {icon_id}}},")
    lines.append('}};')
    for group, values in manifest['balance'].items():
        for name, value in values.items():
            lines.append(f'inline constexpr uint32 {cpp_name(group)}{cpp_name(name)} = {value};')
    for label, values in (
        ('RetiredCelestialAuras', manifest['celestial_revision']['retired_auras']),
        ('VanishProtectedSpellIds', manifest['celestial_revision']['vanish_protected_spell_ids']),
        ('VanishProtectedAuraTypes', manifest['celestial_revision']['vanish_protected_aura_types']),
    ):
        lines.append(f"inline constexpr std::array<uint32, {len(values)}> {label} = {{{{{', '.join(map(str, values))}}}}};")
    lines.append(f"inline constexpr std::array<uint32, {len(celestial_technical)}> CelestialTechnicalSpells = {{{{{', '.join(map(str, celestial_technical))}}}}};")
    lines.append(f"inline constexpr std::array<uint32, {len(sha_technical)}> ShaTechnicalSpells = {{{{{', '.join(map(str, sha_technical))}}}}};")
    cooldowns = [value for name, value in manifest['technical_spells'].items() if name.endswith('_icd')]
    lines.append(f"inline constexpr std::array<uint32, {len(cooldowns)}> PersistentCooldownSpells = {{{{{', '.join(map(str, cooldowns))}}}}};")
    lines.extend(["", "} // namespace Cultivation::Rogue::Generated", "", "#endif", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_sql(path: Path, manifest: dict[str, Any], entries: list[dict[str, Any]], *, check_only: bool = False) -> None:
    lines = [
        "-- Generated by tools/generate_rogue_paths.py. Do not edit.",
        "DELETE FROM `spell_script_names` WHERE `ScriptName`='spell_cultivation_rogue_active' AND `spell_id` IN (-53,14278,5938);",
        "DELETE FROM `spell_ranks` WHERE `spell_id` BETWEEN 86000 AND 86999;",
        "DELETE FROM `spell_script_names` WHERE ABS(`spell_id`) BETWEEN 86000 AND 86999;",
        "",
        "INSERT INTO `spell_ranks` (`first_spell_id`, `spell_id`, `rank`) VALUES",
    ]
    rank_rows: list[str] = []
    for ability in manifest["active_spells"] + manifest["passive_spells"]:
        if len(ability["base_spell_chain"]) == 1:
            continue  # AzerothCore rejects one-record rank chains.
        for path_name in ("celestial", "sha"):
            first_spell = ability[f"{path_name}_first"]
            for rank in range(1, len(ability["base_spell_chain"]) + 1):
                rank_rows.append(f"({first_spell}, {first_spell + rank - 1}, {rank})")
    lines.append(",\n".join(rank_rows) + ";")
    lines.extend(["", "INSERT INTO `spell_script_names` (`spell_id`, `ScriptName`) VALUES"])
    script_rows: list[str] = []
    fan = next(a for a in manifest['active_spells'] if a['logical_name']=='fan_of_knives')
    for spell in (fan['celestial_first'],manifest['technical_spells']['celestial_fan_offhand']):
        script_rows.append(f"({spell}, 'spell_cultivation_rogue_celestial_fan')")
    for name in sorted(seven.WEAPON_COMPONENTS):
        script_rows.append(f"({manifest['technical_spells'][name]}, 'spell_cultivation_rogue_shiv_component')")
    script_rows.append(f"({manifest['technical_spells']['celestial_ghostly_strike_tracker']}, 'spell_cultivation_rogue_ghostly_dodge')")
    for ability in manifest['active_spells']:
        if ability['logical_name'] == 'blind':
            script_rows.append(f"({ability['celestial_first']}, 'spell_cultivation_rogue_blind')")
        if ability['logical_name'] == 'shiv':
            for path_name in ('celestial', 'sha'):
                script_rows.append(f"({ability[path_name + '_first']}, 'spell_cultivation_rogue_shiv')")
    for ability in manifest["active_spells"] + manifest["passive_spells"]:
        if not ability["script_name"]:
            continue
        for path_name in ("celestial", "sha"):
            first = ability[f'{path_name}_first']
            signed_id = -first if len(ability["base_spell_chain"]) > 1 else first
            script_rows.append(f"({signed_id}, '{ability['script_name']}')")
    for path_name in ("celestial", "sha"):
        script_rows.append(f"({manifest['technical_spells'][f'{path_name}_fan_offhand']}, 'spell_cultivation_rogue_active')")
    script_rows.append("(-86437, 'spell_cultivation_rogue_sha_honor')")
    inherited_scripts = {
        "vanish": "spell_rog_vanish",
        "evasion": "spell_cultivation_rogue_evasion",
        "rupture": "spell_rog_rupture",
        "killing_spree": "spell_rog_killing_spree",
        "tricks_of_the_trade": "spell_rog_tricks_of_the_trade",
        "cheat_death": "spell_rog_cheat_death",
        "combat_potency": "spell_cultivation_rogue_combat_potency",
    }
    for ability in manifest["active_spells"] + manifest["passive_spells"]:
        inherited = inherited_scripts.get(ability["logical_name"])
        if not inherited:
            continue
        for path_name in ("celestial", "sha"):
            first = ability[f"{path_name}_first"]
            signed_id = -first if len(ability["base_spell_chain"]) > 1 else first
            script_rows.append(f"({signed_id}, '{inherited}')")
    lines.append(",\n".join(script_rows) + ";")
    group = manifest['celestial_revision']['suppression_group']
    strong = manifest['technical_spells']['celestial_damage_suppression_20']
    weak = manifest['technical_spells']['celestial_damage_suppression_15']
    lines.extend([
        f"DELETE FROM spell_group WHERE id={group};",
        f"INSERT INTO spell_group (id,spell_id) VALUES ({group},{strong}),({group},{weak});",
        f"DELETE FROM spell_group_stack_rules WHERE group_id={group};",
        f"INSERT INTO spell_group_stack_rules (group_id,stack_rule) VALUES ({group},1);",
    ])
    lines.extend([
        "",
        "-- Preserve baseline linked effects and proc metadata for replacement IDs.",
        "DROP TEMPORARY TABLE IF EXISTS `rogue_path_install_map`;",
        "CREATE TEMPORARY TABLE `rogue_path_install_map` (`base_id` INT UNSIGNED PRIMARY KEY, `celestial_id` INT UNSIGNED NOT NULL, `sha_id` INT UNSIGNED NOT NULL);",
        "INSERT INTO `rogue_path_install_map` VALUES",
        ",\n".join(f"({entry['base_spell']}, {entry['celestial_spell']}, {entry['sha_spell']})" for entry in entries) + ";",
        "DROP TEMPORARY TABLE IF EXISTS `rogue_path_effect_map`;",
        "CREATE TEMPORARY TABLE `rogue_path_effect_map` AS SELECT * FROM `rogue_path_install_map`;",
        "DELETE FROM `spell_linked_spell` WHERE ABS(`spell_trigger`) BETWEEN 86000 AND 86999;",
        "DELETE FROM `spell_proc` WHERE ABS(`SpellId`) BETWEEN 86000 AND 86999;",
    ])
    proc_columns = ["SchoolMask", "SpellFamilyName", "SpellFamilyMask0", "SpellFamilyMask1", "SpellFamilyMask2", "ProcFlags", "SpellTypeMask", "SpellPhaseMask", "HitMask", "AttributesMask", "DisableEffectsMask", "ProcsPerMinute", "Chance", "Cooldown", "Charges"]
    for path_name in ("celestial", "sha"):
        custom = f"{path_name}_id"
        lines.extend([
            "INSERT INTO `spell_linked_spell` (`spell_trigger`, `spell_effect`, `type`, `comment`)",
            f"SELECT SIGN(l.`spell_trigger`)*CAST(m.`{custom}` AS SIGNED), IF(e.`base_id` IS NULL, l.`spell_effect`, SIGN(l.`spell_effect`)*CAST(e.`{custom}` AS SIGNED)), l.`type`, CONCAT('Cultivation / Rogue: ', l.`comment`)",
            "FROM `spell_linked_spell` l JOIN `rogue_path_install_map` m ON ABS(l.`spell_trigger`)=m.`base_id` LEFT JOIN `rogue_path_effect_map` e ON ABS(l.`spell_effect`)=e.`base_id`;",
            "INSERT INTO `spell_proc` (`SpellId`, " + ", ".join(f"`{column}`" for column in proc_columns) + ")",
            f"SELECT SIGN(p.`SpellId`)*CAST(m.`{custom}` AS SIGNED), " + ", ".join(f"p.`{column}`" for column in proc_columns),
            "FROM `spell_proc` p JOIN `rogue_path_install_map` m ON ABS(p.`SpellId`)=m.`base_id` WHERE m.`base_id` IN (35541,35550,35551,35552,35553);",
        ])
    lines.extend([
        "DROP TEMPORARY TABLE `rogue_path_install_map`;",
        "DROP TEMPORARY TABLE `rogue_path_effect_map`;",
        "UPDATE `spell_proc` SET `Chance`=100 WHERE `SpellId` IN (-86409, -86429);",
    ])
    lines.append("DELETE FROM `spell_custom_attr` WHERE `spell_id` BETWEEN 86000 AND 86999;")
    for entry in entries:
        if not entry.get('seven_extension'):
            continue  # keep the previously validated native polarity of existing transformed effects
        for path_name in ('celestial', 'sha'):
            mask = '~131072' if entry['logical_name'] == 'backstab' and path_name == 'sha' else '4294967295'
            lines.append(f"INSERT INTO `spell_custom_attr` (`spell_id`,`attributes`) SELECT {entry[path_name + '_spell']}, `attributes` & {mask} FROM `spell_custom_attr` WHERE `spell_id`={entry['base_spell']};")
    ghost_tracker = manifest['technical_spells']['celestial_ghostly_strike_tracker']
    lines.append(f"INSERT INTO `spell_proc` (`SpellId`,`ProcFlags`,`HitMask`,`Chance`) VALUES ({ghost_tracker},680,16,100);")
    fan = next(a for a in manifest["active_spells"] if a["logical_name"] == "fan_of_knives")
    for path_name in ("celestial", "sha"):
        offhand = manifest["technical_spells"][f"{path_name}_fan_offhand"]
        lines.append(f"UPDATE `spell_linked_spell` SET `spell_effect`={offhand} WHERE `spell_trigger`={fan[f'{path_name}_first']} AND `spell_effect`=52874;")
    lines.extend([
        "",
        "DELETE FROM `spell_proc` WHERE `SpellId` IN (-86007, -86207);",
        "INSERT INTO `spell_proc` (`SpellId`, `SchoolMask`, `SpellFamilyName`, `SpellFamilyMask0`, `SpellFamilyMask1`, `SpellFamilyMask2`, `ProcFlags`, `SpellTypeMask`, `SpellPhaseMask`, `HitMask`, `AttributesMask`, `DisableEffectsMask`, `ProcsPerMinute`, `Chance`, `Cooldown`, `Charges`) VALUES",
        "(-86007, 0, 0, 0, 0, 0, 680, 0, 0, 16, 0, 0, 0, 100, 0, 0),",
        "(-86207, 0, 0, 0, 0, 0, 680, 0, 0, 16, 0, 0, 0, 100, 0, 0);",
        "INSERT INTO `spell_proc` (`SpellId`,`ProcFlags`,`SpellTypeMask`,`SpellPhaseMask`,`HitMask`,`Chance`) VALUES (-86437,272,1,2,2,100);",
    ])
    text = "\n".join(lines) + "\n" + SHADOWSTEP_CLONE_SQL
    if check_only:
        def canonical_sql(value):
            # Legacy generator iterated a set for the three weapon bindings.
            # Row order in this one INSERT is immaterial; all statements and
            # duplicates remain checked, without rewriting immutable base SQL.
            statements = value.split(';')
            for index, statement in enumerate(statements):
                prefix = "INSERT INTO `spell_script_names` (`spell_id`, `ScriptName`) VALUES\n"
                if statement.lstrip().startswith(prefix):
                    rows = statement.lstrip()[len(prefix):].strip().split(',\n')
                    statements[index] = prefix + ',\n'.join(sorted(rows))
            return ';'.join(statements)
        if canonical_sql(path.read_text(encoding='utf-8')) != canonical_sql(text):
            raise ValueError('SQL differs: create an explicit pending migration, never overwrite immutable base SQL')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_spell_map(path: Path, generated: list[dict[str, Any]], skill_rows: list[dict[str, int]]) -> None:
    skill_by_spell = {row["spell_id"]: row for row in skill_rows}
    lines = [
        "# Cultivation / Rogue spell ID map",
        "",
        "Generated from `data/cultivation_rogue_spell_manifest.json`.",
        "",
        "| Logical name | Path | Rank | Base | Custom | Type | SkillLineAbility |",
        "|---|---:|---:|---:|---:|---|---:|",
    ]
    for row in generated:
        skill_id = skill_by_spell.get(row["spell_id"], {}).get("id", "")
        lines.append(
            f"| {row['logical_name']} | {row['path']} | {row['rank']} | {row['base_spell']} | "
            f"{row['spell_id']} | {row['section']} | {skill_id} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def semantic_non_string_rows(path: Path) -> dict[int, tuple[int, ...]]:
    rows, _ = load_dbc(path, SPELL_FIELDS)
    string_fields = set(range(136, 152)) | set(range(153, 169)) | set(range(170, 186)) | set(range(187, 203))
    return {row[0]: tuple(value for index, value in enumerate(row) if index not in string_fields) for row in rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--client-spell-baseline", type=Path, required=True)
    parser.add_argument("--server-spell-baseline", type=Path, required=True)
    parser.add_argument("--skill-line-baseline", type=Path, required=True)
    parser.add_argument("--client-spell-output", type=Path, required=True)
    parser.add_argument("--server-spell-output", type=Path, required=True)
    parser.add_argument("--client-skill-line-output", type=Path, required=True)
    parser.add_argument("--server-skill-line-output", type=Path, required=True)
    parser.add_argument("--cpp-output", type=Path, required=True)
    parser.add_argument("--sql-output", type=Path, required=True)
    parser.add_argument("--sql-check-only", action='store_true', help='Verify existing SQL without modifying it')
    parser.add_argument("--spell-map-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    client_rows, client_strings = load_dbc(args.client_spell_baseline, SPELL_FIELDS)
    server_rows, server_strings = load_dbc(args.server_spell_baseline, SPELL_FIELDS)
    import dbc_string_integrity
    recovered_strings = {
        'client': dbc_string_integrity.repair(sys.modules[__name__], client_rows, client_strings),
        'server': dbc_string_integrity.repair(sys.modules[__name__], server_rows, server_strings),
    }
    skill_rows, skill_strings = load_dbc(args.skill_line_baseline, SKILL_LINE_ABILITY_FIELDS)
    stock_restore_client = visibility.restore_stock(sys.modules[__name__], client_rows, client_strings, manifest)
    stock_restore_server = visibility.restore_stock(sys.modules[__name__], server_rows, server_strings, manifest)
    client_ids = {row[0] for row in client_rows}
    server_ids = {row[0] for row in server_rows}
    if client_ids != server_ids:
        raise ValueError("Client and server Spell.dbc ID sets differ")
    entries = validate_manifest(manifest, client_ids, skill_rows)

    generated_client = patch_spells(client_rows, client_strings, entries, manifest, 8, True)
    generated_server = patch_spells(server_rows, server_strings, entries, manifest, 0, False)
    native_talents_client = patch_native_talent_descriptions(
        client_rows, client_strings, manifest, 8)
    native_talents_server = patch_native_talent_descriptions(
        server_rows, server_strings, manifest, 0)
    if native_talents_client != native_talents_server:
        raise ValueError('Client/server native talent description coverage differs')
    visibility.merge_locales(sys.modules[__name__], client_rows, client_strings, server_rows, server_strings, manifest)
    client_summary = [(row["spell_id"], row["base_spell"], row["spell_family_flags"]) for row in generated_client]
    server_summary = [(row["spell_id"], row["base_spell"], row["spell_family_flags"]) for row in generated_server]
    if client_summary != server_summary:
        raise ValueError("Client/server generated spell semantics differ before write")

    generated_skill = patch_skill_line(skill_rows, entries, manifest)
    import path_status
    path_status.patch(sys.modules[__name__], client_rows, client_strings)
    path_status.patch(sys.modules[__name__], server_rows, server_strings)
    dbc_string_integrity.validate(client_rows, client_strings)
    dbc_string_integrity.validate(server_rows, server_strings)
    write_dbc(args.client_spell_output, client_rows, client_strings)
    write_dbc(args.server_spell_output, server_rows, server_strings)
    write_dbc(args.client_skill_line_output, skill_rows, skill_strings)
    write_dbc(args.server_skill_line_output, [list(row) for row in skill_rows], bytearray(skill_strings))
    auxiliary = celestial.auxiliary(sys.modules[__name__], manifest,
        Path(r'C:\Solo WotLK\test-server\20260831-rogue-paths-v2\data\dbc'),
        (args.client_spell_output.parent, args.server_spell_output.parent))
    visibility.generate_variables(sys.modules[__name__], manifest, (args.client_spell_output.parent, args.server_spell_output.parent))
    visibility.write_ui_data(sys.modules[__name__], manifest, client_rows, client_strings)
    import native_talent_metadata
    native_talent_metadata.write(args.manifest.parent.parent / 'client_patch/framexml/CultivationRogueHeader.lua',
                                 manifest, client_rows)

    client_semantics = semantic_non_string_rows(args.client_spell_output)
    server_semantics = semantic_non_string_rows(args.server_spell_output)
    custom_ids = sorted([row["spell_id"] for row in generated_client] +
                        [item['spell_id'] for item in path_status.spec()['statuses']])
    semantic_mismatches = [spell_id for spell_id in custom_ids if client_semantics[spell_id] != server_semantics[spell_id]]
    if semantic_mismatches:
        raise ValueError(f"Client/server custom spell semantic mismatch: {semantic_mismatches}")

    write_cpp_mapping(args.cpp_output, manifest, entries)
    write_sql(args.sql_output, manifest, entries, check_only=args.sql_check_only)
    write_spell_map(args.spell_map_output, generated_client, generated_skill)
    report = {
        "status": "passed",
        "schema_version": manifest["schema_version"],
        "display_passives": len(manifest['display_passives']),
        "stock_restoration": {'client': stock_restore_client, 'server': stock_restore_server},
        "recovered_foreign_strings": recovered_strings,
        "auxiliary_dbc": auxiliary,
        "active_rank_variants": sum(1 for row in generated_client if row["section"] == "active_spells"),
        "passive_rank_variants": sum(1 for row in generated_client if row["section"] == "passive_spells"),
        "technical_spells": len(manifest["technical_spells"]),
        "path_status_spells": path_status.spec()['statuses'],
        "skill_line_rows": len(generated_skill),
        "custom_spell_id_min": min(custom_ids),
        "custom_spell_id_max": max(custom_ids),
        "semantic_mismatches": semantic_mismatches,
        "native_talent_rank_descriptions": native_talents_client,
        "inputs": {
            "manifest_sha256": sha256(args.manifest),
            "client_spell_baseline_sha256": sha256(args.client_spell_baseline),
            "server_spell_baseline_sha256": sha256(args.server_spell_baseline),
            "skill_line_baseline_sha256": sha256(args.skill_line_baseline),
        },
        "outputs": {
            "client_spell_sha256": sha256(args.client_spell_output),
            "server_spell_sha256": sha256(args.server_spell_output),
            "client_skill_line_sha256": sha256(args.client_skill_line_output),
            "server_skill_line_sha256": sha256(args.server_skill_line_output),
            "cpp_sha256": sha256(args.cpp_output),
            "sql_sha256": sha256(args.sql_output),
            "spell_map_sha256": sha256(args.spell_map_output),
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
