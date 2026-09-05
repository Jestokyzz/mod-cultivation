# Установка Cultivation v2.0.0

Скачать `mod-cultivation-v2.0.0-windows-x64.zip` и `SHA256SUMS.txt` из Release. Автоматические GitHub Source code архивы не содержат готовых MPQ/DBC/worldserver.

## Совместимость

Это полный комплект **модуля для совместимого JestokyCraft**, не дистрибутив всей игры и не универсальное ядро AzerothCore. Он содержит клиентские A/X/Z, шесть серверных DBC, принятый worldserver, собственные исходники, минимальные integration patches, SQL, установщик и rollback. Нужны существующие согласованные клиент build 12340 ruRU с Wow-NWQ.exe и серверные runtime DLL. Их точные хэши проверяются по package-manifest.json. EXE клиента, учётные записи, пароли, карты/vmaps/mmaps, конфиги подключения и другие независимые патчи не заменяются этим модулем.

## Обновление установленной Cultivation schema 6

1. Сверить SHA-256 архива и распаковать его в отдельный каталог.
2. Штатно закрыть целевой клиент и worldserver. Убедиться, что доступен резервный диск F:.
3. Сохранить текущие значения mod_cultivation.conf; установщик не перезаписывает существующий файл. Sha DirectDamageBonusCapPvE должен оставаться 60; TestHarness в production отключён.
4. Выполнить в PowerShell из распакованного комплекта:

```powershell
.\installer\Install-Cultivation.ps1 `
  -ServerRoot 'C:\Solo WotLK\WoWBotServer\build\bin\RelWithDebInfo' `
  -ClientRoot 'C:\Games\JestokyCraft' `
  -ServerDataRoot 'C:\Solo WotLK\WoWBotServer\server\data' `
  -SkipSql
```

Пути — пример существующей установки. `ServerRoot` содержит worldserver.exe, `ServerDataRoot` — каталог dbc. Без явного ServerDataRoot установщик читает DataDir фактического worldserver.conf. Для перехода с уже установленной Cultivation schema 6 изменения SQL не требуются. `-SkipSql` нельзя использовать для новой установки или старых Rogue Paths.

## Новая установка и старые Rogue Paths

Для новой установки в совместимую интеграцию убрать `-SkipSql`, указать `-MySqlExe` и правильные имена auth/world/characters БД. Пароль запрашивается интерактивно и не сохраняется в комплекте. Установщик делает логические дампы, SQL preflight/postflight и применяет `sql/fresh`.

Для старых Rogue Paths сначала использовать versioned `sql/upgrade-from-rogue-paths`: внимательно выполнить README, preflight, backup, migration и postflight именно для указанной БД. Не применять fresh SQL поверх старых таблиц. Приложенные rollback SQL и `installer/Rollback-Cultivation.ps1` восстанавливают сохранённое состояние; не удалять резервную копию до проверки.

## Проверка после установки

Запустить сервер штатным способом; проверить готовность мира и `mod-cultivation: startup validation completed; disabled replacement groups=0`. Запускать клиент через **Wow-NWQ.exe**, не Wow.exe. Проверить `.cultivation rogue status`, оба пути, описания до изучения и КД Шага 30 секунд без Подготовки / 21 с ней у Небожителя. При новой Lua-ошибке или crash остановиться и откатиться, не править поверх.

Пользовательская приёмка проведена для тестового комплекта, затем те же хэши установлены в production. Обновлённый установщик реально выполнен с `-SkipSql` на отдельной файловой копии клиента/сервера; все итоговые хэши совпали. Fresh-install сценарий v2.0.0 с SQL целиком повторно не прогонялся. Оставшиеся gameplay-сценарии перечислены в CHANGELOG_RU.md, они не скрыты.
