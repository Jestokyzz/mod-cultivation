"""Aura descriptions describe the active effect, never copy the cast tooltip.

Own $s/$t references bind to the generated row, not its old stock numbers.
Unchanged stock aura wording remains yellow; only changed spans are cyan.
"""
import tooltip_stock as tooltip

# Entries not listed here deliberately retain their own native aura text.
TEXT = {
    'stealth': (
        'Незаметен. {path}Через 3 сек. штраф к скорости передвижения снимается, а уровень незаметности повышается на 1.{/path}',
        'Stealthed. {path}After 3 sec, removes the movement speed penalty and increases Stealth level by 1.{/path}'),
    'evasion': (
        'Вероятность уклонения повышена на $s1%. Шанс попадания по вам издали снижен на $s2%. {path}Получаемый физический урон уменьшен на 15%.{/path}',
        'Dodge chance increased by $s1%. Chance to be hit by ranged attacks reduced by $s2%. {path}Physical damage taken reduced by 15%.{/path}'),
    'cloak_of_shadows': (
        'Вероятность противостояния всем заклинаниям увеличена на {path}$s1%{/path}.',
        'Chance to resist all spells increased by {path}$s1%{/path}.'),
    'feint': (
        'Урон, получаемый от атак по области, снижен на {path}70%{/path}.',
        'Damage taken from area attacks reduced by {path}70%{/path}.'),
    'tricks_of_the_trade': (
        'Угроза от вашей следующей атаки и последующих действий в течение {path}10 сек.{/path} перенаправляется выбранной цели. Наносимый этой целью урон увеличивается на {path}10%{/path}.',
        'Threat from your next attack and subsequent actions for {path}10 sec{/path} is redirected to the selected target. Damage dealt by that target is increased by {path}10%{/path}.'),
    'cold_blood': (
        'Вероятность критического удара {path}следующих двух атакующих способностей{/path} повышена на 100%.',
        'Critical strike chance of your {path}next two offensive abilities{/path} increased by 100%.'),
    'blade_flurry': (
        'Скорость атак повышена на {path}$s1%{/path}. {path}Дополнительный урон равномерно распределяется между ближайшими противниками, не более 4 дополнительных целей.{/path}',
        'Attack speed increased by {path}$s1%{/path}. {path}Additional damage is split evenly among nearby enemies, up to 4 additional targets.{/path}'),
    'adrenaline_rush': (
        'Восполнение энергии увеличено на $s1%. {path}Максимальный запас энергии увеличен на 50.{/path}',
        'Energy regeneration increased by $s1%. {path}Maximum energy increased by 50.{/path}'),
    'killing_spree': (
        'Атакует противника раз в $t1 сек. Наносимый урон увеличен на $61851s3%. {path}Получаемый урон уменьшен на 50%. Приоритет атак — изначально выбранная цель.{/path}',
        'Attacks an enemy every $t1 sec. Damage dealt increased by $61851s3%. {path}Damage taken reduced by 50%. Prioritizes the initially selected target.{/path}'),
    'riposte': (
        'Скорость атаки в ближнем бою снижена на {path}30%{/path}.',
        'Melee attack speed reduced by {path}30%{/path}.'),
    'hemorrhage': (
        'Получаемый физический урон увеличен на $s3 ед. {path}Ваши завершающие приемы не расходуют заряды.{/path}',
        'Physical damage taken increased by $s3. {path}Your finishing moves do not consume charges.{/path}'),
    'shadow_dance': (
        'Возможность использовать некоторые способности, не входя в состояние незаметности. {path}Урон способностей, требующих незаметности, уменьшен на 20%. «Подлый трюк» и «Гаррота» требуют на 15 ед. энергии меньше.{/path}',
        'Allows the use of abilities that require Stealth. {path}Damage from Stealth abilities reduced by 20%. Cheap Shot and Garrote cost 15 less energy.{/path}'),
    'ghostly_strike': (
        'Вероятность уклонения повышена на {path}30%{/path}. {path}Первое успешное уклонение восстанавливает 20 ед. энергии.{/path}',
        'Dodge chance increased by {path}30%{/path}. {path}The first successful dodge restores 20 energy.{/path}'),
    'premeditation': (
        'Сохраняет {path}3{/path} приема серии в течение {path}30 сек.{/path}',
        'Retains {path}3{/path} combo points for {path}30 sec{/path}.'),
}


def active(g, row, base, entry, strings, manifest, locale_index):
    name = entry['logical_name']
    if entry['section'] != 'active_spells':
        return
    standard = g.read_string(strings, base[g.SPELL_TOOLTIP + locale_index])
    text = TEXT[name][0 if locale_index == 8 else 1] if name in TEXT else standard
    # Empty native AuraDescription is intentional for spells with no buff.
    rendered = tooltip.exact(tooltip.bind_stock_fields(text, row[0]), manifest['path_icons']['celestial_color']) if text else ''
    g.set_string(row, strings, g.SPELL_TOOLTIP + locale_index, rendered)


def technical(g, row, name, strings, manifest, locale_index):
    presentation = manifest['technical_presentation'][name]
    if not name.startswith('celestial_') or presentation['visibility'] != 'visible':
        return
    # Some technical IDs replace a stock buff: keep that stock wording yellow.
    inherited = {
        'celestial_ghostly_strike_tracker': TEXT['ghostly_strike'],
        'celestial_cold_blood_window': TEXT['cold_blood'],
        'celestial_tricks_boost': (
            'Наносимый урон увеличен на {path}10%{/path}.',
            'Damage dealt increased by {path}10%{/path}.'),
        'celestial_overkill_bonus': (
            'Скорость восстановления энергии повышена на 30%.',
            'Energy regeneration rate increased by 30%.'),
    }
    if name in inherited:
        g.set_string(row, strings, g.SPELL_TOOLTIP + locale_index,
                     tooltip.exact(inherited[name][0 if locale_index == 8 else 1], manifest['path_icons']['celestial_color']))
        return
    # Entirely new effects have no stock yellow base.
    text = g.read_string(strings, row[g.SPELL_TOOLTIP + locale_index])
    if text:
        g.set_string(row, strings, g.SPELL_TOOLTIP + locale_index,
                     tooltip.exact('{path}' + text + '{/path}', manifest['path_icons']['celestial_color']))
