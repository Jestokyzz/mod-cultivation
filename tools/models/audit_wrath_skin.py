"""Read-only compatibility checks omitted by the original structural validator."""
import json
import struct
import sys
from pathlib import Path

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / 'candidate-v2'
issues = []
for path in sorted(root.rglob('*.skin')):
    data = path.read_bytes()
    assert data[:4] == b'SKIN', path
    count, offset = struct.unpack_from('<II', data, 28)
    assert offset + count * 48 <= len(data), path
    profile = struct.unpack_from('<I', data, 44)[0]
    if profile not in (21, 53, 64, 256):
        issues.append(dict(file=str(path.relative_to(root)), field='bone_count_max', value=profile))
    for index in range(count):
        section = offset + index * 48
        bones = struct.unpack_from('<H', data, section + 12)[0]
        influences = struct.unpack_from('<H', data, section + 16)[0]
        if not 1 <= influences <= 4:
            issues.append(dict(file=str(path.relative_to(root)), section=index,
                               field='bone_influences', value=influences))
        if not 1 <= bones <= profile:
            issues.append(dict(file=str(path.relative_to(root)), section=index,
                               field='bone_count', value=bones))
print(json.dumps({'status': 'FAIL' if issues else 'PASS', 'issues': issues}, indent=2))
sys.exit(bool(issues))
