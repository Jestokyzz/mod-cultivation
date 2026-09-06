# Установка полного комплекта Cultivation

Комплект устанавливается только поверх существующего совместимого сервера AzerothCore и клиента JestokyCraft 3.3.5a build 12340. Карты, vmaps, mmaps и базовые MPQ World of Warcraft в комплект не входят.

В v2.1.0 включены `worldserver.exe` с модулем, восемь серверных DBC, конфигурация, SQL, девять клиентских MPQ, исходники, manifest, SHA-256 и результаты проверок. Актуальная инструкция — `INSTALL_RU.md` в корне архива (в исходниках `docs/install-v2.1.0.md`). Для обновления с v2.0.0 используйте `-UpgradeFrom200`. Маппинг не входит.

Перед установкой остановите клиент, `worldserver` и `authserver`:

```powershell
.\installer\Install-Cultivation.ps1 `
  -ServerRoot 'C:\path\to\server' `
  -ClientRoot 'C:\path\to\JestokyCraft' `
  -BackupRoot 'F:\JestokyCraft Backups' `
  -MySqlExe 'C:\path\to\mysql.exe' `
  -AuthDatabase 'acore_auth' `
  -WorldDatabase 'acore_world' `
  -CharactersDatabase 'acore_characters'
```

Пароль MySQL запрашивается интерактивно и не сохраняется. До изменений установщик проверяет SHA-256, отсутствие активных процессов, сохраняет заменяемые файлы и делает полные дампы трёх БД.

При обнаружении таблиц прежнего `mod-rogue-paths` свежий установщик остановится. Для такого сервера сначала применяется versioned schema-6 upgrade из `sql/upgrade-from-rogue-paths/`; пересоздавать таблицы с потерей состояния установщик не будет.

После установки используйте `.cultivation rogue celestial`, `.cultivation rogue sha`, `.cultivation rogue status`, `.cultivation rogue sync` и `.cultivation rogue reset`.

Статус архива — кандидат. Успешная установка не заменяет игровую проверку клиента.
