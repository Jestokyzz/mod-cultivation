# История изменений

## 2.0.0-candidate2 — не принят

### Исправлено

- Fresh-install SQL теперь создаёт `creature_template` и model rows клона «Шага сквозь тень» (`900406`).
- Внутренний DB-bound script переименован в `npc_cultivation_rogue_shadowstep_clone`; startup больше не должен выдавать `Script named ... is not assigned in the database`.
- Postflight и архитектурный regression требуют точное совпадение C++ registration, fresh SQL и upgrade SQL.

### Известные ограничения

- Кандидат не становится релизом до явного GUI/gameplay acceptance пользователя.

## 2.0.0-candidate1 — не принят

### Изменено

- Система переименована из Rogue Paths в Cultivation.
- Реализация разбойника выделена в подсистему `rogue`.
- Команда `.roguepath <действие>` заменена на `.cultivation rogue <действие>`.
- Loader, конфигурация, ScriptName, таблицы постоянного состояния и SQL переведены в пространство имён Cultivation/Rogue.

### Исправлено

- Миграция переименовывает существующие characters-таблицы без потери выбранного пути и сохранённых кнопок.
- Добавлена regression-проверка, запрещающая возврат старой активной команды и старых имён интеграции.

### Известные ограничения

- Кандидат ещё не прошёл пользовательскую игровую приёмку.
- До приёмки нет тега, GitHub Release и merge в `main`.
