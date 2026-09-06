# Cultivation: правила сопровождения

Общие модели, NPC, иконки, manifests и документация находятся на верхнем уровне модуля.
`src/rogue` — классовая подсистема, не корень релиза.

Перед изменениями читать корневой проектный CLIENT_MODDING_RULES.md и
docs/MODEL_PORTING_RU.md. Сохранять original asset names, FileDataID/build/source hashes.
Любая модель требует проверки зависимостей, уникального владения mutable tracks,
global loops, opacity/SKIN и world acceptance дольше 60 секунд. SetModel и сборка
не заменяют реальную проверку NPC. Иконки paths переиспользовать из data/path_status.json.

Не включать отложенный маппинг, failed/probe материалы, SQL dumps, приватные конфиги,
WTF, SavedVariables, секреты или полное дерево AzerothCore/Playerbots.
Main/теги/Release — только согласованный комплект с SHA-256, SQL pre/postflight,
rollback и явной compatibility matrix. Готовые большие файлы — в Release assets, не Git.
