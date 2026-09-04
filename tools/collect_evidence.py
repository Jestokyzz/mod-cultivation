"""Export only module-owned core changes and collect local, non-GUI evidence."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SERVER = Path(r'C:\Solo WotLK\test-server\20260831-rogue-paths-v1')
BASELINE = Path(r'F:\JestokyCraft Backups\rogue-paths\baseline-20260830T072500\manifest.json')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


changes, patch = [], []
for entry in json.loads(BASELINE.read_text(encoding='utf-8-sig')):
    source, backup = Path(entry['Source']), Path(entry['Backup'])
    if not source.is_relative_to(REPO / 'src'):
        continue
    assert digest(backup).lower() == entry['SHA256'].lower(), f'Baseline checksum mismatch: {backup.name}'
    if digest(source) == digest(backup):
        continue
    relative = source.relative_to(REPO).as_posix()
    patch.extend(difflib.unified_diff(backup.read_text(encoding='utf-8-sig').splitlines(keepends=True),
                                    source.read_text(encoding='utf-8-sig').splitlines(keepends=True),
                                    fromfile='a/' + relative, tofile='b/' + relative))
    changes.append({'file': relative, 'baseline_sha256': digest(backup), 'candidate_sha256': digest(source)})
patch_path = ROOT / 'core-patches/rogue-paths.patch'
patch_path.parent.mkdir(exist_ok=True)
patch_path.write_text(''.join(patch), encoding='utf-8', newline='\n')
check = subprocess.run(['git', '-c', f'safe.directory={REPO.as_posix()}', 'apply', '--reverse', '--check', str(patch_path)],
                       cwd=REPO, capture_output=True, text=True)
assert check.returncode == 0, check.stderr
offline = subprocess.run([sys.executable, str(ROOT / 'tools/test_generated_data.py')], capture_output=True, text=True)
assert offline.returncode == 0, offline.stdout + offline.stderr
compiled = REPO.parent / 'build-solitary-v4-ninja/bin/worldserver.exe'
installed = SERVER / 'worldserver.exe'
assert digest(compiled) == digest(installed), 'Installed binary differs from successful build'
mpq = json.loads((ROOT / 'client_patch/build/manifest.json').read_text(encoding='utf-8-sig'))
assert digest(Path(mpq['Baseline'])).lower() == mpq['BaselineSHA256'].lower(), 'Production baseline MPQ changed'
assert digest(ROOT / 'client_patch/build/patch-ruRU-Z.MPQ').lower() == mpq['OutputSHA256'].lower()
generation = json.loads((ROOT / 'generated/generation_report.json').read_text(encoding='utf-8'))
reports = {}
for name in ('world_protocol_test', 'talent_protocol_test', 'restart_protocol_test'):
    reports[name] = json.loads((ROOT / 'generated' / (name + '.json')).read_text(encoding='utf-8'))
    assert reports[name]['status'] == 'passed', name
stdout = (SERVER / 'logs/world-stdout.log').read_text(encoding='utf-8', errors='replace')
assert 'mod-cultivation: startup validation passed' in stdout
files = {}
for folder in ('src', 'tools', 'data', 'conf', 'core-patches'):
    for item in (ROOT / folder).rglob('*'):
        if item.is_file() and '__pycache__' not in item.parts:
            files[item.relative_to(ROOT).as_posix()] = digest(item)
report = {
    'status': 'candidate-unaccepted', 'version': '1.0.0',
    'created_utc': datetime.now(timezone.utc).isoformat(),
    'build': {'result': 'compiled-and-linked', 'installed_sha256': digest(installed),
              'target': 'worldserver / RelWithDebInfo / Ninja / MSVC', 'production_binary_replaced': False},
    'offline_tests': {'status': 'passed', 'output': offline.stdout + offline.stderr},
    'runtime_protocol': reports,
    'startup_module_validation': 'passed',
    'client_gui_acceptance': 'not-performed; user login/application approval required',
    'combat_pvp_poison_tick_acceptance': 'not-performed',
    'real_talent_learning_reset_and_combat_tree': 'not-performed; current test uses isolated talent fixtures',
    'sql_rollback_execution': 'not-performed',
    'playerbots': {'target': 200, 'autologin': True, 'class_spell_ai_acceptance': 'not-performed'},
    'core_changes': changes, 'core_patch_reverse_check': 'passed',
    'generation': generation, 'mpq': mpq, 'source_sha256': files,
}
(ROOT / 'generated/validation_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'PASS: {len(changes)} scoped core diffs, patch reverse-check, 12 offline tests, matching installed binary, protocol reports')
print('NOT accepted: GUI/combat/talent learning/rollback execution remain unverified')
