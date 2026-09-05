"""Real worldserver integration test, isolated fixture DBs and localhost:8097 only.

Does not drive the GUI, authenticate an existing account, or claim client acceptance.
A unique disposable ordinary-player account owns every modified character row.
Its random world-session key is never logged. Production endpoints are not options.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import select
import socket
import struct
import subprocess
import time
import sys

ROOT = Path(__file__).resolve().parents[1]
MYSQL = Path(r"C:\Solo WotLK\WoWBotServer\deps\mysql-8.4.10-winx64\bin\mysql.exe")
REPORT = ROOT / "generated" / "world_protocol_test.json"
V3 = '--v3' in sys.argv
SCHEMA3 = '--schema3' in sys.argv
SCHEMA4 = '--schema4' in sys.argv
SCHEMA5 = '--schema5' in sys.argv
SCHEMA6 = '--schema6' in sys.argv
DISPLAY_SCHEMA = SCHEMA3 or SCHEMA4 or SCHEMA5 or SCHEMA6
LATEST_SCHEMA = SCHEMA5 or SCHEMA6
V2 = '--v2' in sys.argv or V3 or SCHEMA6
CELESTIAL_ONLY = '--celestial-only' in sys.argv
RESOURCES_ONLY = '--resources-only' in sys.argv
SHA_SINISTER_ONLY = '--sha-sinister-only' in sys.argv
SHA41_ONLY = '--sha41-only' in sys.argv
SHADOWSTEP_ONLY = '--shadowstep-only' in sys.argv
CELESTIAL_ONLY = CELESTIAL_ONLY or RESOURCES_ONLY
DB_VERSION = 'v1' if SCHEMA6 else 'v3' if V3 else 'v2' if V2 else 'v1'
DB_PREFIX = 'cultivation_test_' if SCHEMA6 else 'rogue_paths_test_'
WORLD_PORT = 8099 if (V3 or SCHEMA6) else 8098 if V2 else 8097
REPORT_ROOT = ROOT / 'generated' / 'v1.2.0' if V3 else ROOT / 'generated' / 'v1.1.0' if V2 else ROOT / 'generated'
if SCHEMA3:
    assert V3, 'Schema 3 is isolated to v3'
    REPORT_ROOT = ROOT / 'generated/v1.3.0'
if SCHEMA4:
    assert V3 and not SCHEMA3 and not SCHEMA5, 'Schema 4 is isolated to v3 and mutually exclusive'
    REPORT_ROOT = ROOT / 'generated/v1.4.0'
if SCHEMA5:
    assert V3 and not SCHEMA3 and not SCHEMA4, 'Schema 5 is isolated to v3 and mutually exclusive'
    REPORT_ROOT = ROOT / 'generated/v1.5.0'
if SCHEMA6:
    assert not (SCHEMA3 or SCHEMA4 or '--schema5' in sys.argv), 'Schema 6 is mutually exclusive'
    REPORT_ROOT = ROOT / 'generated/v2.0.0'
REPORT_ROOT.mkdir(parents=True, exist_ok=True)
REPORT = REPORT_ROOT / 'world_protocol_test.json'
if CELESTIAL_ONLY:
    assert V3, 'Native Celestial harness is restricted to v3'
    REPORT = REPORT_ROOT / 'celestial_native_test.json'
if RESOURCES_ONLY:
    REPORT = REPORT_ROOT / 'celestial_resources_native_test.json'
if SHA_SINISTER_ONLY:
    assert V3, 'Sha proc harness is restricted to v3'
    REPORT = REPORT_ROOT / 'sha_sinister_native_test.json'
if SHA41_ONLY:
    assert V3, 'Sha candidate41 harness is restricted to v3'
    REPORT = REPORT_ROOT / 'sha_candidate41_native_test.json'
if SHADOWSTEP_ONLY:
    assert SCHEMA6, 'Shadowstep fixture is isolated to Cultivation v1'
    REPORT = REPORT_ROOT / 'shadowstep_native_test.json'
TALENTS_ONLY = '--talents-only' in sys.argv
RESTART_ONLY = '--restart-only' in sys.argv
if TALENTS_ONLY:
    REPORT = REPORT_ROOT / 'talent_protocol_test.json'
if RESTART_ONLY:
    REPORT = REPORT_ROOT / 'restart_protocol_test.json'


def sql(database, statement):
    assert database in ("auth", "characters", "world")
    result = subprocess.run(
        [str(MYSQL), "--host=127.0.0.1", "--port=3306", "--user=acore",
         "--default-character-set=utf8mb4", "--batch", "--raw", "--skip-column-names",
         "--database=" + DB_PREFIX + database + "_" + DB_VERSION],
        input=statement, text=True, encoding="utf-8", capture_output=True, check=False)
    if result.returncode:
        # SQL may contain the fixture session key: never echo it on failure.
        raise RuntimeError("Isolated fixture SQL failed (statement withheld)" if database == 'auth' else result.stderr.strip())
    return [row.split("\t") for row in result.stdout.strip().splitlines()]


def wait_sql(database, statement, predicate, timeout=8):
    # Logout's packet precedes the asynchronous characters transaction commit.
    deadline = time.monotonic() + timeout
    while True:
        rows = sql(database, statement)
        if predicate(rows) or time.monotonic() >= deadline:
            return rows
        time.sleep(0.2)


class RC4:
    def __init__(self, key):
        self.s = list(range(256))
        j = 0
        for i in range(256):
            j = (j + self.s[i] + key[i % len(key)]) & 255
            self.s[i], self.s[j] = self.s[j], self.s[i]
        self.i = self.j = 0
        self.apply(bytes(1024))

    def apply(self, data):
        output = bytearray()
        for b in data:
            self.i = (self.i + 1) & 255
            self.j = (self.j + self.s[self.i]) & 255
            self.s[self.i], self.s[self.j] = self.s[self.j], self.s[self.i]
            output.append(b ^ self.s[(self.s[self.i] + self.s[self.j]) & 255])
        return bytes(output)


class WorldClient:
    def __init__(self, username, key):
        self.sock = socket.create_connection(("127.0.0.1", WORLD_PORT), timeout=10)
        self.enc = self.dec = None
        self.spells = set()
        self.buttons = []
        self.cooldowns = {}
        self.messages = []
        self.packet_sequence = 0
        self.cooldown_packet_events = []
        self.modify_cooldown_events = []
        self.pct_spell_mod_events = []
        self.spell_go_events = []
        opcode, challenge = self.receive()
        assert opcode == 0x1EC, hex(opcode)
        seed = secrets.token_bytes(4)
        digest = hashlib.sha1(username.encode() + bytes(4) + seed + challenge[4:8] + key).digest()
        payload = (struct.pack("<II", 12340, 0) + username.encode() + b"\0" +
                   struct.pack("<I", 0) + seed + struct.pack("<IIIQ", 0, 0, 1, 0) +
                   digest + bytes(4))
        self.send(0x1ED, payload)
        self.enc = RC4(hmac.new(bytes.fromhex("C2B3723CC6AED9B5343C53EE2F4367CE"), key, "sha1").digest())
        self.dec = RC4(hmac.new(bytes.fromhex("CC98AE04E897EACA12DDC09342915357"), key, "sha1").digest())
        auth = self.until(0x1EE)
        assert auth[0] == 0x0C, f"World authentication response {auth[0]}"

    def read(self, length):
        data = bytearray()
        while len(data) < length:
            chunk = self.sock.recv(length - len(data))
            if not chunk:
                raise ConnectionError("Isolated worldserver closed fixture session")
            data.extend(chunk)
        return bytes(data)

    def receive(self):
        first = self.read(1)
        if self.dec:
            first = self.dec.apply(first)
        rest = self.read(4 if first[0] & 0x80 else 3)
        if self.dec:
            rest = self.dec.apply(rest)
        header = first + rest
        if first[0] & 0x80:
            size = ((first[0] & 0x7F) << 16) | (header[1] << 8) | header[2]
            opcode = struct.unpack_from("<H", header, 3)[0]
        else:
            size = struct.unpack_from(">H", header)[0]
            opcode = struct.unpack_from("<H", header, 2)[0]
        assert 2 <= size <= 0x800000
        body = self.read(size - 2)
        self.observe(opcode, body)
        return opcode, body

    def send(self, opcode, body=b""):
        header = struct.pack(">H", len(body) + 4) + struct.pack("<I", opcode)
        self.sock.sendall((self.enc.apply(header) if self.enc else header) + body)

    def observe(self, opcode, body):
        self.packet_sequence += 1
        if SHA_SINISTER_ONLY and opcode == 0x250:  # SMSG_SPELLNONMELEEDAMAGELOG
            offset = 0
            for _ in range(2):  # target and attacker packed GUIDs
                mask = body[offset]
                offset += 1 + mask.bit_count()
            spell, damage = struct.unpack_from('<II', body, offset)
            if spell in (86274, 86551) and damage:
                if not hasattr(self, 'sha_damage_events'):
                    self.sha_damage_events = []
                self.sha_damage_events.append((spell, damage))
        if opcode == 0x132:  # SMSG_SPELL_GO
            self.spell_go_events.append((self.packet_sequence, body))
        if opcode == 0x129 and body[0] != 2:
            self.buttons = list(struct.unpack_from("<" + "I" * ((len(body) - 1) // 4), body, 1))
        elif opcode == 0x12A:
            count = struct.unpack_from("<H", body, 1)[0]
            self.spells = {struct.unpack_from("<I", body, 3 + n * 6)[0] for n in range(count)}
            offset = 3 + count * 6
            # Some legacy core records are omitted despite the advertised count.
            for pos in range(offset + 2, len(body) - 15, 16):
                spell, item, category, duration, category_duration = struct.unpack_from("<IHHII", body, pos)
                self.cooldowns[spell] = (max(duration, category_duration), category)
        elif opcode == 0x12B:
            self.spells.add(struct.unpack_from("<I", body)[0])
        elif opcode == 0x203:
            self.spells.discard(struct.unpack_from("<I", body)[0])
        elif opcode == 0x12C:
            old, new = struct.unpack_from("<II", body)
            self.spells.discard(old)
            self.spells.add(new)
        elif opcode == 0x134:  # SMSG_SPELL_COOLDOWN
            for pos in range(9, len(body) - 7, 8):
                spell, duration = struct.unpack_from("<II", body, pos)
                self.cooldowns[spell] = (duration, 0)
                self.cooldown_packet_events.append((self.packet_sequence, spell, duration))
        elif opcode == 0x491:  # SMSG_MODIFY_COOLDOWN
            spell = struct.unpack_from("<I", body, 0)[0]
            adjustment = struct.unpack_from("<i", body, 12)[0]
            self.modify_cooldown_events.append((self.packet_sequence, spell, adjustment))
        elif opcode == 0x267:  # native SMSG_SET_PCT_SPELL_MODIFIER: family bit, op, value
            self.pct_spell_mod_events.append(struct.unpack_from('<BBi', body))
        elif opcode == 0x1DE:  # SMSG_CLEAR_COOLDOWN
            self.cooldowns.pop(struct.unpack_from("<I", body)[0], None)
        elif opcode == 0x096 and body and body[0] == 0:  # CHAT_MSG_SYSTEM
            size = struct.unpack_from("<I", body, 25)[0]
            self.messages.append(body[29:29 + size].rstrip(b"\0").decode("utf-8", "replace"))

    def until(self, wanted, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.sock.settimeout(max(0.1, deadline - time.monotonic()))
            opcode, body = self.receive()
            if opcode == wanted:
                return body
        raise TimeoutError(f"Missing server opcode {wanted:#x}")

    def drain(self, seconds=0.7):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if select.select([self.sock], [], [], min(0.1, deadline - time.monotonic()))[0]:
                self.receive()

    def command(self, command):
        self.messages.clear()
        self.send(0x095, struct.pack("<II", 1, 7) + command.encode("utf-8") + b"\0")
        self.drain()
        return list(self.messages)

    def login(self, guid):
        self.send(0x037)
        self.until(0x03B)
        self.send(0x03D, struct.pack("<Q", guid))
        self.until(0x236)
        self.drain(1.0)

    def close(self):
        self.sock.close()

    def logout(self):
        self.send(0x04B)
        self.until(0x04D, timeout=30)
        self.spells.clear()
        self.cooldowns.clear()

    def create_character(self, name, class_id=4):
        self.send(0x036, name.encode() + b"\0" + bytes([1, class_id, 0, 0, 0, 0, 0, 0, 0]))
        assert self.until(0x03A)[0] == 0x2F, "Character creation failed"

    def cast_self(self, spell):
        self.send(0x12E, struct.pack('<BIBI', 1, spell, 0, 0))


def test_talent_fixture(client, account, guid, report):
    # These isolated talent rows test ownership and synchronization, not the
    # client's talent-tree spending UI. Never write an online character.
    sql('characters', f'UPDATE characters SET talentGroupsCount=2,activeTalentGroup=0 WHERE guid={guid} AND account={account};' +
        f'INSERT INTO character_talent(guid,spell,specMask) VALUES({guid},1329,1),({guid},14195,1),({guid},51713,2),({guid},31230,2);' +
        f'INSERT INTO character_spell(guid,spell,specMask) VALUES({guid},1329,1),({guid},51713,2),({guid},63644,3),({guid},63645,3) ON DUPLICATE KEY UPDATE specMask=VALUES(specMask);' +
        f'INSERT INTO character_action(guid,spec,button,action,type) VALUES({guid},0,10,1329,0),({guid},1,10,51713,0) ON DUPLICATE KEY UPDATE action=VALUES(action),type=0;')
    if V2:
        sql('characters', f'INSERT INTO character_talent(guid,spell,specMask) VALUES({guid},14278,1);' +
            f'INSERT INTO character_spell(guid,spell,specMask) VALUES({guid},14278,1);' +
            f'INSERT INTO character_action(guid,spec,button,action,type) VALUES({guid},0,11,14278,0) ON DUPLICATE KEY UPDATE action=VALUES(action),type=0;' +
            f'INSERT INTO character_spell_cooldown(guid,spell,category,item,time,needSend) VALUES({guid},14278,0,0,UNIX_TIMESTAMP()+900,1);')
    display_manifest = json.loads((ROOT / 'data/cultivation_rogue_spell_manifest.json').read_text(encoding='utf-8')) if DISPLAY_SCHEMA else None
    primary_bases, secondary_bases = set(), set()
    if DISPLAY_SCHEMA:
        for ability in display_manifest['passive_spells']:
            if ability['type'] == 'common_passive':
                continue
            chain = ability['base_spell_chain']
            primary_bases.add(chain[-1])
            sql('characters', f'INSERT INTO character_talent(guid,spell,specMask) VALUES({guid},{chain[-1]},1) ON DUPLICATE KEY UPDATE specMask=1;')
            if len(chain) > 1:
                secondary_bases.add(chain[0])
                sql('characters', f'INSERT INTO character_talent(guid,spell,specMask) VALUES({guid},{chain[0]},2) ON DUPLICATE KEY UPDATE specMask=2;')
    talent_mask_before = int(sql('characters', f'SELECT SUM(specMask) FROM character_talent WHERE guid={guid};')[0][0])
    def check_displays(path, bases):
        if not DISPLAY_SCHEMA:
            return
        all_ids = {row['spell_id'] for row in display_manifest['display_passives']}
        expected = {row['spell_id'] for row in display_manifest['display_passives'] if row['path'] == path and
                    (not row['talent_required'] or row['base_spell'] in bases)} if path else set()
        actual = all_ids.intersection(client.spells)
        assert actual == expected, ('display ownership', path, sorted(actual), sorted(expected))
        assert not any(button in all_ids for button in client.buttons), 'Display-only passive leaked onto action bar'
    client.login(guid)
    messages = client.command('.cultivation rogue sha')
    check_displays('sha', primary_bases)
    if DISPLAY_SCHEMA:
        before_buttons = list(client.buttons)
        client.command('.cultivation rogue sync')
        check_displays('sha', primary_bases)
        assert client.buttons == before_buttons, 'Display sync changed actions'
        client.command('.cultivation rogue celestial')
        check_displays('celestial', primary_bases)
        client.command('.cultivation rogue sha')
        check_displays('sha', primary_bases)
        report['checks'].append('six passive talents: exact highest active-spec display rank; sync idempotent; Celestial/Sha swap removes opposite displays; no action-bar passives')
    assert client.buttons[10] == 86251, ('Mutilate button', client.buttons[10], messages)
    assert 86256 in client.spells and 86306 not in client.spells
    report['checks'].append('active-spec Mutilate full rank chain; inactive Shadow Dance excluded')
    assert int(sql('characters', f'SELECT SUM(specMask) FROM character_talent WHERE guid={guid};')[0][0]) == talent_mask_before
    if V2:
        assert 86327 in client.spells and 14278 not in client.spells
        assert client.buttons[11] == 86327
        assert client.cooldowns[86327][0] > 850000
    client.cast_self(63644)
    client.drain(7)
    check_displays('sha', secondary_bases)
    assert 86306 in client.spells and 86256 not in client.spells, ('secondary spellbook', sorted(s for s in client.spells if 86000 <= s <= 86999))
    assert client.buttons[10] == 86306, ('secondary async action-button load', client.buttons[10])
    report['checks'].append('native spec-switch cast: Mutilate removed, Shadow Dance learned, async buttons remapped')
    if V2:
        assert 86327 not in client.spells and 86127 not in client.spells and 14278 not in client.spells
    client.cast_self(63645)
    client.drain(7)
    check_displays('sha', primary_bases)
    assert 86256 in client.spells and 86306 not in client.spells
    assert client.buttons[10] == 86251, ('primary async action-button load', client.buttons[10])
    report['checks'].append('native return to primary spec and talent points preserved')
    if V2:
        assert 86327 in client.spells and client.buttons[11] == 86327
        assert client.cooldowns[86327][0] > 800000
        report['checks'].append('Ghostly Strike: active talent required, stock removed, own slot and cooldown survive both native spec switches')
    client.logout()
    if DISPLAY_SCHEMA:
        ids = ','.join(str(row['spell_id']) for row in display_manifest['display_passives'])
        assert int(sql('characters', f'SELECT COUNT(*) FROM character_aura WHERE guid={guid} AND spell IN ({ids});')[0][0]) == 0, 'Display-only spell created persistent mechanic aura'
        # Deliberately leave the old display learned in character_spell: login must clean it.
        sql('characters', f'DELETE FROM character_talent WHERE guid={guid} AND spell=51701 AND specMask=1;' +
            f'INSERT INTO character_talent(guid,spell,specMask) VALUES({guid},51700,1);')
        primary_bases.remove(51701)
        primary_bases.add(51700)
        client.login(guid)
        client.drain(2)
        check_displays('sha', primary_bases)
        report['checks'].append('relog and HAT rank change: stale rank-3 display removed; rank-2 display learned; display spells create no saved gameplay auras')
        client.command('.cultivation rogue reset')
        check_displays(None, set())
        assert int(sql('characters', f'SELECT SUM(specMask) FROM character_talent WHERE guid={guid};')[0][0]) == talent_mask_before
        report['checks'].append('path reset removes all 42 display candidates and keeps talent fixture unchanged')
        client.logout()


def run():
    report = {"scope": "real world protocol; NOT GUI/authserver/combat acceptance", "checks": [], "status": "running"}
    client = None
    try:
        # A spawned process is not a ready world. Never create an account until
        # the exact isolated listener and its startup validation are ready.
        server_log = (max(Path(r'C:\Solo WotLK\test-server\20260904-cultivation-v1\logs').glob('world-stdout*.log'),
                          key=lambda path: path.stat().st_mtime)
                      if SCHEMA6 else
                      Path(r'C:\Solo WotLK\test-server') / ('20260831-rogue-paths-' + DB_VERSION) / 'logs/world-stdout.log')
        deadline = time.monotonic() + 60
        while True:
            log = server_log.read_text(encoding='utf-8', errors='replace')[-24000:]
            if 'mod-cultivation: startup validation failed' in log:
                raise RuntimeError('Isolated startup validation failed; inspect Server.log')
            if ('mod-cultivation: startup validation passed' in log or
                'mod-cultivation: startup validation completed; disabled replacement groups=0' in log):
                try:
                    with socket.create_connection(('127.0.0.1', WORLD_PORT), timeout=1):
                        break
                except OSError:
                    pass
            if time.monotonic() >= deadline:
                raise TimeoutError('Isolated world not ready; no fixture account created')
            time.sleep(0.25)
        if RESTART_ONLY:
            prior = json.loads((REPORT_ROOT / 'world_protocol_test.json').read_text(encoding='utf-8'))
            assert prior['status'] == 'passed'
            account, guid = int(prior['account_id']), int(prior['character_guid'])
            rows = sql('auth', f'SELECT username FROM account WHERE id={account};')
            assert len(rows) == 1 and rows[0][0].startswith('RPTEST_')
            username = rows[0][0]
            assert sql('characters', f'SELECT account,name,online FROM characters WHERE guid={guid};')[0] == [str(account), prior['character_name'], '0']
            assert sql('auth', f'SELECT COUNT(*) FROM account_access WHERE id={account};')[0][0] == '0'
            before = int(sql('characters', f'SELECT time-UNIX_TIMESTAMP() FROM character_spell_cooldown WHERE guid={guid} AND spell=86203;')[0][0])
            assert before > 15, 'Fixture cooldown expired before restart test'
            key = secrets.token_bytes(40)
            sql('auth', f"UPDATE account SET session_key=UNHEX('{key.hex()}') WHERE id={account} AND username='{username}';")
            client = WorldClient(username, key)
            client.login(guid)
            assert client.buttons[:5] == [86203,86201,86274,86263,86209], client.buttons[:5]
            if V2:
                assert client.buttons[5:12] == [86309,86310,86321,86322,86323,86326,86328]
                assert 86441 in client.spells and 1860 not in client.spells
                assert 86327 not in client.spells
            assert before * 1000 - 12000 <= client.cooldowns[86203][0] <= before * 1000 + 2000
            assert any('Ша' in message for message in client.command('.cultivation rogue status'))
            report.update(account_id=account, character_guid=guid, character_name=prior['character_name'])
            report['checks'].append('existing isolated fixture after externally verified worldserver restart: DB path, spellbook, five downrank buttons and remaining cooldown')
            client.logout()
            report['status'] = 'passed'
            return
        tag = "".join(secrets.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(8))
        username = "RPTEST_" + tag.upper()
        name = "Rp" + tag
        key, salt = secrets.token_bytes(40), secrets.token_bytes(32)
        password = secrets.token_hex(24).upper()
        x = int.from_bytes(hashlib.sha1(salt + hashlib.sha1((username + ":" + password).encode()).digest()).digest(), "little")
        verifier = pow(7, x, int("894B645E89E1535BBDAD5B8B290650530801B18EBFBF5E8FAB3C82872A3E9BB7", 16)).to_bytes(32, "little")
        sql("auth", f"INSERT INTO account(username,salt,verifier,session_key,locale,os) VALUES ('{username}',UNHEX('{salt.hex()}'),UNHEX('{verifier.hex()}'),UNHEX('{key.hex()}'),8,'Win');")
        account = int(sql("auth", f"SELECT id FROM account WHERE username='{username}';")[0][0])
        assert sql("auth", f"SELECT COUNT(*) FROM account_access WHERE id={account};")[0][0] == "0"
        report.update(account_id=account, character_name=name)
        client = WorldClient(username, key)
        client.create_character(name)
        guid_rows = wait_sql("characters", f"SELECT guid FROM characters WHERE account={account} AND name='{name}';", bool)
        assert guid_rows, 'Created character did not reach the characters DB before timeout'
        guid = int(guid_rows[0][0])
        report["character_guid"] = guid
        negative_fixtures = []
        for class_id, level, suffix, expected in [(1, 80, 'w', 'только разбойникам'), (4, 1, 'l', '80-й уровень')]:
            # A tag ending in the chosen suffix used to reproduce the main
            # rogue's exact ten-character name (for example ...w + warrior w).
            # A dedicated fixture prefix makes the names disjoint by design.
            test_name = 'Rn' + tag[:6] + suffix
            client.create_character(test_name, class_id)
            fixture_rows = wait_sql('characters', f"SELECT guid FROM characters WHERE account={account} AND name='{test_name}';", bool)
            assert fixture_rows, 'Negative fixture character did not reach the characters DB before timeout'
            fixture_guid = int(fixture_rows[0][0])
            if level != 1:
                sql('characters', f'UPDATE characters SET level={level} WHERE guid={fixture_guid} AND account={account};')
            negative_fixtures.append((class_id, level, expected, fixture_guid))
        spell_manifest = json.loads((ROOT / "data/cultivation_rogue_spell_manifest.json").read_text(encoding="utf-8"))
        by_name = {r["logical_name"]: r for r in spell_manifest["active_spells"]}
        base_buttons = [26889, 1856, 48638, 1752, 31224]
        if V2:
            base_buttons += [1833,53,48657,2094,6770,51724,5938]
        if LATEST_SCHEMA:
            base_buttons += [14185]
        if CELESTIAL_ONLY:
            # Ghostly Strike starts learned. Preparation deliberately does not:
            # the native harness learns it inside the same live world session
            # and proves the next real Sprint changes from 180 to 126 seconds.
            base_buttons += [14278, 11305]
        sql("characters", f"UPDATE characters SET level=80,health=5000,power4=100 WHERE guid={guid} AND account={account};" +
            "INSERT INTO character_spell(guid,spell,specMask) VALUES " + ",".join(f"({guid},{s},1)" for s in base_buttons) + " ON DUPLICATE KEY UPDATE specMask=1;" +
            "INSERT INTO character_action(guid,spec,button,action,type) VALUES " + ",".join(f"({guid},0,{i},{s},0)" for i, s in enumerate(base_buttons)) + " ON DUPLICATE KEY UPDATE action=VALUES(action),type=0;" +
            f"INSERT INTO character_spell_cooldown(guid,spell,category,item,time,needSend) VALUES({guid},26889,0,0,UNIX_TIMESTAMP()+900,1);")
        if CELESTIAL_ONLY:
            # This disposable character is promoted directly from level 1 to
            # 80. Seed its normal defence skill before login so character-sheet
            # dodge tests do not include an artificial -400 skill deficit.
            sql('characters', f'INSERT INTO character_skills(guid,skill,value,max) VALUES({guid},95,400,400) ON DUPLICATE KEY UPDATE value=400,max=400;')
            sql('characters', f'INSERT INTO character_talent(guid,spell,specMask) VALUES({guid},14278,1);')
        elif LATEST_SCHEMA and not SHADOWSTEP_ONLY:
            sql('characters', f'INSERT INTO character_talent(guid,spell,specMask) VALUES({guid},14185,1);')
        if TALENTS_ONLY:
            test_talent_fixture(client, account, guid, report)
            report['status'] = 'passed'
            return
        if V2:
            sql('characters', f'INSERT INTO character_spell(guid,spell,specMask) VALUES({guid},1860,1);' +
                f'INSERT INTO character_spell_cooldown(guid,spell,category,item,time,needSend) VALUES({guid},2094,0,0,UNIX_TIMESTAMP()+900,1);')
        client.login(guid)
        if SHADOWSTEP_ONLY:
            report['scope'] = 'native Shadowstep fresh/learn/reset, both paths, real casts; NOT GUI acceptance'
            client.command('.cultivation rogue testshadowstep')
            client.drain(2)
            report['checks'] = [m for m in client.messages if m.startswith('RPSTEP|')]
            summary = [m for m in report['checks'] if m.startswith('RPSTEP|SUMMARY|')]
            assert summary, ('Shadowstep harness did not finish', report['checks'])
            assert summary[-1].split('|')[-1] == '0', summary[-1]
            # Native SPELLMOD_COOLDOWN is sent before casting, not as a forced
            # cooldown packet. Player::AddSpellAndCategoryCooldowns deliberately
            # omits SMSG_SPELL_COOLDOWN when only an ordinary spellmod changed it.
            mods = [event for event in client.pct_spell_mod_events if event[1] == 11]
            expected_bits = {5, 6, 11, 38, 41}
            for bit in expected_bits:
                values = [value for field, op, value in mods if field == bit]
                assert -30 in values and values[-1] == 0, ('Native modifier learn/reset delivery', bit, values)
            report['native_cooldown_modifiers'] = mods
            assert not [event for event in client.modify_cooldown_events if event[1] in (86105, 86305)]
            client.logout()
            report['status'] = 'passed'
            return
        if SHA41_ONLY:
            report['scope'] = 'native Sha candidate41 DBC/config/incoming-damage/control-break contract; NOT GUI acceptance'
            client.command('.cultivation rogue sha')
            client.command('.cultivation rogue testsha41')
            client.drain(2)
            report['checks'] = [m for m in client.messages if m.startswith('RPS41|')]
            summary = [m for m in report['checks'] if m.startswith('RPS41|SUMMARY|')]
            assert summary, ('Sha candidate41 harness did not finish', report['checks'])
            assert summary[-1].split('|')[-1] == '0', summary[-1]
            client.logout()
            report['status'] = 'passed'
            return
        if SHA_SINISTER_ONLY:
            report['scope'] = '2000 real Sha Sinister Strike casts; server queue plus independently received combat-log packets; NOT GUI acceptance'
            client.command('.cultivation rogue sha')
            client.command('.cultivation rogue testshasinister')
            client.drain(16)
            report['checks'] = [m for m in client.messages if m.startswith('RPSS|')]
            summaries = [m for m in report['checks'] if m.startswith('RPSS|SUMMARY|')]
            assert summaries, ('Sha harness did not finish', report['checks'])
            _, _, attempts, hits, procs, errors, status = summaries[-1].split('|')
            events = getattr(client, 'sha_damage_events', [])
            primary = [d for s, d in events if s == 86274]
            extra = [d for s, d in events if s == 86551]
            report.update(attempts=int(attempts), successful_hits=int(hits), non_damaging_attempts=int(attempts)-int(hits), selected_procs=int(procs),
                          harness_errors=int(errors), primary_damage_packets=len(primary),
                          extra_damage_packets=len(extra), observed_percent=100 * len(extra) / max(1, int(hits)))
            assert status == 'PASS', report['checks']
            assert len(primary) == int(hits) == 2000, 'Actual parent damage packet count mismatch'
            assert len(extra) == int(procs), 'Selected proc did not produce exactly one damage packet'
            client.logout()
            report['status'] = 'passed'
            return
        if RESOURCES_ONLY:
            report['scope'] = 'native resource mechanics on disposable RPTEST fixture; NOT GUI acceptance'
            client.command('.cultivation rogue celestial')
            client.command('.cultivation rogue testresources')
            client.drain(41)
            report['checks'] = [m for m in client.messages if m.startswith('RPCT|')]
            summary = [m for m in report['checks'] if m.startswith('RPCT|SUMMARY|')]
            assert summary, ('Resource harness did not finish', report['checks'])
            assert summary[-1].split('|')[-1] == '0', summary[-1]
            client.logout()
            report['status'] = 'passed'
            return
        if CELESTIAL_ONLY:
            report['scope'] = 'native worldserver integration harness, controlled combat inputs; NOT GUI acceptance'
            client.command('.cultivation rogue celestial')
            messages = client.command('.cultivation rogue testcelestial')
            client.drain(2)
            messages = list(client.messages)
            report['native_results'] = [m for m in messages if m.startswith('RPCT|')]
            sprint_spell = by_name["sprint"]["celestial_first"] + 2
            sprint_cooldown = client.cooldowns.get(sprint_spell, (0, 0))[0]
            sprint_go = [sequence for sequence, body in client.spell_go_events
                         if struct.pack('<I', sprint_spell) in body]
            sprint_packets = [(sequence, duration) for sequence, spell, duration in client.cooldown_packet_events
                              if spell == sprint_spell]
            sprint_modifiers = [(sequence, adjustment) for sequence, spell, adjustment in client.modify_cooldown_events
                                if spell == sprint_spell]
            sprint_packet_ok = 120000 <= sprint_cooldown <= 126000
            no_post_cast_modifier = not sprint_modifiers
            packet_ok = sprint_packet_ok and no_post_cast_modifier
            report['native_results'].append(
                f'RPCT|preparation-client-sprint-packet-70pct|{"PASS" if sprint_packet_ok else "FAIL"}|{sprint_cooldown}|126000')
            report['native_results'].append(
                f'RPCT|preparation-no-post-cast-cooldown-correction|{"PASS" if no_post_cast_modifier else "FAIL"}|{len(sprint_modifiers)}|0')
            summary = [m for m in messages if m.startswith('RPCT|SUMMARY|')]
            assert summary, ('Native test harness did not finish', messages)
            report['checks'] = report['native_results']
            assert packet_ok, ('Preparation was not calculated natively before cast', sprint_cooldown, sprint_modifiers)
            assert summary[-1].split('|')[-1] == '0', summary[-1]
            client.logout()
            report['status'] = 'passed'
            return
        assert client.buttons[:len(base_buttons)] == base_buttons, ("baseline buttons", client.buttons[:len(base_buttons)])
        assert not any(86000 <= s <= 86999 for s in client.spells), "Variants auto-learned before path selection"
        report["checks"].append("ordinary-player login and five baseline action slots")
        cycle = [("celestial", 1), ("sha", 2), ("небожитель", 1), ("sha", 2), ("celestial", 1), ("reset", 0)] if LATEST_SCHEMA else [("celestial", 1), ("sha", 2), ("небожитель", 1), ("reset", 0)]
        for command, path in cycle:
            messages = client.command(".cultivation rogue " + command)
            report.setdefault("commands", []).append({"command": command, "messages": messages})
            actual_path = int(sql("characters", f"SELECT path FROM character_cultivation_rogue WHERE guid={guid};")[0][0])
            assert actual_path == path, (command, actual_path, messages)
            mapping = {}
            for row in spell_manifest["active_spells"]:
                for rank, base in enumerate(row["base_spell_chain"]):
                    mapping[base] = base if not path else row["celestial_first" if path == 1 else "sha_first"] + rank
            expected_cycle_buttons = [mapping[s] for s in base_buttons]
            if LATEST_SCHEMA and path == 1:
                expected_cycle_buttons[-1] = 0
            assert client.buttons[:len(base_buttons)] == expected_cycle_buttons, (command, "buttons", client.buttons[:len(base_buttons)])
            if LATEST_SCHEMA:
                saved_slot = int(sql('characters', f'SELECT COUNT(*) FROM character_cultivation_rogue_suppressed_action WHERE guid={guid} AND spec=0 AND button={len(base_buttons)-1};')[0][0])
                assert saved_slot == (1 if path == 1 else 0), (command, 'suppressed Preparation slot', saved_slot)
            if V2:
                safe = 86440 if path == 1 else 86441 if path == 2 else 1860
                assert safe in client.spells and not (set([86440,86441,1860]) - {safe}) & client.spells
                assert client.cooldowns[mapping[2094]][0] > 850000
            for row in spell_manifest['active_spells']:
                wrong = row['base_spell_chain'] if path else []
                for prefix, candidate_path in [('celestial_first', 1), ('sha_first', 2)]:
                    if path != candidate_path:
                        wrong = wrong + [row[prefix] + n for n in range(len(row['base_spell_chain']))]
                assert not client.spells.intersection(wrong), (command, 'opposite/standard spellbook entry', client.spells.intersection(wrong))
            for logical in ("mutilate", "killing_spree", "shadow_dance", "ghostly_strike") if V2 else ("mutilate", "killing_spree", "shadow_dance"):
                row = by_name[logical]
                assert not any(row[prefix] + rank in client.spells for prefix in ("celestial_first", "sha_first") for rank in range(len(row["base_spell_chain"]))), (command, "unearned talent", logical)
            cooldown = client.cooldowns.get(mapping[26889], (0, 0))[0]
            assert 850000 < cooldown <= 900000, (command, "lost cooldown", cooldown, client.cooldowns)
            report["checks"].append(command + ": DB persistence, buttons/downranks, talent exclusion, cooldown preserved")
        if LATEST_SCHEMA:
            report['checks'].append('Celestial/Sha/Celestial/Sha/Celestial/reset: ordinary actions stay in place; passive Preparation slot is durably suppressed and restored')
        assert any('завершена' in m for m in client.command('.cultivation rogue sync'))
        expected_schema = '6' if SCHEMA6 else '5' if SCHEMA5 else '4' if SCHEMA4 else '3' if SCHEMA3 else '2' if V3 else '1'
        assert any(('Версия синхронизации: ' + expected_schema) in m for m in client.command('.cultivation rogue status'))
        client.command('.cultivation rogue sha')
        expected_buttons = [r for r in client.buttons[:len(base_buttons)]]
        client.logout()
        saved = wait_sql('characters', f'SELECT spell,time-UNIX_TIMESTAMP() FROM character_spell_cooldown WHERE guid={guid} AND spell BETWEEN 86201 AND 86203;', lambda rows: bool(rows))
        assert len(saved) == 1 and int(saved[0][1]) > 800, ('persisted cooldown', saved)
        client.login(guid)
        assert client.buttons[:len(base_buttons)] == expected_buttons, ('relog buttons', client.buttons[:len(base_buttons)])
        assert client.cooldowns.get(86203, (0,))[0] > 800000, 'relog cooldown lost'
        assert any('Ша' in m for m in client.command('.cultivation rogue status')), 'relog path lost'
        report['checks'].append('sync/status, logout DB save, relog path/actionbar/cooldown')
        print('PASS: sync/status and relog with persistent path/actionbar/cooldown', flush=True)
        client.logout()
        if V2:
            saved_spells = {int(r[0]) for r in wait_sql('characters', f'SELECT spell FROM character_spell WHERE guid={guid};', lambda r: bool(r))}
            for name in ('backstab', 'sap'):
                row = by_name[name]
                required = {row['sha_first'] + n for n in range(len(row['base_spell_chain']))}
                assert required <= saved_spells, (name, 'missing persisted ranks', required - saved_spells)
                assert not set(row['base_spell_chain']) & saved_spells
            report['checks'].append('all 12 Backstab and 4 Sap ranks persisted as Sha only; Safe Fall visible passive replaces stock; Blind cooldown and 12 buttons retained')
        # Offline character fixture edits below only affect freshly created GUIDs.
        # No GM permission is granted, including for negative command tests.
        for class_id, level, expected, fixture_guid in negative_fixtures:
            client.login(fixture_guid)
            messages = client.command('.cultivation rogue celestial')
            assert any(expected in m for m in messages), (class_id, level, messages)
            assert not any(86000 <= s <= 86999 for s in client.spells)
            assert sql('characters', f'SELECT COUNT(*) FROM character_cultivation_rogue WHERE guid={fixture_guid} AND path<>0;')[0][0] == '0'
            report['checks'].append(f'ordinary-player rejection: class={class_id}, level={level}')
            client.logout()
        report["status"] = "passed"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
        raise
    finally:
        if client:
            if CELESTIAL_ONLY:
                ghost_hits = []
                for sequence, body in client.spell_go_events:
                    offset = 0
                    for _ in range(2):
                        offset += 1 + body[offset].bit_count()
                    spell_id = struct.unpack_from('<I', body, offset + 1)[0]
                    if spell_id != 86127:
                        continue
                    offset += 13
                    hits = body[offset]
                    offset += 1 + 8 * hits
                    misses = body[offset]
                    ghost_hits.append({'sequence': sequence, 'hits': hits, 'misses': misses,
                                       'first_miss_reason': body[offset + 9] if misses else None})
                report['ghostly_spell_go_outcomes'] = ghost_hits
            client.close()
        report["timestamp_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if not os.environ.get("MYSQL_PWD"):
        raise SystemExit("Run through test_world_protocol.ps1 (private DB credentials)")
    run()
