"""Record reproducible source/data/Lua results, never mark game acceptance."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
NAMES = ['test_audit_fixes', 'test_generated_data', 'test_shadowstep_contract',
         'test_sha_candidate41', 'test_celestial_resources', 'test_sha_presentation',
         'test_cultivation_architecture', 'test_tooltip_presentation', 'test_tooltip_stock_values',
         'test_visibility_schema3', 'test_native_header']


def main():
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromNames(NAMES).run(result)
    report = {'tests': result.testsRun, 'passed': result.wasSuccessful(),
              'failures': [{'test': str(t), 'trace': trace} for t, trace in result.failures + result.errors],
              'suite': NAMES, 'scope': 'Python source/data + mocked Lua 5.1; NOT native/GUI acceptance'}
    destination = ROOT / 'generated/audit-static-tests.json'
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf8')
    state_path = ROOT / 'audit-fixes-manifest.json'
    state = json.loads(state_path.read_text('utf8'))
    state['status'] = 'static-tested-build-pending-unaccepted' if result.wasSuccessful() else 'static-failed-unaccepted'
    state['test_report'] = 'generated/audit-static-tests.json'
    state.setdefault('native_acceptance', 'pending')
    state['gui_acceptance'] = 'pending'
    state['installable_package'] = False
    artifacts = ['client_patch/staging/DBFilesClient/Spell.dbc', 'generated/server/dbc/Spell.dbc',
                 'client_patch/framexml/CultivationRogueHeader.lua', 'generated/generation_report.json',
                 'generated/audit-static-tests.json']
    state['artifacts'] = {name: {'sha256': hashlib.sha256((ROOT / name).read_bytes()).hexdigest(),
                               'bytes': (ROOT / name).stat().st_size} for name in artifacts}
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + '\n', encoding='utf8')
    print(f'{result.testsRun} checks; failures={len(result.failures)}; errors={len(result.errors)}; native/GUI pending')
    for test, trace in result.failures + result.errors:
        print(str(test), '\n', '\n'.join(line[:250] for line in trace.splitlines()[:8]))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
