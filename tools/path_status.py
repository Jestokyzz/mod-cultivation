"""Presentation-only allegiance records. The persistent path remains server-owned."""
import json
from pathlib import Path
MODULE=Path(__file__).resolve().parents[1]
def spec():
    return json.loads((MODULE/'data/path_status.json').read_text(encoding='utf-8'))
def patch(g,rows,strings):
    data=spec();by_id={r[0]:r for r in rows};base=by_id[data['baseline_spell']]
    for item in data['statuses']:
        if item['spell_id'] in by_id: raise ValueError('Path status ID collision')
        row=list(base);row[0]=item['spell_id']
        row[4]=(row[4]&~0xC0)|0xA5800000 # negative, no cancel, dead/mounted, bypass immunity
        row[5]|=0x400 # no threat
        row[7]|=0x00100000 # native SPELL_ATTR3_ALLOW_AURA_WHILE_DEAD
        row[2]=0;row[3]=0 # no dispel type or mechanic
        row[28:31]=[0,0,0] # no damage/CC aura interrupts
        row[34:37]=[0,0,0] # no proc producer or charges
        row[40]=21 # validated indefinite duration
        row[133]=row[134]=item['icon_id']
        for i in range(3):g.clear_effect(row,i)
        g.set_effect(row,0,4,0) # inert SPELL_AURA_DUMMY; no additional bonus
        for locale,suffix in ((0,'en'),(8,'ru')):
            for field,value in ((136,item['name_'+suffix]),(153,''),(170,item['text_'+suffix]),(187,item['text_'+suffix])):
                g.set_string(row,strings,field+locale,value);row[field+16]|=0x101
        rows.append(row)
def icons(g,rows,strings):
    ids={r[0] for r in rows}
    for item in spec()['statuses']:
        if item['icon_id'] in ids: raise ValueError('Path status icon collision')
        rows.append([item['icon_id'],g.add_string(strings,item['virtual_path'])])
