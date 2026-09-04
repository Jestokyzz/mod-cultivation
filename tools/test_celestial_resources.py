"""Source/generator regression; native runtime acceptance remains separate."""
import json
from pathlib import Path
import generate_rogue_paths as g

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / 'data/cultivation_rogue_spell_manifest.json').read_text(encoding='utf-8'))
rows, strings = g.load_dbc(Path(r'C:\Solo WotLK\work\mobility-retirement-v1\clean-dbc\server\Spell.dbc'), 234)
stock = {row[0]: row for row in rows}
premed = list(stock[14183])
g.patch_active_fields(premed, 'premeditation', 'celestial')
assert premed[40] == 9, 'Premeditation must use native 30-second duration, not stock 20'
assert premed[80] == premed[81] == 2, 'Both grant and retention must be 3 combo points'
assert premed[96] == 148, 'Native retention owns expiry'
source = (ROOT / 'src/rogue/RoguePathCommonSpells.cpp').read_text(encoding='utf-8')
cost = source.split('void ModifyPowerCost(', 1)[1].split('void ModifyCritChance(', 1)[0]
assert 'Celestial && snapshot.deadlyPoisonStacks == 5' not in cost, 'No pre-cast Mutilate discount'
assert 'mutilateRefunded' in source, 'One refund per parent, not one per weapon'
assert 'snapshot.mutilateRefunded = true' in source
assert 'snapshot.deadlyPoisonStacks == 5' in source
entry = next(x for x in manifest['active_spells'] if x['logical_name'] == 'mutilate')
assert 'возвращает 10' in entry['descriptions']['ruRU']['celestial']
print('PASS Celestial resource source/generator invariants (not runtime acceptance)')
