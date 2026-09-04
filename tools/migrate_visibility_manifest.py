"""One-time, deterministic schema-3 manifest migration from audited schema-2 data.

This tool does not deploy, modify a client, or rewrite a baseline DBC.
"""
import json
from pathlib import Path
import generate_rogue_paths as g

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / 'data/cultivation_rogue_spell_manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if 'display_passives' in manifest:
        raise SystemExit('Already migrated; edit the manifest, do not replay migration')
    audit = ROOT / 'generated/schema3-audit'
    stock, _ = g.load_dbc(audit / 'stock-Spell.dbc', 234)
    by_id = {row[0]: row for row in stock}
    talent_rows, _ = g.load_dbc(audit / 'stock-Talent.dbc', 23)
    var_rows, _ = g.load_dbc(audit / 'stock-SpellDescriptionVariables.dbc', 2)
    assert all(row[0] < 9000 for row in var_rows)
    manifest['stock_sources'] = {
        'spell': {'path': 'generated/schema3-audit/stock-Spell.dbc', 'sha256': g.sha256(audit / 'stock-Spell.dbc')},
        'icon': {'path': 'generated/schema3-audit/stock-SpellIcon.dbc', 'sha256': g.sha256(audit / 'stock-SpellIcon.dbc')},
        'talent': {'path': 'generated/schema3-audit/stock-Talent.dbc', 'sha256': g.sha256(audit / 'stock-Talent.dbc')},
        'variables': {'path': 'generated/schema3-audit/stock-SpellDescriptionVariables.dbc', 'sha256': g.sha256(audit / 'stock-SpellDescriptionVariables.dbc')},
    }
    manifest['stock_scoped_variables'] = {}
    manifest['talent_ui'] = {'addon': 'RoguePathsUI', 'interface': 30300, 'mappings': []}
    manifest['display_passives'] = []
    # Freeze every existing custom icon allocation, including now-unused passive frames.
    # No shift of 6100..6177 is allowed when choosing a stock icon instead.
    for ability in manifest['active_spells'] + manifest['passive_spells']:
        if not ability.get('stock_icon'):
            ability['custom_icon_ids'] = {p: g.path_icon_id(manifest, ability['logical_name'], p) for p in ('celestial', 'sha')}
        ability['icon_source'] = 'stock_base_rank' if ability.get('stock_icon') or ability in manifest['passive_spells'] else 'approved_path_frame'
        ability['stock_icon_reference'] = {
            str(i): {'SpellIconID': by_id[i][133], 'ActiveIconID': by_id[i][134]} for i in ability['base_spell_chain']}
        ability['descriptions'] = {}
        for locale, descriptions in (('ruRU', g.PATH_DESCRIPTIONS_RU), ('enUS', g.PATH_DESCRIPTIONS_EN)):
            values = list(descriptions[ability['logical_name']])
            overrides = g.celestial.RU if locale == 'ruRU' else g.celestial.EN
            if ability['logical_name'] in overrides:
                values[0] = overrides[ability['logical_name']]
            ability['descriptions'][locale] = dict(zip(('celestial', 'sha'), values))
        chain = set(ability['base_spell_chain'])
        for base in sorted(chain):
            if by_id[base][232] in {r[0] for r in var_rows}:
                manifest['stock_scoped_variables'][str(base)] = 9000 + len(manifest['stock_scoped_variables'])
        matches = [r for r in talent_rows if chain.intersection(r[4:9])]
        if matches:
            assert len(matches) == 1, ability['logical_name']
            r = matches[0]
            manifest['talent_ui']['mappings'].append({'logical_name': ability['logical_name'], 'talent_id': r[0],
                'tab_id': r[1], 'tier': r[2], 'column': r[3], 'rank_spells': [i for i in r[4:9] if i]})
    passive_texts = {
        'overkill': (
            'После выхода из незаметности бонус к восстановлению энергии действует 30 сек. вместо 20 сек.',
            'После выхода из незаметности восстановление энергии повышается на 100% на 6 сек., после чего уменьшается на 30% на 4 сек.'),
        'seal_fate': (
            'Каждый приём серии, который должен был появиться сверх максимума, восстанавливает 5 ед. энергии. Не более 10 ед. энергии в секунду.',
            'С вероятностью 20% срабатывание создаёт 2 дополнительных приёма серии вместо 1. Внутреннее восстановление усиленного срабатывания — 2 сек.'),
        'master_poisoner': (
            'Продолжительность ваших ядов увеличивается на 50%. Одно рассеивание не может снять более 2 доз смертельного или нейтрализующего яда.',
            'Продолжительность ваших ядов уменьшается вдвое, вероятность наложения повышается на 20 процентных пунктов. Первое наложение на 4 сек. усиливает наносящие урон яды на 20% и замедление калечащего яда до 70%.'),
        'combat_potency': (
            'Каждый пятый успешный удар оружием в левой руке восстанавливает 15 ед. энергии. Стандартное случайное срабатывание заменено.',
            'Удары оружием в левой руке с вероятностью 25% восстанавливают 10 ед. энергии и повышают скорость атаки на 5% на 4 сек. Эффект суммируется до 3 раз.'),
        'cheat_death': (
            'После предотвращения смерти получаемый урон уменьшается на 90% на 4 сек., а за это время восстанавливается 10% максимального здоровья. Пока действует защита, наносимый вами урон уменьшается на 20%. Стандартное внутреннее восстановление сохраняется.',
            'После предотвращения смерти получаемый урон уменьшается на 80% на 2 сек. Вместо лечения восстанавливается 60 ед. энергии, завершается восстановление «Шага сквозь тень» и наносимый урон повышается на 10% на 6 сек. Стандартное внутреннее восстановление сохраняется.'),
        'honor_among_thieves': (
            'До 2 избыточных приёмов серии сохраняются в резерве и автоматически возвращаются после следующего завершающего приёма по той же цели.',
            'Критические эффекты союзников больше не создают приёмы серии. Ваши прямые критические атаки с вероятностью 50% создают дополнительный приём серии, но не более 2 раз в секунду.'),
    }
    english = {
        'combat_potency': ('Every fifth successful off-hand weapon hit restores 15 energy, replacing the standard random proc.',
                           'Successful off-hand weapon hits have a 25% chance to restore 10 energy and increase attack speed by 5% for 4 seconds, stacking up to 3 times.'),
        'master_poisoner': ('Your poisons last 50% longer. A single enemy dispel removes at most 2 doses of Deadly or Wound Poison.',
                            'Your poisons last half as long and have 20 percentage points more application chance. The first application creates a 4-second window: damaging poisons deal 20% more damage and Crippling Poison slows by 70%.'),
        'honor_among_thieves': ('Up to 2 excess combo points are reserved and returned after your next finisher against the same target.',
                               'Allied critical effects no longer grant combo points. Your direct critical attacks have a 50% chance to grant an additional combo point, at most twice per second.'),
    }
    offset = 0
    for ability in manifest['passive_spells']:
        name = ability['logical_name']
        if name not in passive_texts:
            continue
        ability['descriptions']['ruRU'] = dict(zip(('celestial', 'sha'), passive_texts[name]))
        if name in english:
            ability['descriptions']['enUS'] = dict(zip(('celestial', 'sha'), english[name]))
        for rank, base in enumerate(ability['base_spell_chain']):
            for which, first in (('celestial', 86600), ('sha', 86700)):
                manifest['display_passives'].append({'logical_name': name, 'type': 'display_only_passive',
                    'path': which, 'rank': rank + 1, 'base_spell': base, 'spell_id': first + offset + rank,
                    'mechanic_spell': ability[which + '_first'] + rank, 'talent_required': True,
                    'skill_line': 253, 'icon_source_spell': base})
        offset += len(ability['base_spell_chain'])
    assert offset == 20
    for which, spell, mechanic in (('celestial', 86620, 86542), ('sha', 86720, 86543)):
        manifest['display_passives'].append({'logical_name': 'stealth_mastery', 'type': 'display_only_passive',
            'path': which, 'rank': 1, 'base_spell': 1860, 'spell_id': spell, 'mechanic_spell': mechanic,
            'talent_required': False, 'skill_line': 39, 'icon_source_spell': 8676,
            'names': {'ruRU': 'Мастерство незаметности', 'enUS': 'Stealth Mastery'},
            'descriptions': {
                'ruRU': 'После 3 сек. непрерывного пребывания в состоянии незаметности штраф к скорости передвижения снимается, а уровень незаметности повышается на 1. Эффект исчезает при выходе из незаметности.' if which == 'celestial' else 'Первая специальная прямая атака из незаметности или в течение 3 сек. после выхода стоит на 20 ед. энергии меньше и наносит на 10% больше прямого урона.',
                'enUS': 'After 3 seconds continuously in stealth, the movement speed penalty is removed and stealth level increases by 1. The effect ends when you leave stealth.' if which == 'celestial' else 'Your first special direct attack from stealth or within 3 seconds after leaving it costs 20 less energy and deals 10% more direct damage.'}})
    for item in manifest['display_passives']:
        if item['spell_id'] in by_id:
            raise ValueError('Display ID collides with stock')
    manifest['balance'] = {'combat_potency': {'celestial_hit_interval': 5, 'celestial_energy': 15,
        'sha_proc_chance': 25, 'sha_energy': 10, 'sha_haste_percent': 5, 'sha_haste_duration_ms': 4000, 'sha_max_stacks': 3},
        'honor_among_thieves': {'celestial_reserve': 2, 'sha_proc_chance': 50, 'sha_limit': 2, 'sha_window_ms': 1000}}
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Manifest migrated: 42 display records; exact stock icon references; stable framed icon IDs; talent-node mapping')


if __name__ == '__main__':
    main()
