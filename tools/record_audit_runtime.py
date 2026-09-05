"""Record measured candidate evidence, with explicit untested and unresolved gates."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path(r'C:\Solo WotLK')


def artifact(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size}


def main():
    state_path = ROOT / 'audit-fixes-manifest.json'
    state = json.loads(state_path.read_text('utf8'))
    reports = ['shadowstep_native_test.json', 'sha_candidate41_native_test.json',
               'celestial_resources_native_test.json', 'world_protocol_test.json', 'celestial_native_test.json']
    evidence = {}
    for name in reports:
        path = ROOT / 'generated/v2.0.0' / name
        data = json.loads(path.read_text('utf8'))
        assert data['status'] == 'passed', name
        evidence[name] = {**artifact(path), 'status': data['status'], 'scope': data['scope']}
    state['status'] = 'test-candidate-installed-acceptance-pending'
    state['native_acceptance'] = 'covered-cases-passed; remaining matrix and Ghostly first-run failure unresolved'
    state['gui_acceptance'] = 'blocked-computer-use-os-error-3; no GUI observation'
    state['build_authorized'] = True
    state['production_modified'] = False
    state['installable_package'] = False
    state['native_reports'] = evidence
    state['runtime_artifacts'] = {
        'build_worldserver': artifact(PROJECT / 'WoWBotServer/build-solitary-v4-ninja/bin/worldserver.exe'),
        'test_worldserver': artifact(PROJECT / 'test-server/20260904-cultivation-v1/worldserver.exe'),
        'test_server_spell': artifact(PROJECT / 'test-server/20260904-cultivation-v1/data/dbc/Spell.dbc'),
        'package_manifest': artifact(ROOT / 'client_patch/build/v2.0.0-audit-candidate5/manifest.json')}
    assert state['runtime_artifacts']['build_worldserver']['sha256'] == state['runtime_artifacts']['test_worldserver']['sha256']
    state['open_checks'] = ['fresh-client GUI', 'PvP DR sequence', 'Hemorrhage failed-hit charge preservation and damage magnitude',
                            'Dance Garrote periodic damage', 'Premeditation target change/finisher',
                            'unresolved first full-harness Ghostly failure; fourteen fresh reruns passed']
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print('Recorded tested scope and open gates; no production/release acceptance')


if __name__ == '__main__':
    main()
