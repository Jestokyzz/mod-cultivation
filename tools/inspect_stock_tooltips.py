"""Small read-only schema report for the tooltip migration."""
import json
from pathlib import Path
import re
import generate_rogue_paths as g
import audit_rogue_visibility as audit

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'data/cultivation_rogue_spell_manifest.json').read_text(encoding='utf-8'))
rows, strings = g.load_dbc(root / 'generated/schema3-audit/stock-Spell.dbc', 234)
vr, vs = g.load_dbc(root / 'generated/schema3-audit/stock-SpellDescriptionVariables.dbc', 2)
ids = {i for a in manifest['active_spells'] + manifest['passive_spells'] for i in a['base_spell_chain']}
tokens = set()
variables = set()
for row in rows:
    if row[0] not in ids:
        continue
    variables.add(row[232])
    for field in (170, 178, 187, 195):
        tokens.update(re.findall(r'\$(?:\d+)?[a-zA-Z]+\d*', g.read_string(strings, row[field])))
print('TOKENS', sorted(tokens))
print('VARIABLES', [(r[0], g.read_string(vs, r[1])) for r in vr if r[0] in variables])
for table in ('SpellDuration', 'TalentTab'):
    source, data = audit.stock('DBFilesClient\\' + table + '.dbc')
    destination = audit.OUTPUT / ('stock-' + table + '.dbc')
    destination.write_bytes(data)
    print('INPUT', table, g.sha256(destination))
for name in ('patch-3.MPQ', 'patch-2.MPQ', 'patch.MPQ'):
    data = audit.read(audit.CLIENT / 'Data' / name, 'DBFilesClient\\Spell.dbc')
    if data:
        rr, ss = audit.dbc(data, 234)
        print('GLOBAL', name, repr(g.read_string(ss, rr[51701][170])))
