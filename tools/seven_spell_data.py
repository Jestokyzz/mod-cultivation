"""Declarative v2 additions used by the existing Spell.dbc generator."""

DESCRIPTIONS_RU = {
    'cheap_shot': ('Стоимость −10, оглушение +0,5 сек. до DR, всего 3 приёма серии. После обычного окончания или досрочного снятия цель 4 сек. наносит на 15% меньше урона.', 'Стоимость −20 (минимум 10), оглушение 3 сек. против существ и игроков. На время действия цель получает на 10% больше урона из всех источников.'),
    'backstab': ('По цели под вашим контролем стоимость −10. Прямой урон −10%, 2 приёма серии. Успешное попадание по такой цели возвращает 10 энергии.', 'Стандартная стоимость; прямой урон +30%, итоговый критический урон +20%. После «Шага сквозь тень» можно атаковать спереди.'),
    'blind': ('При успешном наложении удаляет все отрицательные эффекты периодического урона независимо от их источника. Дальность, стоимость, длительность и восстановление стандартные.', 'Перезарядка −60 сек.; длится 5 сек. против существ и игроков. Ваши эффекты периодического урона не снимают контроль.'),
    'safe_fall': ('Обнуляет урон настоящего падения. Опасное приземление даёт +30% скорости на 4 сек. и иммунитет к отбрасыванию на 2 сек.; восстановление 10 сек.', 'Урон падения −70%. Если исходный урон не меньше 10% максимального здоровья и вы выжили: +30 энергии, следующая специальная атака за 5 сек. получает +20% урона и 1 приём серии; восстановление 20 сек.'),
    'sap': ('Дальность +5 м.; длительность +2 сек. до DR. Досрочное игровое снятие замедляет цель на 70% и уменьшает её урон по вам на 20% на 4 сек.', 'Стандартная стоимость 65 энергии. Действует на находящуюся в бою цель 6 сек. против существ и игроков. Длина серии приёмов увеличивается на 2. Восстановление 10 сек.'),
    'ghostly_strike': ('Стоимость −10, прямой урон −20%. Стандартный бонус уклонения увеличен ещё на 15 п.п., длительность увеличена на 3 сек. Первое настоящее уклонение возвращает 20 энергии; приёмы серии не создаются.', 'Стоимость 25 энергии, перезарядка 15 сек., 2 приёма серии. Урон +40% по любой цели. Вместо уклонения успешный удар даёт +20% скорости атаки и уменьшает итоговую броню цели на 20% на 6 сек.'),
    'shiv': ('Фактическая стандартная стоимость от оружия снижена на 10 ед. (минимум 0). Стандартный удар левой рукой, 1 приём серии и одна попытка яда. При попадании накладывает «Фатальное снадобье» на 8 сек.: отрицательные болезни цели нельзя рассеять.', 'Стоимость +15 один раз. Два удара левой рукой: 100% и 50%, по одной попытке яда; всего 1 приём серии. Ваши яды по цели на 4 сек. сильнее на 20%; не складывается с Master Poisoner. После окна восстановление энергии −20% на 3 сек.'),
}
DESCRIPTIONS_EN = {
    'cheap_shot': ('Costs 10 less energy, stuns for 0.5 seconds longer before diminishing returns and awards 3 combo points total. After normal expiry or early removal the target deals 15% less damage for 4 seconds.', 'Costs 20 less energy (minimum 10); stuns creatures and players for 3 seconds. While active, the target takes 10% more damage from all sources.'),
    'backstab': ('Costs 10 less against a target under your control. Deals 10% less direct damage and awards 2 combo points. A successful hit against such a target restores 10 energy.', 'Standard cost; +30% direct damage and +20% final critical damage. Shadowstep permits frontal use.'),
    'blind': ('On successful application removes every harmful periodic-damage aura regardless of caster. Range, cost, duration and cooldown remain standard.', 'Cooldown reduced by 60 seconds; lasts 5 seconds against creatures and players. Your periodic damage effects do not break it.'),
    'safe_fall': ('Prevents real fall damage. A dangerous landing grants 30% movement speed for 4 seconds and knockback immunity for 2 seconds; 10-second internal cooldown.', 'Reduces real fall damage by 70%. Surviving a fall worth at least 10% maximum health before reduction restores 30 energy and empowers one special attack within 5 seconds by 20% plus 1 combo point; 20-second internal cooldown.'),
    'sap': ('Range +5 yards. Duration +2 seconds before diminishing returns. Early gameplay removal slows the target by 70% and reduces its damage to you by 20% for 4 seconds.', 'Standard 65 energy cost. Can affect a target in combat for 6 seconds against creatures and players. Awards 2 combo points. Cooldown 10 seconds.'),
    'ghostly_strike': ('Costs 10 less energy and deals 20% less direct damage. Adds 15 percentage points to the standard dodge bonus and lasts 3 seconds longer. The first real dodge restores 20 energy; no combo points are awarded.', 'Costs 25 energy; 15-second cooldown, 2 combo points and 40% more damage against any target. No dodge bonus. A successful hit instead grants 20% attack speed and reduces the target\'s final armor by 20% for 6 seconds.'),
    'shiv': ('Reduces the actual standard weapon-derived cost by 10, minimum 0. Retains the standard off-hand hit, 1 combo point and one poison attempt. A hit applies Fatal Concoction for 8 seconds, preventing dispels of harmful diseases.', 'Costs 15 more energy once. Two off-hand hits at 100% and 50%, one poison attempt each and only 1 combo point total. Your poisons gain 20% damage on this target for 4 seconds; strongest bonus with Master Poisoner. Afterwards energy regeneration is reduced by 20% for 3 seconds.'),
}

TARGETED = {'celestial_cheap_shot_guard', 'sha_cheap_shot_mark', 'sha_blind_strike',
            'celestial_sap_guard', 'sha_sap_icd', 'sha_sap_strike',
            'celestial_shiv_protection', 'celestial_shiv_icd', 'sha_shiv_vulnerability',
            'sha_ghostly_strike_armor'}
WEAPON_COMPONENTS = {'celestial_shiv_hit', 'sha_shiv_hit', 'sha_shiv_second'}
DURATIONS = {
    'celestial_cheap_shot_guard': 35, 'sha_cheap_shot_mark': 35, 'sha_blind_strike': 1,
    'celestial_safe_fall_speed': 35, 'celestial_safe_fall_knockback': 39, 'sha_safe_fall_dive': 28,
    'celestial_sap_guard': 35, 'sha_sap_icd': 18, 'sha_sap_strike': 1,
            'celestial_ghostly_strike_tracker': 1, 'sha_ghostly_strike_fury': 32,
            'sha_ghostly_strike_armor': 32,
    'celestial_shiv_protection': 35, 'celestial_shiv_icd': 31, 'sha_shiv_vulnerability': 35,
    'sha_shiv_regen_penalty': 27, 'celestial_safe_fall_icd': 1, 'sha_safe_fall_icd': 18,
    'sha_opener_armor': 39, 'sha_shadowstep_position': 27,
}
EFFECTS = {'celestial_safe_fall_speed': (31, 30, 0), 'celestial_safe_fall_knockback': (37, 1, 0),
           'celestial_sap_guard': (33, -70, 0), 'celestial_ghostly_strike_tracker': (49, 30, 0),
           'sha_ghostly_strike_fury': (138, 20, 0), 'sha_ghostly_strike_armor': (101, -20, 0),
           'sha_shiv_regen_penalty': (110, -20, 0),
           'sha_opener_armor': (280, 15, 0)}


def patch_active(g, row, name, path):
    celestial = path == 'celestial'
    # Encode every unconditional path cost delta in Spell.dbc so the native
    # client formatter and the server start from the same value. Conditional
    # discounts (Dance, Mutilate, Blind/Feint windows) remain runtime rules.
    if name == 'cheap_shot':
        row[42] = max(0, row[42] - (10 if celestial else 20))
        if not celestial:
            row[40] = 27  # three seconds before diminishing returns for every target type
    elif name == 'backstab':
        # Both variants keep the stock DBC cost. Celestial's -10 discount is
        # conditional on this rogue's hard control and is applied at cast time.
        row[42] = max(0, row[42])
    elif name == 'sap' and not celestial:
        row[42] = 65
        row[12] = 0
        row[13] = 0
    elif name == 'ghostly_strike':
        row[42] = max(0, row[42] - 10) if celestial else 25
    elif name == 'shiv':
        # Preserve native weapon-speed scaling. This changes only the flat
        # component: Celestial = stock formula -10, Sha = stock formula +15.
        row[42] = max(0, row[42] + (-10 if celestial else 15))

    if name == 'backstab' and not celestial:
        row[6] &= ~0x100000  # client positional restriction; server enforces position per cast
    elif name == 'blind':
        if not celestial:
            row[29] -= 60000  # visible base cooldown; server applies talents and configured delta
            row[40] = 28  # five seconds before diminishing returns for every target type
    elif name == 'sap':
        if celestial:
            row[46] = 7  # verified SpellRange: 10 yards
        else:
            row[5] &= ~0x100  # ONLY_PEACEFUL_TARGETS; remaining checks stay server-side
            row[29] = 10000
            row[40] = 32  # six seconds before diminishing returns for every target type
    elif name == 'ghostly_strike':
        # Dodge is granted only following a successful enemy impact, not self-target resolution.
        g.clear_effect(row, 1)
        if not celestial:
            row[29] = 15000


def patch_technical(g, row, name):
    if name in ('sha_cheap_shot_mark', 'sha_blind_strike'):
        row[49] = 10
    if name == 'celestial_safe_fall_knockback':
        row[110] = 98  # immunity to SPELL_EFFECT_KNOCK_BACK
        g.set_effect(row, 1, 37, 1)
        row[111] = 144  # immunity to SPELL_EFFECT_KNOCK_BACK_DEST
    elif name == 'sha_ghostly_strike_armor':
        row[110] = 1  # physical resistance TOTAL_PCT
    elif name == 'sha_opener_armor':
        row[110] = 1
        row[122:125] = [0xffffffff, 0xffffffff, 0xffffffff]
    if name in DURATIONS:
        row[4] |= 0x80  # hidden technical client-side aura
        row[2] = 0  # not dispellable
    if name == 'celestial_ghostly_strike_tracker':
        row[36] = 0  # proc charges must not remove the dodge aura after the energy proc


def weapon_component(g, template, spell_id, name):
    row = list(template)  # verified native Shiv damage spell 5940, not a school-damage imitation
    row[0] = spell_id
    g.clear_effect(row, 0)  # CP is awarded once by parent hit processing
    row[7] |= 0x10000  # no caster proc chains
    row[8] |= 0x800000  # no item proc; poison explicitly dispatched through native helper
    row[42] = 0
    row[4] |= 0x80
    return row
