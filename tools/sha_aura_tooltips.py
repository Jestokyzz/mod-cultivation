"""Native Sha buff descriptions: effects, never the stock cast text plus delta."""
import tooltip_stock as tooltip

TEXT = {
    'stealth': ('Незаметен. Скорость передвижения снижена на $s3%. {path}Первая специальная прямая атака из незаметности или в течение 3 сек. после выхода стоит на 20 ед. энергии меньше и наносит на 10% больше урона.{/path}',
                'Stealthed. Movement speed reduced by $s3%. {path}The first special direct attack from Stealth or within 3 sec after leaving it costs 20 less energy and deals 10% more damage.{/path}'),
    'evasion': ('Вероятность уклонения повышена на $s1%. Шанс попадания по вам издали снижен на $s2%. {path}Уклонение восстанавливает 5 ед. энергии.{/path}',
                'Dodge chance increased by $s1%. Chance to be hit by ranged attacks reduced by $s2%. {path}Dodging restores 5 energy.{/path}'),
    'cloak_of_shadows': ('Вероятность противостояния заклинаниям повышена на $s1%. {path}Собственные яды наносят на 20% больше урона и не могут промахнуться или быть сопротивлены.{/path}',
                         'Chance to resist spells increased by $s1%. {path}Your poisons deal 20% more damage and cannot miss or be resisted.{/path}'),
    'feint': ('Получаемый урон от атак по области снижен на {path}30%{/path}.',
              'Damage taken from area attacks reduced by {path}30%{/path}.'),
    'cold_blood': ('Вероятность критического удара следующей {path}специальной прямой атаки{/path} повышена на 100%. {path}Итоговый критический урон увеличен на 40%.{/path}',
                   'Critical strike chance of the next {path}special direct attack{/path} increased by 100%. {path}Final critical damage increased by 40%.{/path}'),
    'tricks_of_the_trade': ('Угроза следующей атаки и последующих действий перенаправляется выбранной цели. Её урон увеличивается на {path}25% на 4 сек.{/path}',
                            'Threat from your next attack and subsequent actions is redirected to the selected target. Its damage is increased by {path}25% for 4 sec{/path}.'),
    'blade_flurry': ('Скорость атак повышена на {path}50%{/path}. Атаки поражают дополнительного ближайшего противника {path}силой 100% урона. Стоимость атакующих способностей увеличена на 20%.{/path}',
                     'Attack speed increased by {path}50%{/path}. Attacks strike an additional nearby enemy {path}for 100% damage. Offensive abilities cost 20% more energy.{/path}'),
    'adrenaline_rush': ('Восполнение энергии увеличено на {path}200%{/path}.',
                        'Energy regeneration increased by {path}200%{/path}.'),
    'killing_spree': ('Атакует противника раз в $t1 сек. Наносимый урон увеличен на {path}30%{/path}. {path}Получаемый урон увеличен на 20%.{/path}',
                      'Attacks an enemy every $t1 sec. Damage dealt increased by {path}30%{/path}. {path}Damage taken increased by 20%.{/path}'),
    'riposte': ('{path}Скорость атаки повышена на 25%.{/path}', '{path}Attack speed increased by 25%.{/path}'),
    'hemorrhage': ('Физический урон, получаемый {path}от применившего эффект разбойника{/path}, увеличен на {path}$s3{/path}.',
                   'Physical damage taken {path}from the rogue who applied the effect{/path} increased by {path}$s3{/path}.'),
    'shadow_dance': ('Возможность использовать некоторые способности, не входя в состояние незаметности. {path}«Подлый трюк» недоступен. «Внезапный удар» и «Удар в спину» стоят на 20 ед. энергии меньше и наносят на 30% больше урона.{/path}',
                     'Allows use of abilities that require Stealth. {path}Cheap Shot is unavailable. Ambush and Backstab cost 20 less energy and deal 30% more damage.{/path}'),
    'expose_armor': ('Броня снижена на {path}35%{/path}.', 'Armor reduced by {path}35%{/path}.'),
    'ghostly_strike': ('{path}Скорость атаки повышена на 20%, итоговая броня цели уменьшена на 20%.{/path}',
                       "{path}Attack speed increased by 20%; the target's final armor is reduced by 20%.{/path}"),
    'premeditation': ('Сохраняет 2 приёма серии в течение {path}6 сек.{/path}',
                      'Retains 2 combo points for {path}6 sec{/path}.'),
    'envenom': ('', ''),  # Sha does not create the stock poison-proc buff.
}


def active(g, row, base, entry, strings, manifest, locale_index):
    if entry['section'] != 'active_spells':
        return
    standard = g.read_string(strings, base[g.SPELL_TOOLTIP + locale_index])
    text = TEXT.get(entry['logical_name'], (standard, standard))[0 if locale_index == 8 else 1]
    rendered = tooltip.exact(tooltip.bind_stock_fields(text, row[0]), manifest['path_icons']['sha_color']) if text else ''
    g.set_string(row, strings, g.SPELL_TOOLTIP + locale_index, rendered)
