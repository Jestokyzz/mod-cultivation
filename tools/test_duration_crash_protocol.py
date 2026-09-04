"""Reproduce the Celestial Rupture aura-construction crash on the isolated v3 realm.

The disposable protocol fixture receives temporary GM access only long enough to
invoke the stock `.aura` command on itself. Access is removed in every outcome.
Production endpoints and databases are not options in the imported harness.
"""
import json
from pathlib import Path
import secrets
import struct
import sys
import time


sys.argv.extend(['--v3', '--schema5'])
import test_world_protocol as world  # noqa: E402


REPORT = Path(__file__).resolve().parents[1] / 'generated/v1.5.0/world_protocol_test.json'
RESULT = Path(__file__).resolve().parents[1] / 'generated/v1.5.0/duration_crash_protocol_test.json'
SPELL_ID = 86030


def run():
    result = {'spell_id': SPELL_ID, 'status': 'failed'}
    prior = json.loads(REPORT.read_text(encoding='utf-8'))
    assert prior['status'] == 'passed'
    account = int(prior['account_id'])
    guid = int(prior['character_guid'])
    username = world.sql('auth', f'SELECT username FROM account WHERE id={account};')[0][0]
    assert username.startswith('RPTEST_')
    assert world.sql('auth', f'SELECT COUNT(*) FROM account_access WHERE id={account};')[0][0] == '0'

    key = secrets.token_bytes(40)
    client = None
    access_granted = False
    try:
        world.sql('auth', f"UPDATE account SET session_key=UNHEX('{key.hex()}') WHERE id={account};")
        world.sql('auth', f'INSERT INTO account_access(id,gmlevel,RealmID) VALUES({account},3,-1);')
        access_granted = True
        client = world.WorldClient(username, key)
        client.login(guid)
        client.send(0x13D, struct.pack('<Q', guid))  # CMSG_SET_SELECTION
        client.drain()
        client.command(f'.aura {SPELL_ID}')
        messages = client.command('.cultivation rogue status')
        assert any('Текущий путь:' in message for message in messages), messages
        client.command(f'.unaura {SPELL_ID}')
        client.logout()
        result['status'] = 'passed'
        result['check'] = 'real Aura construction completed and the world session remained responsive'
        print(f'PASS: real Aura construction for Celestial Rupture {SPELL_ID}; world session remained responsive')
    finally:
        if client:
            client.close()
        if access_granted:
            world.sql('auth', f'DELETE FROM account_access WHERE id={account};')
        assert world.sql('auth', f'SELECT COUNT(*) FROM account_access WHERE id={account};')[0][0] == '0'
        result['temporary_gm_access_removed'] = True
        result['timestamp_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    if not __import__('os').environ.get('MYSQL_PWD'):
        raise SystemExit('Set MYSQL_PWD through the local secret wrapper')
    run()
