"""Package approved, unchanged PNG icons; no drawing or global stock replacement."""
import ctypes
import json
from pathlib import Path
import generate_rogue_paths as dbc

ROOT = Path(r'C:\Solo WotLK')
MODULE = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work/mobility-retirement-v1'


def main():
    manifest = json.loads((MODULE / 'data/cultivation_rogue_spell_manifest.json').read_text(encoding='utf-8'))
    catalog = {}
    for name in manifest['path_icons']['asset_catalogs']:
        approved = ROOT / 'artifacts/rogue_pw_icons' / name
        source_manifest = json.loads((approved / 'reports/generation_manifest.json').read_text(encoding='utf-8'))
        qa = json.loads((approved / 'reports/qa_report.json').read_text(encoding='utf-8'))
        for record in source_manifest['files']:
            source = ROOT / record['output']
            key = (source.stem, record['profile'])
            if key in catalog:
                raise ValueError('Duplicate icon source: ' + str(key))
            catalog[key] = (source, record['sha256'].lower(), qa[source.stem][record['profile']])
    baseline = ROOT / 'work/rogue-pw-icons-audit-20260830/extract/28-ruRU-patch-ruRU-Z/DBFilesClient/SpellIcon.dbc'
    rows, strings = dbc.load_dbc(baseline, 2)
    ids = {r[0] for r in rows}
    dll = ctypes.CDLL(str(ROOT / 'work/research/BlpConverter/BlpConverter/rust_blp_converter.dll'))
    encode = dll.image_to_blp
    encode.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int)
    encode.restype = ctypes.c_int
    info = dll.blp_get_info
    info.argtypes = (ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32))
    info.restype = ctypes.c_int
    result = []
    icon_jobs = []
    for ability in manifest['active_spells'] + manifest['passive_spells']:
        if 'custom_icon_ids' not in ability:
            continue
        slug = ability['logical_name']
        for path, profile in (('celestial', 'sage'), ('sha', 'demon')):
            icon_jobs.append((slug, path, profile, dbc.path_icon_id(manifest, slug, path)))
    for display in manifest['display_passives']:
        if display['logical_name'] != 'stealth_mastery':
            continue
        path = display['path']
        icon_jobs.append((display['logical_name'], path, 'sage' if path == 'celestial' else 'demon', display['icon_id']))
    for slug, path, profile, icon_id in icon_jobs:
            source, expected, qa = catalog[(slug, profile)]
            if dbc.sha256(source) != expected:
                raise ValueError(f'Approved PNG changed: {source}')
            if qa['content_lock']['status'] != 'CONTENT_LOCK_PASS' or qa['filter_only']['status'] != 'FILTER_ONLY_PASS':
                raise ValueError(f'Content lock failed: {slug}/{profile}')
            if icon_id in ids:
                raise ValueError(f'SpellIcon collision: {icon_id}')
            ids.add(icon_id)
            virtual = (f'Interface\\Icons\\ability_rogue_surpriseattack2_{path}'
                       if slug == 'stealth_mastery' else
                       f'Interface\\Icons\\JC_RoguePaths\\{path}_{slug}')
            dest = WORK / 'icon-staging' / Path(*virtual.split('\\')).with_suffix('.blp')
            dest.parent.mkdir(parents=True, exist_ok=True)
            rc = encode(str(source).encode(), str(dest).encode(), 3, 0)
            width, height, mips = ctypes.c_uint32(), ctypes.c_uint32(), ctypes.c_uint32()
            rc2 = info(str(dest).encode(), ctypes.byref(width), ctypes.byref(height), ctypes.byref(mips))
            if rc or rc2 or (width.value, height.value, mips.value) != (64, 64, 7):
                raise ValueError(f'BLP validation failed: {source}')
            rows.append([icon_id, dbc.add_string(strings, virtual)])
            result.append(dict(logical_name=slug, path=path, icon_id=icon_id, virtual_path=virtual+'.blp',
                               png=str(source), png_sha256=dbc.sha256(source), blp=str(dest), blp_sha256=dbc.sha256(dest),
                               dimensions=[64,64], mip_levels=7))
    for item in manifest['path_icons'].get('shared_icons', []):
        source = ROOT / item['source_png']
        if dbc.sha256(source) != item['source_png_sha256']:
            raise ValueError(f'User-supplied shared PNG changed: {source}')
        icon_id = item['icon_id']
        if icon_id in ids:
            raise ValueError(f'SpellIcon collision: {icon_id}')
        ids.add(icon_id)
        virtual = item['virtual_path']
        dest = WORK / 'icon-staging' / Path(*virtual.split('\\')).with_suffix('.blp')
        dest.parent.mkdir(parents=True, exist_ok=True)
        rc = encode(str(source).encode(), str(dest).encode(), 3, 0)
        width, height, mips = ctypes.c_uint32(), ctypes.c_uint32(), ctypes.c_uint32()
        rc2 = info(str(dest).encode(), ctypes.byref(width), ctypes.byref(height), ctypes.byref(mips))
        if rc or rc2 or (width.value, height.value, mips.value) != (64, 64, 7):
            raise ValueError(f'BLP validation failed: {source}')
        rows.append([icon_id, dbc.add_string(strings, virtual)])
        result.append(dict(logical_name=item['logical_name'], path='shared', icon_id=icon_id,
                           virtual_path=virtual+'.blp', png=str(source), png_sha256=dbc.sha256(source),
                           blp=str(dest), blp_sha256=dbc.sha256(dest), dimensions=[64,64], mip_levels=7))
    expected_count = manifest['path_icons']['count'] + len(manifest['path_icons'].get('shared_icons', []))
    if len(result) != expected_count:
        raise ValueError('Texture count differs from central manifest')
    import path_status
    path_status.icons(dbc, rows, strings)
    for item in path_status.spec()['statuses']:
        source=MODULE/item['source_png']
        if dbc.sha256(source)!=item['source_sha256']: raise ValueError('Status PNG hash mismatch')
        dest=WORK/'icon-staging'/Path(*item['virtual_path'].split('\\')).with_suffix('.blp')
        dest.parent.mkdir(parents=True,exist_ok=True)
        if encode(str(source).encode(),str(dest).encode(),3,0): raise ValueError('Status BLP conversion failed')
        result.append(dict(logical_name=item['path']+'_path_status',icon_id=item['icon_id'],virtual_path=item['virtual_path']+'.blp',png=str(source),png_sha256=dbc.sha256(source),blp=str(dest),blp_sha256=dbc.sha256(dest)))
    for dest in (MODULE / 'client_patch/staging/DBFilesClient/SpellIcon.dbc', MODULE / 'generated/server/dbc/SpellIcon.dbc'):
        dbc.write_dbc(dest, sorted(rows), strings)
    (WORK / 'icons-manifest.json').write_text(json.dumps(dict(status='passed', source='approved +2px unchanged', files=result), indent=2)+'\n', encoding='utf-8')
    print(f'PASS {len(result)} content-locked/shared BLP icons, unique SpellIcon IDs, 7 mip-levels; stock mappings unchanged')


if __name__ == '__main__':
    main()
