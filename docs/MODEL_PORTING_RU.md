# Перенос моделей и эффектов Cultivation

Общие ресурсы принадлежат модулю, а не каталогу `src/rogue`.
Asset registry расположен в корневом `models-manifest.json`.

## Обязательная цепочка

1. Зафиксировать исходный CASC product/build, FileDataID, оригинальное имя и SHA-256.
2. Извлечь M2 и все SFID/TXID/AFID/BFID зависимости. SKID/child models разрешить явно.
3. Конвертировать структуру MD21/MD20 в Wrath, не ограничиваясь номером версии.
4. Проверить header/payload overlap, вложенные track descriptors, lookup indices,
   bone palettes/influences, opacity/material и циклы UV/particles.
5. Собрать clean asset MPQ отдельно от итоговых client/server DBC и SQL.
6. Проверить весь virtual-path graph и единственного custom-owner каждого пути.
7. Проверить world NPC, подход/удаление/возврат, relog и эффекты дольше 60 секунд.

## Подтверждённые ловушки

- Расширение заголовка в байтах 304–311 перезаписывает source global-loop durations;
  на других моделях там бывают name/sequences. Переместить payload до записи header.
- Поверхностная копия M2Color track делит mutable nested descriptors между владельцами.
  Loader делает повторный fixup и может упасть по 0082AF8A. Клонировать descriptor arrays.
- TextureWeightCombo 65535 не означает универсальную непрозрачность; проверять конечный track.
- Прямой `PlayerModel:SetModel` не доказывает загрузку world display/model DBC:
  обязательны реальные NPC и проверка effective locale-owner.
- Дыхание пандарена не доказывает работу огня/молний. UV/global cycles проверяются отдельно.
- Цветовой множитель может почти не менять сине-белый source. Проверять конечную текстуру,
  не только числа tint; не изменять alpha или анимации при перекраске.
- Старый MultiConverter может удалять particles. Такой результат не является полным портом FX.
- Современный EdgeFade не идентичен Wrath diffuse approximation: жёсткие полосы возможны.
  Не выдавать художественную визуализацию за доказательство доступной игровой модели.

## Имена и общие иконки

Исходные basenames M2 сохраняются. Каталог варианта (`original`, `sha`, `celestial`)
не заменяет source identity. Файлы baked appearance отличать от исходного NPC ID.
Две переиспользуемые иконки: `sha_ability_rogue_envelopingshadows` (FDID 651083),
`achievement_faction_celestials` (FDID 645203). Клиентские SpellIcon IDs — в
`data/path_status.json`; нельзя путать их с FDID.

## Отложенный маппинг

Объекты осквернения, столы, фонари, флаги и статуи исключены из этого релиза.
Экспериментальный particle-layout converter и визуально не принятая композиция
не считаются принятой частью NPC-порта. Исходники сохранены локально для будущей работы.
