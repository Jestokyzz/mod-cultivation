"""One-time presentation inventory; migrate editable data into the central manifest."""
import json
from pathlib import Path
import generate_rogue_paths as g
import visibility_schema3 as v

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / 'data/cultivation_rogue_spell_manifest.json'
    m = json.loads(path.read_text(encoding='utf-8'))
    if 'technical_presentation' in m:
        raise SystemExit('Already migrated')
    rows, strings = g.load_dbc(ROOT / 'client_patch/staging/DBFilesClient/Spell.dbc', 234)
    by_id = {r[0]: r for r in rows}
    stock, ss = v.source(g, m, 'spell', 234)
    abilities = m['active_spells'] + m['passive_spells']
    # These are visible gameplay modifiers implemented in server hooks, not native effects.
    dummy = {
        'celestial_path_passive': ('Безупречный расчёт', 'Flawless Calculation', 14195, 'Завершающий приём с 5 приёмами серии восстанавливает 5 ед. энергии в секунду в течение 2 сек. и уменьшает получаемый урон на 5% на 6 сек.', 'A 5-point finisher restores 5 energy per second for 2 seconds and reduces damage taken by 5% for 6 seconds.'),
        'sha_path_passive': ('Кровавый азарт', 'Blood Thrill', 14177, 'После выхода из незаметности или применения «Хладнокровия», «Выброса адреналина», «Череды убийств» или «Танца теней» на 6 сек. увеличивает прямой урон и получаемый урон на 8%, а восстановление энергии — на 20%. Внутреннее восстановление — 20 сек.', 'After leaving stealth or using Cold Blood, Adrenaline Rush, Killing Spree or Shadow Dance: direct damage and damage taken increase by 8%, and energy regeneration by 20%, for 6 seconds. Internal cooldown: 20 seconds.'),
        'sha_vanish_exposure': ('Уязвимость после исчезновения', 'Vanish Exposure', 1856, 'Получаемый урон увеличен на 10%.', 'Damage taken increased by 10%.'),
        'sha_cold_blood_exposure': ('Уязвимость после хладнокровия', 'Cold Blood Exposure', 14177, 'Получаемый урон увеличен на 10%.', 'Damage taken increased by 10%.'),
        'celestial_cloak_guard': ('Защита плаща Теней', 'Cloak Protection', 31224, 'Получаемый магический урон уменьшен на 20%.', 'Magic damage taken reduced by 20%.'),
        'sha_kick_mark': ('Уязвимость после пинка', 'Kick Vulnerability', 1766, 'Прямой урон применившего эффект разбойника увеличен на 10%.', 'Direct damage from the applying rogue increased by 10%.'),
        'sha_kidney_mark': ('Уязвимость после удара по почкам', 'Kidney Shot Vulnerability', 408, 'Прямой урон применившего эффект разбойника увеличен на 15% против существ или на 10% против игроков.', 'Direct damage from the applying rogue increased by 15% in PvE or 10% in PvP.'),
        'sha_dismantle_mark': ('Уязвимость после разоружения', 'Dismantle Vulnerability', 51722, 'Прямой урон применившего эффект разбойника увеличен на 15%.', 'Direct damage from the applying rogue increased by 15%.'),
        'sha_master_poisoner_window': ('Мастер ядов', 'Master Poisoner', 58410, 'Наносящие урон яды применившего эффект разбойника усилены на 20%. Калечащий яд замедляет на 70%.', 'Damaging poisons from the applying rogue are increased by 20%. Crippling Poison slows by 70%.'),
        'sha_hunger_buff': ('Жажда крови', 'Hunger for Blood', 51662, 'Прямой урон увеличен на 12%.', 'Direct damage increased by 12%.'),
        'sha_cheat_death_damage': ('Обман смерти', 'Cheat Death', 31230, 'Наносимый прямой урон увеличен на 10%.', 'Direct damage increased by 10%.'),
        'sha_shadowstep_damage': ('Шаг сквозь тень', 'Shadowstep', 36554, 'Следующая специальная прямая атака наносит на 40% больше урона.', 'Your next special direct attack deals 40% more damage.'),
        'celestial_cheat_death_heal': ('Восстановление после обмана смерти', 'Cheat Death Recovery', 31230, 'Восстанавливает 10% максимального здоровья за 4 сек.', 'Restores 10% maximum health over 4 seconds.'),
    }
    native = {
        24: ('Восстанавливает {n} ед. энергии в секунду.', 'Restores {n} energy per second.'),
        110: ('Восстановление энергии изменено на {sign}{n}%.', 'Energy regeneration changed by {sign}{n}%.'),
        87: ('Получаемый урон изменён на {sign}{n}%.', 'Damage taken changed by {sign}{n}%.'),
        138: ('Скорость атаки увеличена на {n}%.', 'Attack speed increased by {n}%.'),
        35: ('Максимальный запас энергии увеличен на {n}.', 'Maximum energy increased by {n}.'),
        79: ('Наносимый урон изменён на {sign}{n}%.', 'Damage dealt changed by {sign}{n}%.'),
        229: ('Получаемый урон от атак по области уменьшен на {n}%.', 'Area damage taken reduced by {n}%.'),
        33: ('Скорость передвижения уменьшена на {n}%.', 'Movement speed reduced by {n}%.'),
        280: ('Игнорирование брони увеличено на {n}%.', 'Armor penetration increased by {n}%.'),
        67: ('Оружие недоступно.', 'Disarmed.'),
        270: ('Игнорирует сопротивление эффектам природы.', 'Ignores resistance to Nature effects.'),
    }
    result = {}
    retired = set(m['celestial_revision']['retired_auras'])
    for logical, spell in m['technical_spells'].items():
        row = by_id[spell]
        which = 'celestial' if logical.startswith('celestial') else 'sha'
        simple = logical.split('_', 1)[1]
        parent = next((a for a in sorted(abilities, key=lambda a: -len(a['logical_name'])) if simple.startswith(a['logical_name'])), None)
        item = {'visibility': 'hidden', 'reason': 'internal proc/cast/timer tracker; not a second learned spell', 'path': which}
        if spell in retired or logical.endswith('_icd') or logical in ('celestial_stealth_mastery', 'sha_stealth_window'):
            result[logical] = item
            continue
        if logical in m['celestial_revision']['visible_auras']:
            item = {'visibility': 'visible', 'path': which, 'preserve_validated_presentation': True}
        elif logical in dummy:
            ru, en, source, ru_text, en_text = dummy[logical]
            item = {'visibility': 'visible', 'path': which, 'icon_source_spell': source,
                    'names': {'ruRU': ru, 'enUS': en}, 'descriptions': {'ruRU': ru_text, 'enUS': en_text}}
        elif row[95] in native and parent:
            source = parent['base_spell_chain'][0]
            amount = g.signed(row[80] + 1)
            if amount >= 0x80000000:
                amount -= 0x100000000
            fmt = dict(n=abs(amount), sign='+' if amount >= 0 else '−')
            ru, en = native[row[95]]
            item = {'visibility': 'visible', 'path': which, 'icon_source_spell': source,
                    'names': {'ruRU': g.read_string(ss, stock[source][144]), 'enUS': g.read_string(strings, by_id[source][136])},
                    'descriptions': {'ruRU': ru.format(**fmt), 'enUS': en.format(**fmt)}}
        elif logical in ('celestial_finisher_regen', 'celestial_finisher_guard', 'sha_blood_thrill'):
            source = 14195 if which == 'celestial' else 14177
            text = {'celestial_finisher_regen': ('Восстанавливает 5 ед. энергии в секунду.', 'Restores 5 energy per second.'),
                    'celestial_finisher_guard': ('Получаемый урон уменьшен на 5%.', 'Damage taken reduced by 5%.'),
                    'sha_blood_thrill': ('Прямой урон и получаемый урон увеличены на 8%, восстановление энергии — на 20%.', 'Direct damage and damage taken increased by 8%; energy regeneration increased by 20%.')}[logical]
            item = {'visibility': 'visible', 'path': which, 'icon_source_spell': source,
                    'names': {'ruRU': 'Безупречный расчёт' if which == 'celestial' else 'Кровавый азарт', 'enUS': 'Flawless Calculation' if which == 'celestial' else 'Blood Thrill'},
                    'descriptions': dict(zip(('ruRU', 'enUS'), text))}
        result[logical] = item
    m['technical_presentation'] = result
    m['balance']['master_poisoner'] = {'sha_damage_percent': 20, 'sha_application_percentage_points': 20, 'sha_slow_percent': 70}
    path.write_text(json.dumps(m, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Technical presentation inventory:', len(result), 'entries;', sum(i['visibility'] == 'visible' for i in result.values()), 'visible')


if __name__ == '__main__':
    main()
