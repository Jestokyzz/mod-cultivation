# Технический регламент Cultivation

В рабочем проекте полный регламент — `C:\Solo WotLK\CLIENT_MODDING_RULES.md`.
Этот переносимый файл фиксирует обязательный минимум для модуля, не заменяя его.

Перед записью: подтвердить точный NWQ client path, inventory/SHA-256, проверенный
backup вне активного клиента (в проекте только F:\JestokyCraft Backups), clean staging.
Не менять official MPQ и не редактировать активный архив на месте. Один virtual path —
один custom-owner; FrameXML.toc также один. Неполный listfile не использовать для
реконструкции/compact. Для точечной замены — копия known-good, readback и SHA-256.

Модельный порт регулируется [MODEL_PORTING_RU.md](docs/MODEL_PORTING_RU.md):
source build/FDID/hash, замкнутые зависимости, исходные имена, header relocation,
mutable descriptor ownership, opacity/skin indices, отдельная проверка global/UV loops.
Эффекты не отбрасывать молча. Не считать SetModel достаточным тестом world NPC.
Использовать общий models-manifest.json и data/path_status.json, не создавать дублей.

Client/server DBC генерировать согласованно, custom records сравнивать семантически,
stock server enUS Playerbots и ruRU client не заменять друг другом целиком.
SQL: точная WORLD/CHARACTERS/AUTH база, UTF-8, preflight, backup, postflight, rollback.
Любой новый crash/Lua error — остановка, откат, разбор причины и regression.
Клон — 1920x1080 borderless (gxWindow=1, gxMaximize=1); GUI acceptance отдельно от static PASS.
Не публиковать failed/deferred mapping, приватные данные или исходники всего ядра.
