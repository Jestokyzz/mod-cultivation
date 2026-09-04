# mod-cultivation

Статус: **кандидат разработки `v2.0.0-candidate1`, не принятый релиз**. Production-клиент и production-БД этим кандидатом не изменяются.

## Архитектура

`Cultivation` — верхнеуровневая система развития классов. Каждая классовая реализация живёт в собственной подсистеме. Сейчас реализована первая подсистема:

```text
Cultivation
└── rogue
    ├── Celestial / Небожитель
    └── Sha / Ша
```

Корневая точка загрузки — `Addmod_cultivationScripts()`. Общая команда и маршрутизация находятся в `src/CultivationCommand.cpp`, вся механика разбойника — в `src/rogue/`. Новые классы должны добавляться отдельными каталогами `src/<subsystem>` и не смешивать своё состояние с таблицами rogue.

## Команды

```text
.cultivation rogue celestial
.cultivation rogue nebozhitel
.cultivation rogue небожитель
.cultivation rogue sha
.cultivation rogue ша
.cultivation rogue status
.cultivation rogue sync
.cultivation rogue reset
```

Старая команда `.roguepath` удалена. RBAC 1001 теперь называется `Command: cultivation` и защищает корневую команду `.cultivation`.

## Постоянное состояние

Единственный источник выбора пути rogue — таблица `character_cultivation_rogue`. Подавленные кнопки хранятся в `character_cultivation_rogue_suppressed_action`. Миграция `data/sql/migrations/2.0.0` переименовывает прежние таблицы и сохраняет строки персонажей; пересоздание с потерей данных запрещено.

Схема 6 также переводит:

- `roguepath` → `cultivation` в таблице `command`;
- `Command: roguepath` → `Command: cultivation` в RBAC;
- прежние `spell_rogue_path_*` / `spell_rog_path_*` → `spell_cultivation_rogue_*` в `spell_script_names`.

Для auth, world и characters используются отдельные `preflight`, `up`, `postflight` и `rollback`. Перед изменением даже тестовой БД сервер должен быть остановлен, а проверенный дамп сохранён только в `F:\JestokyCraft Backups`.

## Сборка и генерация

Целевая ревизия AzerothCore: `7c8ed00e7f654617a47bdf728b49707f60aa1aae`, ветка `release/solitary-1.4.5-rc1`.

Из `C:\Solo WotLK`:

```powershell
& .\WoWBotServer\azerothcore-wotlk\modules\mod-cultivation\tools\build_data.ps1
& .\work\BUILD_SERVER.bat
```

CMake автоматически обнаруживает `modules/mod-cultivation/src`. Конфигурация устанавливается как `configs/modules/mod_cultivation.conf`; ключи rogue имеют префикс `Cultivation.Rogue.`.

Manifest custom Spell ID — `data/cultivation_rogue_spell_manifest.json`. Один генератор создаёт клиентские ruRU и серверные enUS DBC и сравнивает их числовые поля. Различие локализованных строк ожидаемо; произвольная замена всего клиентского DBC серверной копией запрещена.

## Клиентская часть

Модуль использует игровые DBC/MPQ и нативный FrameXML. AddOn не является способом реализации механик или первоначальных тултипов и не входит в репозиторий либо устанавливаемый клиентский комплект. Локальные исторические AddOn-фикстуры исключены через `.gitignore`.

MPQ собирается из clean staging либо точечной заменой документированного пути в копии известного custom MPQ с обязательным обратным извлечением и SHA-256. Official MPQ не изменяются и не реконструируются по неполному `(listfile)`.

Тестовый клиент запускается только из явно названного каталога `C:\Solo WotLK\test-client` с:

```text
SET gxWindow "1"
SET gxMaximize "1"
SET gxResolution "1920x1080"
```

## Проверки кандидата

До публикации релиза обязательны:

1. `tools/build_data.ps1` без ошибок, включая `test_cultivation_architecture.py`.
2. Чистая CMake-конфигурация, компиляция и линковка worldserver с `mod-cultivation` и без `mod-rogue-paths`.
3. Миграция схемы 6 в изолированных `cultivation_test_*_v1` DB: preflight → up → postflight, с проверкой сохранения строк.
4. Загрузка изолированного worldserver без новых ошибок и выполнение `.cultivation rogue status`, смены пути, `sync` и `reset`.
5. GUI/gameplay acceptance в clone-клиенте 1920×1080 borderless.
6. Явное подтверждение пользователя.

Компиляция и offline-тесты сами по себе означают только `candidate installed, client acceptance pending`. До подтверждения запрещены merge в `main`, тег и GitHub Release.

## Полный устанавливаемый комплект

`tools/package_full_candidate.ps1` собирает из проверенного test-client/test-server единый архив для совместимой установки. В него входят клиентские MPQ `A/Z/X`, серверный `worldserver.exe`, согласованные server DBC, конфигурация, SQL, исходники, проверки и `package-manifest.json` с SHA-256 каждого файла. Установка выполняется через `installer/Install-Cultivation.ps1` с обязательным внешним backup и дампами БД.

Большие бинарные артефакты не добавляются в историю Git. После явной игровой приёмки полный архив прикладывается к GitHub Release; до этого он остаётся кандидатом.

## GitHub

Это отдельный модуль и отдельный Git-репозиторий; всё дерево AzerothCore в него не включается. Кандидат допускается отправлять только в отдельную candidate-ветку после проверки GitHub-владельца, имени репозитория и visibility. Принятый релиз публикуется по SemVer и должен содержать исходники, SQL, генераторы, manifest/SHA-256, инструкции установки/rollback и полный устанавливаемый комплект.
