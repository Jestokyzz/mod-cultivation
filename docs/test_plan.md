# Acceptance: отдельный клиент и сервер

Статусы ниже относятся к реальным испытаниям, а не наличию кода.

| Проверка | Статус |
|---|---|
| worldserver compile/link | PASS, schema-5 candidate9 |
| Offline: ID, числовая семантика, ранги/имена/иконки, ranges/radii, technical effects, SLA, enUS, SQL, Lua 5.1 | PASS: 33 core + 13 visibility Lua + 21 talent/UI Lua checks |
| SQL на rogue_paths_test_* и повторная миграция | PASS: schema 5 дважды, `CREATE TABLE IF NOT EXISTS`, postflight |
| MPQ extract + SHA-256 DBC/иконок | PASS: 6 DBC readback, 92 BLP, сохранены остальные known members |
| worldserver startup, custom ID validation | PASS candidate9: `disabled replacement groups=0` |
| Небожитель: реальные замены, action slots, talent gating | PASS world protocol; combat/GUI отдельно |
| Ша: реальные замены/action slots/talent gating | PASS world protocol; passive combat triggers отдельно |
| Небожитель→Ша→Небожитель→Ша→Небожитель→reset | PASS: ordinary slots сохранены, Preparation suppressed-row создан/удалён на каждом шаге |
| relog и restart persistence | Relog PASS для path/actionbar/cooldown; внешний restart ещё не выполнен |
| Assassination/Combat/Subtlety, talent reset, dual spec | НЕ ВЫПОЛНЕН |
| downranking и macro buttons | НЕ ВЫПОЛНЕН |
| Preparation fresh-state: 3:00 before talent → 2:06 immediately after learn → first cast 2:06 → reset 3:00 → relearn/relog 2:06 | GUI acceptance ожидается; native non-triggered transition PASS `180000 -> 126000`, post-cast modifier отсутствует |
| Preparation full masks: Cold Blood/Shadowstep/Vanish/Evasion/Sprint; glyph adds Dismantle/Kick/Blade Flurry; Ghostly Strike unchanged | Native `ApplySpellMod` PASS для обоих списков; GUI spellbook/tooltips ожидаются |
| Vanish→switch→Preparation→switch→reset cooldown exploit | НЕ ВЫПОЛНЕН |
| Poison: 0/3/4/5 own stacks, чужие дозы, Envenom, dispel, recursion | НЕ ВЫПОЛНЕН |
| Rupture/Garrote: тики, длительность, сумма урона, refresh | НЕ ВЫПОЛНЕН |
| PvP/pets, DR, immune/miss/dodge, Cheat Death, GUID ownership | НЕ ВЫПОЛНЕН |
| другой класс и обычный RBAC без GM | PASS для warrior 80 и rogue 1 без account_access |
| 1920x1080 client: spellbook/tooltips/macros, FrameXML/errors/crash | НЕ ВЫПОЛНЕН |

## Schema-5 candidate9: Celestial native regression

- Runtime report: `generated/v1.5.0/celestial_native_test.json`, status `passed`, summary `98/0`.
- Kidney Shot: пять реальных cast, длительности 2/3/4/5/6 секунд; дополнительный runtime duration modifier отсутствует.
- Ambush: реальный cast за пределом штатных 5 ярдов успешен, за пределом custom range отклонён.
- Preparation: базовый и glyph-списки получают нативные 70% базового КД до каста; Sprint подтверждён real-cast переходом `180000 -> 126000`, отдельный `SMSG_MODIFY_COOLDOWN` запрещён и отсутствует. Уже идущий КД Cold Blood остаётся неизменным после `SyncPlayerSpells`; glyph-маска не затрагивает Ghostly Strike.
- Ghostly Strike: 30% dodge на 10 секунд после hit, ноль приёмов серии.
- Shadowstep: реальный cast на союзника, безопасная позиция, отсутствие origin-clone, снятие замедления/сковывания и отсутствие бонуса урона следующей атаки.
- Fan of Knives: три уникальные цели дают ровно 12 энергии независимо от poison/proc и off-hand событий.
- GUI/client acceptance остаётся `pending` до явной проверки пользователя; кандидат не является known-good релизом.

Для каждого runtime случая сохраняются path, исходные и итоговые spell IDs, talent ranks, action slots, cooldown timestamps, cast IDs и actual damage/heal. Для периодики сравниваются количество тиков и полный урон; для modifiers — health delta, combat log и floating text. Удар от каждого оружия Fan/Mutilate проверяется отдельно. Для персональных эффектов требуются второй разбойник и контролируемый pet.

Новая ошибка клиента останавливает испытание: rollback к baseline, сохранение failed-артефактов и логов только на F:, фиксация причины и regression до следующего кандидата. Результат становится known-good только после явного принятия пользователем.

## Обязательный gate после повторного сообщения о той же неисправности

1. Текущий кандидат и использованная архитектура помечаются failed.
2. Повторять тот же AddOn, Lua-hook, server hook или пакет с другими условиями запрещено.
3. Требование переписывается в наблюдаемый переход до первого использования или изучения.
4. Определяется первичный источник значения и создаётся regression, воспроизводящий исходный симптом на чистом состоянии.
5. Новый кандидат проверяется в порядке: static → native runtime → протокол → чистый GUI до первого изучения → learn/cast/reset/relog.
6. Пока последний GUI-шаг не подтверждён пользователем, статус остаётся `candidate-unaccepted`, а формулировка «исправлено» не используется.
## Seal Fate rollback regression

- Все пять рангов Небожителя сохраняют стандартный proc Seal Fate.
- При 5 приёмах серии одно потерянное стандартное срабатывание восстанавливает 5 энергии.
- За одну секунду восстанавливается не более 10 энергии; следующий секундный интервал снова допускает восстановление.
- При числе приёмов серии меньше 5 дополнительная энергия не выдаётся.
- Все пять display-only рангов сохраняют штатный центр иконки Seal Fate с рамкой выбранного пути; `INV_Qiraj_JewelGlyphed` запрещён.
- Тултип в ruRU/enUS содержит прежнее описание конвертации, а вариант Ша остаётся неизменным.

## Candidate35: Combat Potency / Sprint

- Static: все native talent branches ruRU/enUS не содержат `{rank}`; Celestial «Боевой потенциал» рангов 1–5 содержит соответственно `1..5 ед. энергии`.
- Native runtime: настоящий Celestial Sprint при активной Celestial Stealth сохраняет Stealth, снимает Entangling Roots/Hamstring, блокирует новые root/snare 4 сек. и после окончания снова допускает их.
- Protocol result: `113/0`, включая `sprint-preserves-stealth`; Preparation Sprint packet остаётся `126000`, post-cast correction отсутствует.
- GUI 1920x1080: ожидается проверка пользователем тултипа `0/5` и Sprint из незаметности; до неё candidate35 остаётся `candidate-unaccepted`.

## Schema-5 repeated switching / action bars

- Runtime report: `generated/v1.5.0/world_protocol_test.json`, status `passed`.
- Fixture cycle: Небожитель → Ша → Небожитель → Ша → Небожитель → reset, затем sync, logout/relog и повторный Ша.
- Проверены DB path/schema, все downrank spell buttons, отсутствие opposite path и unearned talent variants, сохранение cooldown и точное состояние `character_cultivation_rogue_suppressed_action`.
- Существующий персонаж `2523` не изменялся runtime fixture: schema 5, путь Небожителя, 12 прежних action records. В доступных baseline SQL отсутствует историческая кнопка Preparation, поэтому её старый slot нельзя восстанавливать догадкой.

## Candidate41: единый контракт Ша

- Static PASS: шесть DBC генерируются из одного manifest; client/server копии идентичны, 94 BLP проходят readback, 600 tooltip-записей и 31 Lua 5.1 UI-проверка не содержат удалённых формулировок.
- До запуска test-server его `mod_cultivation.conf` сравнивается с текущим `.conf.dist`. Запрещены старые `PvP`, `MarkCharges`, `ArmorIgnore`, `FrontShadowstepDamage`, `BlindDamage`, `SapDamage` и аналогичные overrides.
- Native значения: Evasion `120000 ms / 8000 ms`, Blind `5000 ms`, Cheap Shot `3000 ms`, Sap `65 energy / 6000 ms / 10000 ms`, Backstab stock cost, Ambush `75 energy`, Expose Armor `35%`, Vanish energy `4 x 10`.
- Native report `generated/v1.5.0/sha_candidate41_native_test.json`: PASS `31/0` на установленном candidate44. Помимо runtime Config/DBC, через фактический ScriptMgr pipeline проверены melee/direct/periodic множители Cheap `1100/1000` и Kidney `1150/1000` от другого источника, а также правила снятия Gouge.
- Runtime: собственные poison/bleed ticks не снимают Sha Gouge; Sprint не создаёт post-slow; каждое уклонение даёт 5 энергии; Cheap/Kidney увеличивают фактический входящий урон любого источника на 10%/15%; Deadly Throw даёт попадания в `0/1/2 s`; Vanish восстанавливает 40 энергии за 4 секунды.
- Damage acceptance: Backstab и Ambush сравниваются на существе и player-controlled цели; обе цели получают одинаковую ветку. Проверяются отдельно direct multiplier и итоговый critical multiplier, чтобы текст не подменял механику.
- Control acceptance: Cheap `3 s`, Blind `5 s`, Sap максимум `6 s` с корректным DR; Sap разрешён на цели в бою, добавляет 2 CP и повторно доступен через 10 секунд.
- GUI 1920x1080 borderless: до первого изучения и после него тексты совпадают с generated DBC, изменённые фрагменты окрашены в цвет Ша, заголовок ранга присутствует, новые иконки Stealth Mastery видны в обоих путях.
- До пользовательского GUI-подтверждения статус только `candidate installed, client acceptance pending`.

## Candidate46: механика, тексты и иконки аур

- Static: 600 локализованных tooltip-записей, 343 icon mapping, 43 display-записи, 19 TalentUI узлов и 97 BLP; все проверки PASS.
- Native report: `generated/v1.5.0/sha_candidate41_native_test.json`, результат `40/0` на установленном candidate46.
- Проверено загруженное сервером: Sap без stance-требования, `65 energy / 6 s / 10 s`; Adrenaline Rush `10 s` и штраф `4 s`; Preparation `390 s`; Shadow Dance `5 s`; Ghostly Strike `25 energy`, debuff цели `-20% armor / 6 s`; Overkill `8 s`; Cheat Death `+25% / 2 s`.
- Проверка иконок: каждый active variant использует стандартный base-rank `ActiveIconID`; каждая видимая technical-аура использует stock `icon_source_spell`, кроме явно утверждённых общих иконок 6194/6195.
- GUI 1920x1080 borderless: сверить стандартный рисунок каждого реально появившегося бафа/дебафа и одновременно правильный текст пути; отдельно проверить новые общие метки и два имени Stealth Mastery. До этого статус `candidate installed, client acceptance pending`.

## Candidate47: иконки технических аур Небожителя (GUI-отклонён)

- Static: `celestial_shiv_protection` обязан иметь SpellIcon 1960 и разрешаться в `Interface\\Icons\\Ability_Creature_Poison_06`; прежний `Ability_Rogue_DualWeild` запрещён.
- Static: `celestial_stealth_mastery` обязан называться `Мастерство незаметности` / `Stealth Mastery`, иметь SpellIcon 6196 и разрешаться в общий нерамочный `Interface\\Icons\\ability_rogue_surpriseattack2`.
- Regression: display-пассивка «Мастерство незаметности» сохраняет отдельную рамочную иконку Небожителя 6192; gameplay/non-string поля обеих технических аур не меняются.
- Native report `generated/v1.5.0/sha_candidate41_native_test.json`: PASS `40/0` на установленном candidate47; это серверная regression-проверка, а не GUI acceptance.
- GUI 1920x1080 borderless: после входа Небожителем получить обе реальные ауры и проверить точные имя/рисунок/текст. До пользовательского подтверждения статус только `candidate installed, client acceptance pending`.

GUI candidate47 показал, что общий нерамочный icon 6196 для «Мастерства незаметности» не соответствует требованию. Этот выбор запрещён candidate48 regression.

## Candidate48: рамка «Мастерства незаметности» Небожителя

- Static: техническая аура 86542 и display-пассивка 86620 обязаны иметь один SpellIconID 6192, разрешаемый в `Interface\\Icons\\ability_rogue_surpriseattack2_celestial`; icon 6196 у ауры запрещён.
- Regression: относительно candidate47 у Spell 86542 меняется только поле SpellIconID 133; имя, описание, ActiveIconID и все gameplay-поля остаются прежними. «Фатальное снадобье» сохраняет SpellIcon 1960.
- GUI 1920x1080 borderless: после трёх секунд незаметности проверить цветную Небожительскую рамку у реальной ауры. До пользовательского подтверждения статус только `candidate installed, client acceptance pending`.
