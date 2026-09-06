"""Regression: mutable nested track descriptors cannot have two owners."""
import json, struct, sys
from pathlib import Path

def audit(path):
    b = path.read_bytes()
    n, o = struct.unpack_from('<II', b, 72)
    owners = {}
    issues = []
    for i in range(n):
        for component in (0, 20):
            for kind in (4, 12):
                count, offset = struct.unpack_from('<II', b, o+i*40+component+kind)
                assert offset+count*8 <= len(b)
                for j in range(count):
                    slot = offset+j*8
                    label = f'color[{i}].track[{component}].array[{kind}][{j}]'
                    if slot in owners:
                        issues.append({'descriptor':slot, 'first':owners[slot], 'second':label})
                    owners[slot] = label
    return {'path':str(path), 'issues':issues}

if __name__ == '__main__':
    results = [audit(p) for p in sorted(Path(sys.argv[1]).rglob('*.m2'))]
    print(json.dumps(results, indent=2))
    sys.exit(any(r['issues'] for r in results))
