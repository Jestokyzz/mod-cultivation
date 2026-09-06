"""Read-only audit: textured batches must reference a real opacity track."""
import json
import struct
import sys
from pathlib import Path

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / 'candidate-v2'
results = []
for path in sorted(root.rglob('*.m2')):
    data = path.read_bytes()
    skin = path.with_name(path.stem + '00.skin').read_bytes()
    weights, _ = struct.unpack_from('<II', data, 88)
    combos, offset = struct.unpack_from('<II', data, 144)
    count, batches = struct.unpack_from('<II', skin, 36)
    issues = []
    for index in range(count):
        batch = batches + index * 24
        textures = struct.unpack_from('<H', skin, batch + 14)[0]
        lookup = struct.unpack_from('<H', skin, batch + 20)[0]
        if not textures:
            continue
        if lookup >= combos:
            issues.append({'batch': index, 'invalid_combo': lookup})
            continue
        track = struct.unpack_from('<H', data, offset + lookup * 2)[0]
        if track >= weights:
            issues.append({'batch': index, 'invalid_weight_track': track})
    results.append({'model': path.name, 'weight_tracks': weights, 'batches': count, 'issues': issues})
print(json.dumps(results, indent=2))
sys.exit(any(result['issues'] for result in results))
