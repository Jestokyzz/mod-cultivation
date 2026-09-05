"""Repair proven foreign-string offsets, then reject any dangling Spell string."""
import hashlib
import struct

STRING_FIELDS = set(range(136, 152)) | set(range(153, 169)) | set(range(170, 186)) | set(range(187, 203))
# Provenance: work/pvp-ports/vendor/mod-bg-twinpeaks/client-side/DBFilesClient/Spell.dbc
# SHA256 b74d687235a0578bde525c75a3d2b82ae1bbd0f459cc868f0483d01019c744df.
# All non-string fields of each donor record match both clean mobility baselines.
# Names/ranks were correctly rebound; description/aura offsets were copied raw.
RECOVERY = {
    85000: ('0028d26fb7c86217d51d62e3e5b62999ceef86df4f093cf966b1764483467966',
            (15296071, 'Roots the target!'), (126944, 'Rooted.')),
    85001: ('1e5f2c26cbe3507f03e0a712a5145872e23ed1bf3720d69bd855654d9d368ec0',
            (15296099, 'Increases youf damage by 5%'), (1260965, 'Damage increased by $s1%.')),
    85002: ('f4f9def5243dee673a3cd8ec488c0c5136d59d535c8eca5dd72ca6b7f30e2c5c',
            (15296156, 'Increases the targets Stamina by $s1%.'), (15296195, 'Stamina increased by $s1%.')),
}


def repair(g, rows, strings):
    changed = []
    for row in rows:
        if row[0] not in RECOVERY:
            continue
        fingerprint, description, aura = RECOVERY[row[0]]
        values = [value for field, value in enumerate(row) if field not in STRING_FIELDS]
        if hashlib.sha256(struct.pack('<%dI' % len(values), *values)).hexdigest() != fingerprint:
            raise ValueError(f'Foreign record {row[0]} differs from proven donor; refuse recovery')
        for start, (old_offset, expected) in ((170, description), (187, aura)):
            for locale in (0, 1, 2, 3, 6, 7, 8):
                field = start + locale
                offset = row[field]
                if offset < len(strings) and g.read_string(strings, offset) == expected:
                    continue  # Idempotent on already repaired input.
                if offset != old_offset:
                    raise ValueError(f'Unexpected foreign string {row[0]}/{field}: {offset}')
                g.set_string(row, strings, field, expected)
                changed.append((row[0], field))
    return changed


def validate(rows, strings):
    for row in rows:
        for field in STRING_FIELDS:
            offset = row[field]
            if offset >= len(strings) or strings.find(b'\0', offset) < 0:
                raise ValueError(f'Dangling Spell.dbc string: {row[0]}/{field}={offset}')
