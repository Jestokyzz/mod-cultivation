"""Generate presentation-only talent metadata from final numeric Spell records."""
import json

START = '-- BEGIN GENERATED TALENT METADATA'
END = '-- END GENERATED TALENT METADATA'


def metadata(manifest, rows):
    spells = {r[0]: r for r in rows}
    abilities = {a['logical_name']: a for a in manifest['active_spells'] + manifest['passive_spells']}
    result = {}
    tabs = {tab: i + 1 for i, tab in enumerate(manifest['talent_ui']['tab_order'])}
    for mapping in manifest['talent_ui']['mappings']:
        ability = abilities[mapping['logical_name']]
        position = f"{tabs[mapping['tab_id']]}:{mapping['tier'] + 1}:{mapping['column'] + 1}"
        paths = {}
        for path in ('celestial', 'sha'):
            ranks = []
            for stock in mapping['rank_spells']:
                rank = ability['base_spell_chain'].index(stock)
                row = spells[ability[path + '_first'] + rank]
                ranks.append(dict(cost=row[42], cooldown=max(row[29:31]), passive=bool(row[4] & 0x40),
                                  costChanged=row[42] != spells[stock][42],
                                  cooldownChanged=max(row[29:31]) != max(spells[stock][29:31]),
                                  preparation=path == 'celestial' and ability['logical_name'] in
                                  ('cold_blood', 'shadowstep', 'vanish', 'evasion', 'sprint')))
            paths[path] = ranks
        result[position] = paths
    return result


def write(header, manifest, rows):
    data = metadata(manifest, rows)
    lines = [START, 'local talentMetadata = {']
    for position, paths in data.items():
        lines.append('    [' + json.dumps(position) + '] = {')
        for path, ranks in paths.items():
            values = []
            for rank in ranks:
                values.append('{ ' + ', '.join(f'{k} = {str(v).lower()}' for k, v in rank.items()) + ' }')
            lines.append('        ' + path + ' = { ' + ', '.join(values) + ' },')
        lines.append('    },')
    lines += ['}', END]
    source = header.read_text(encoding='utf8')
    if source.count(START) != 1 or source.count(END) != 1:
        raise ValueError('Native header metadata insertion point is not unique')
    begin, tail = source.split(START)
    _, end = tail.split(END)
    header.write_text(begin + '\n'.join(lines) + end, encoding='utf8')
    return data
