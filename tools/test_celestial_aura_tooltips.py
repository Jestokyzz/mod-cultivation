"""Independent acceptance gates for native buff descriptions and DBC scope."""
import json
import re
from pathlib import Path
import generate_rogue_paths as g

ROOT = Path(__file__).resolve().parents[1]
m = json.loads((ROOT / 'data/cultivation_rogue_spell_manifest.json').read_text(encoding='utf-8'))
rows, strings = g.load_dbc(ROOT / 'client_patch/staging/DBFilesClient/Spell.dbc', 234)
spells = {r[0]: r for r in rows}
entries = {x['logical_name']: x for x in m['active_spells']}

def text(name, field=195):
    return g.read_string(strings, spells[entries[name]['celestial_first']][field])

assert text('kidney_shot') == '|cffFFD200Оглушение.|r'
assert text('cheap_shot') == '|cffFFD200Оглушение.|r'
assert 'следующих двух' in text('cold_blood') and 'следующей атакующей' not in text('cold_blood')
assert 'завершающий' not in g.read_string(strings, spells[m['technical_spells']['celestial_cold_blood_window']][195])
for name in ('celestial_cold_blood_window', 'celestial_ghostly_strike_tracker', 'celestial_tricks_boost'):
    actual = g.read_string(strings, spells[m['technical_spells'][name]][195])
    assert actual.startswith('|cffFFD200') and '|cff7CEBFF' in actual, name
assert '70%' in text('feint') and '$48659' not in text('feint')
assert '$31224s1' not in text('cloak_of_shadows')
assert f"${entries['cloak_of_shadows']['celestial_first']}s1" in text('cloak_of_shadows')
assert '4 дополнительных' in text('blade_flurry') and 'дополнительному ближайшему' not in text('blade_flurry')
assert 'Вероятность уклонения' in text('ghostly_strike') and 'урона оружия' not in text('ghostly_strike')
assert '3' in text('premeditation') and '30' in text('premeditation')
assert 'возвращает 10' in text('mutilate', 178) and 'стоимость применения уменьшается' not in text('mutilate', 178)

checked = 0
for entry in m['active_spells']:
    for rank in range(len(entry['base_spell_chain'])):
        row = spells[entry['celestial_first'] + rank]
        for locale in (0, 8):
            aura = g.read_string(strings, row[187 + locale])
            assert '{rank}' not in aura and '{path}' not in aura
            assert aura.count('|cff') == aura.count('|r')
            assert not re.search(r'%(?:s|d|f|u)\b', aura)
            # Native buffs can have dynamic fields, but never an entire finisher table.
            assert '\n1 ' not in aura and '\n5 ' not in aura
            checked += 1

# No gameplay changes outside Celestial Premeditation in this DBC candidate.
old_rows, old_strings = g.load_dbc(Path(r'F:\JestokyCraft Backups\rogue-paths\pre-change-celestial-resources-candidate36-20260903T093813\test-server\20260831-rogue-paths-v3\data\dbc\Spell.dbc'), 234)
server_rows, server_strings = g.load_dbc(ROOT / 'generated/server/dbc/Spell.dbc', 234)
new = {r[0]: r for r in server_rows}
string_fields = {i for start in (136, 153, 170, 187) for i in range(start, start+16)}
changes = []
for old in old_rows:
    actual = new[old[0]]
    changed = [i for i in range(234) if i not in string_fields and old[i] != actual[i]]
    if changed: changes.append((old[0], changed))
    sha = any(e['sha_first'] <= old[0] < e['sha_first'] + len(e['base_spell_chain']) for e in m['active_spells']+m['passive_spells'])
    if sha:
        # Candidate38 explicitly changes Sha descriptions, not names/ranks or mechanics.
        for index in string_fields - set(range(170, 186)) - set(range(187, 203)):
            assert g.read_string(old_strings, old[index]) == g.read_string(server_strings, actual[index]), ('Sha changed', old[0], index)
assert changes == [(86108, [40, 81])], changes
print(f'PASS {checked} buff-locales, current values, no cast-tooltip leakage, Sha names/ranks unchanged, only Premeditation numeric DBC change')
