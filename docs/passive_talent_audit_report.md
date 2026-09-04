# Аудит пассивных талантов

Статус: static-pass-runtime-pending

- Display-only записей: 43; TalentUI узлов: 19.
- Бойня, Печать судьбы, Мастер ядов, Боевой потенциал, Обман смерти, Воровская честь — каждый ранг и оба пути.
- Активные талантовые способности включены в карту Talent.dbc для дополнения штатного tooltip.
- Механические ауры отделены от видимых записей; новых proc/effect у display нет.
- SyncVisibleTalentPassives: active spec / exact highest rank / selected path; отдельные циклы удаления и изучения.
- Сброс талантов, dual spec, relog, смена пути и отсутствие двойного эффекта в игре: НЕ ПРОВЕРЕНЫ для schema 3.

Полная построчная проверка: `generated/schema3-audit/artifact-validation.json`.
