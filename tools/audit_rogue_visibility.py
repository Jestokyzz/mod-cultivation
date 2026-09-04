"""Read-only client/MPQ audit; writes evidence only, never installs artifacts."""
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import generate_rogue_paths as g

ROOT = Path(__file__).resolve().parents[1]
CLIENT = Path(r'C:\Solo WotLK\test-client\20260831-rogue-paths-v3')
MPQ = Path(r'C:\Solo WotLK\work\wow-patch-interface\mpqcli.exe')
OUTPUT = ROOT / 'generated/schema3-audit'


def read(archive, virtual):
    result = subprocess.run([str(MPQ), 'read', virtual, str(archive)], capture_output=True)
    return result.stdout if result.returncode == 0 else None


def dbc(data, fields):
    magic, count, actual, size, strings_size = struct.unpack_from('<4s4I', data)
    assert magic == b'WDBC' and actual == fields and size == fields * 4
    end = 20 + count * size
    assert len(data) == end + strings_size
    return {row[0]: list(row) for row in struct.iter_unpack('<' + 'I' * fields, data[20:end])}, bytearray(data[end:])


def stock(virtual):
    for name in ('patch-ruRU-3.MPQ', 'patch-ruRU-2.MPQ', 'patch-ruRU.MPQ', 'locale-ruRU.MPQ'):
        archive = CLIENT / 'Data/ruRU' / name
        data = read(archive, virtual)
        if data:
            return archive, data
    raise RuntimeError('Official resource missing: ' + virtual)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / 'data/cultivation_rogue_spell_manifest.json').read_text(encoding='utf-8'))
    spell_source, spell_data = stock('DBFilesClient\\Spell.dbc')
    icon_source, icon_data = stock('DBFilesClient\\SpellIcon.dbc')
    base, base_strings = dbc(spell_data, 234)
    stock_icons, icon_strings = dbc(icon_data, 2)
    owner = CLIENT / 'Data/ruRU/patch-ruRU-Z.MPQ'
    current, strings = dbc(read(owner, 'DBFilesClient\\Spell.dbc'), 234)
    current_icons, current_icon_strings = dbc(read(owner, 'DBFilesClient\\SpellIcon.dbc'), 2)
    sla, _ = dbc(read(owner, 'DBFilesClient\\SkillLineAbility.dbc'), 14)
    report = {'status': 'audit-not-acceptance', 'client': str(CLIENT),
              'stock_spell': str(spell_source), 'stock_spell_sha256': hashlib.sha256(spell_data).hexdigest(),
              'stock_icons': str(icon_source), 'stock_icons_sha256': hashlib.sha256(icon_data).hexdigest(),
              'records': [], 'ui_owners': {}, 'token_examples': {}, 'icon_resources': {}}
    (OUTPUT / 'stock-Spell.dbc').write_bytes(spell_data)
    (OUTPUT / 'stock-SpellIcon.dbc').write_bytes(icon_data)
    talent_source, talent_data = stock('DBFilesClient\\Talent.dbc')
    (OUTPUT / 'stock-Talent.dbc').write_bytes(talent_data)
    report['stock_talent'] = {'source': str(talent_source), 'sha256': hashlib.sha256(talent_data).hexdigest()}
    for ability in manifest['active_spells'] + manifest['passive_spells']:
        for index, base_id in enumerate(ability['base_spell_chain']):
            row = base[base_id]
            icon_path = g.read_string(icon_strings, stock_icons[row[133]][1])
            virtual = icon_path + ('' if icon_path.lower().endswith('.blp') else '.blp')
            if virtual not in report['icon_resources']:
                found = None
                for archive in sorted((CLIENT / 'Data').rglob('*.MPQ'), reverse=True):
                    if archive.name.lower() not in ('common.mpq','common-2.mpq','expansion.mpq','lichking.mpq','patch.mpq','patch-2.mpq','patch-3.mpq','locale-ruru.mpq','expansion-locale-ruru.mpq','lichking-locale-ruru.mpq','patch-ruru.mpq','patch-ruru-2.mpq','patch-ruru-3.mpq'):
                        continue
                    data = read(archive, virtual)
                    if data:
                        assert data[:4] in (b'BLP1', b'BLP2')
                        found = {'archive': str(archive), 'sha256': hashlib.sha256(data).hexdigest()}
                        break
                report['icon_resources'][virtual] = found
            for path in ('celestial', 'sha'):
                spell_id = ability[path + '_first'] + index
                variant = current[spell_id]
                actual_path = g.read_string(current_icon_strings, current_icons[variant[133]][1]) if variant[133] in current_icons else None
                text = g.read_string(base_strings, row[178])
                for token in re.findall(r'\$[^\s.,;:()%!\[\]]+', text):
                    report['token_examples'].setdefault(token, text)
                report['records'].append({'logical_name': ability['logical_name'], 'path': path, 'base': base_id, 'variant': spell_id,
                    'base_icon': row[133], 'variant_icon': variant[133], 'base_active_icon': row[134], 'variant_active_icon': variant[134],
                    'base_icon_path': icon_path, 'variant_icon_path': actual_path, 'stock_blp_exists': bool(report['icon_resources'][virtual]),
                    'skill_line_ability': [s for s in sla.values() if s[2] == spell_id],
                    'attributes': variant[4:12], 'base_attributes': row[4:12],
                    'base_name': g.read_string(base_strings, row[144]), 'name': g.read_string(strings, variant[144]),
                    'base_description': text, 'description': g.read_string(strings, variant[178]),
                    'base_effects': row[71:116], 'variant_effects': variant[71:116],
                    'visual_test': 'not-run'})
    for virtual in ('Interface\\FrameXML\\FrameXML.toc','Interface\\FrameXML\\GameTooltip.lua',
                    'Interface\\FrameXML\\TalentFrameBase.lua','Interface\\AddOns\\Blizzard_TalentUI\\Blizzard_TalentUI.lua'):
        owners = []
        for archive in sorted((CLIENT / 'Data').rglob('*.MPQ')):
            if not re.match(r'patch(?:-ruru)?-[a-z]\.mpq$', archive.name, re.I):
                continue
            data = read(archive, virtual)
            if data:
                relative = archive.name + '/' + virtual.replace('\\', '/')
                destination = OUTPUT / 'ui' / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                owners.append({'archive': str(archive), 'sha256': hashlib.sha256(data).hexdigest(), 'extracted': str(destination)})
        report['ui_owners'][virtual] = owners
    (OUTPUT / 'visibility-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    seven = {'cheap_shot','backstab','blind','safe_fall','sap','ghostly_strike','shiv'}
    print(json.dumps({'seven_sample': [r for r in report['records'] if r['logical_name'] in seven and r['path'] == 'celestial'][:3],
                      'ui_owners': report['ui_owners'], 'record_count': len(report['records']),
                      'missing_stock_resources': [p for p, v in report['icon_resources'].items() if not v]}, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
