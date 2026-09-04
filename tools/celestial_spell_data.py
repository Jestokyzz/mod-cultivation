"""Schema 2 Celestial overrides; Sha rows are deliberately untouched."""
from pathlib import Path
import struct

RU = {
    'fan_of_knives': 'радиус действия — 12 м. Каждая поражённая цель восстанавливает 4 ед. энергии.',
    'feint': 'на 8 сек. уменьшает получаемый урон от атак по области на 70%.',
    'sprint': 'при применении снимает эффекты замедления и обездвиживания и даёт невосприимчивость к ним на 4 сек.',
    'evasion': 'базовая длительность — 20 сек. Пока действует эффект, получаемый физический урон уменьшается на 15%.',
    'ambush': 'дальность действия составляет 8 м.; создаёт 3 приёма серии.',
    'dismantle': 'после окончания разоружения цель ещё 6 сек. наносит на 20% меньше урона.',
    'cheap_shot': 'Стоимость −10 (минимум 10), оглушение +0,5 сек., 3 приёма серии. После оглушения цель на 4 сек. наносит на 15% меньше урона.',
    'kidney_shot': 'длительность оглушения увеличена на 1 сек. до применения уменьшения длительности.',
    'vanish': 'снимает отрицательные эффекты периодического урона, замедления и обездвиживания. Остальные эффекты контроля не снимаются.',
    'blind': 'при успешном наложении с цели удаляются все отрицательные эффекты периодического урона независимо от их источника.',
    'sap': 'Дальность +5 м.; длительность +2 сек. до DR. Досрочное игровое снятие эффекта на 4 сек. замедляет цель на 70% и уменьшает наносимый ею урон на 20%.',
    'preparation': 'пассивно сокращает итоговое время восстановления «Хладнокровия», «Шага сквозь тень», «Исчезновения», «Ускользания» и «Спринта» на 30%. Символ подготовки также добавляет «Долой оружие», «Пинок» и «Шквал клинков». Уже идущая перезарядка не изменяется.',
}
EN = {
    'fan_of_knives': '12-yard radius. Each unique target hit restores 4 energy.',
    'feint': 'Reduces damage taken from area attacks by 70% for 8 seconds.',
    'sprint': 'Removes slows and roots and grants immunity to them for 4 seconds. Normal Sprint speed and duration remain.',
    'evasion': 'Base duration 20 seconds. Reduces all physical damage taken by 15% while active.',
    'ambush': 'Range is 8 yards and awards 3 combo points.',
    'dismantle': 'After the disarm ends, the target deals 20% less damage for 6 seconds.',
    'cheap_shot': 'Costs 10 less energy (minimum 10), stun lasts 0.5 seconds longer, awards 3 combo points. After the stun, the target deals 15% less damage for 4 seconds.',
    'kidney_shot': 'Stun duration is increased by 1 second before diminishing returns.',
    'vanish': 'Removes harmful periodic damage, slow and root effects. Other control effects are not removed.',
    'blind': 'On successful application removes every harmful periodic-damage aura regardless of caster.',
    'sap': 'Range +5 yards; duration +2 seconds before diminishing returns. Early gameplay removal slows the target by 70% and reduces its damage dealt by 20% for 4 seconds.',
    'preparation': 'Passively reduces final cooldown of Cold Blood, Shadowstep, Vanish, Evasion and Sprint by 30%. Glyph of Preparation also adds Dismantle, Kick and Blade Flurry. Running cooldowns are unchanged.',
}
NAMES = {'vanish':'Исчезновение', 'sprint':'Спринт', 'evasion':'Ускользание', 'feint':'Ложный выпад',
         'ambush':'Внезапный удар', 'dismantle':'Долой оружие', 'cheap_shot':'Подлый трюк',
         'kidney_shot':'Удар по почкам', 'blind':'Ослепление', 'sap':'Ошеломление',
         'fan_of_knives':'Веер клинков', 'preparation':'Подготовка'}


def localized(g, row, strings, name_ru, name_en, text_ru, text_en, rank_ru='Небожитель'):
    for locale, name, text, rank in ((8,name_ru,text_ru,rank_ru),(0,name_en,text_en,'Celestial')):
        for field, value in ((g.SPELL_NAME,name),(g.SPELL_RANK,rank),(g.SPELL_DESCRIPTION,text),(g.SPELL_TOOLTIP,text)):
            g.set_string(row, strings, field+locale, value)
            row[field+16] |= 0x101


def active(g, row, base, name, strings, manifest, russian):
    if name not in RU:
        return
    cfg=manifest['celestial_revision']
    if name == 'ambush': row[46]=cfg['ambush_range_id']
    if name == 'fan_of_knives': row[92]=cfg['radius_id']
    if name == 'feint': row[133]=base[133]
    # Client and server each carry both proper locales, not English technical fallback in ruRU.
    if russian:
        g.set_string(row,strings,g.SPELL_NAME+8,NAMES[name])
    for field in (g.SPELL_NAME,g.SPELL_RANK,g.SPELL_DESCRIPTION,g.SPELL_TOOLTIP):
        row[field+16] |= 0x101
    if not g.read_string(strings, row[g.SPELL_TOOLTIP+(8 if russian else 0)]):
        row[g.SPELL_TOOLTIP+(8 if russian else 0)]=row[g.SPELL_DESCRIPTION+(8 if russian else 0)]
    if name == 'evasion':
        dodge=base[80]+1
        text=f'Вероятность уклонения повышена на {dodge}%. Получаемый физический урон уменьшен на 15%.'
        g.set_string(row,strings,g.SPELL_TOOLTIP+(8 if russian else 0),text if russian else f'Dodge increased by {dodge}%. Physical damage taken reduced by 15%.')


def merge_locales(g, client, cs, server, ss, manifest):
    c={r[0]:r for r in client}; s={r[0]:r for r in server}
    ids=[a['celestial_first']+i for a in manifest['active_spells'] if a['logical_name'] in RU for i in range(len(a['base_spell_chain']))]
    for spell in ids:
        for field in (g.SPELL_NAME,g.SPELL_RANK,g.SPELL_DESCRIPTION,g.SPELL_TOOLTIP):
            g.set_string(c[spell],cs,field,g.read_string(ss,s[spell][field]))
            g.set_string(s[spell],ss,field+8,g.read_string(cs,c[spell][field+8]))


def technical(g, row, name, strings, manifest):
    cfg=manifest['celestial_revision']
    if row[0] in cfg['retired_auras']:
        for i in range(3): g.clear_effect(row,i)
        g.set_effect(row,0,4,0)
        row[4] |= 0x80
        row[40]=36
        localized(g,row,strings,'Устаревший служебный эффект','Retired internal effect','Не используется.','Not used.')
        return
    if name not in cfg['visible_auras']: return
    row[4] &= ~(0x80|0x40)
    row[9] &= ~(0x18000400)
    row[49]=1
    row[2]=0
    row[3]=0
    if name.startswith('celestial_damage_suppression_'):
        amount=int(name.rsplit('_',1)[1])
        # DUMMY deliberately: the centralized pre-packet damage modifier also covers old DoTs.
        # A native percent-done aura would snapshot some DoTs and double scale others.
        g.set_effect(row,0,4,-amount,6)
        row[46]=13
        row[4] |= 0x04000000  # negative aura, never a slow mechanic
        row[40]=32 if amount==20 else 35
        row[133]=cfg['icons']['suppression']
        localized(g,row,strings,'Ослабление Небожителя','Celestial Weakening',f'Наносимый урон уменьшен на {amount}%.',f'Damage dealt reduced by {amount}%.')
    elif name == 'celestial_sprint_immunity':
        for i,aura_type in enumerate((26,33)):  # root/slow, including spells without mechanic tags
            g.set_effect(row,i,38,1)  # SPELL_AURA_STATE_IMMUNITY
            row[110+i]=aura_type
        row[40]=35
        row[133]=cfg['icons']['sprint_freedom']
        localized(g,row,strings,'Свобода движения','Freedom of Movement','Невосприимчивость к эффектам замедления и обездвиживания.','Immune to slows and roots.')
    elif name == 'celestial_feint_guard':
        row[40]=31
        row[133]=cfg['icons']['feint']
        localized(g,row,strings,'Ложный выпад','Feint','Получаемый урон от атак по области уменьшен на 70%.','Area damage taken reduced by 70%.')
    elif name == 'celestial_sap_guard':
        row[4] |= 0x04000000
        row[40]=35
        row[133]=cfg['icons']['sap']
        localized(g,row,strings,'Последствия ошеломления','Sap Aftereffect','Скорость передвижения снижена на 70%.','Movement speed reduced by 70%.')


def auxiliary(g, manifest, baseline, outputs):
    cfg=manifest['celestial_revision']
    results={}
    for name,fields,template_id,key in (('SpellRadius',4,14,'radius_id'),('SpellRange',40,2,'ambush_range_id')):
        rows,strings=g.load_dbc(baseline / (name+'.dbc'),fields)
        by_id={r[0]:r for r in rows}
        assert cfg[key] not in by_id, f'{name} ID collision'
        row=list(by_id[template_id]); row[0]=cfg[key]
        if name=='SpellRadius':
            row[1]=row[3]=struct.unpack('<I',struct.pack('<f',12.0))[0]
            row[2]=0
        else:
            for i in (3,4):
                row[i]=struct.unpack('<I',struct.pack('<f',8.0))[0]
            # A custom 8-yard range is not a melee-only range. Keeping the
            # stock melee flag makes client/server validation collapse back to
            # melee semantics despite the larger numeric maximum.
            row[5]=0
        rows.append(row)
        for output in outputs: g.write_dbc(output/(name+'.dbc'),sorted(rows),strings)
        results[name]={'baseline_sha256':g.sha256(baseline/(name+'.dbc')),'id':row[0],'row':row}
    return results
