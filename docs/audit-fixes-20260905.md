# Audit fixes candidate, 2026-09-05

Status: implementation in progress; no production deployment or acceptance.
Backup: F:\JestokyCraft Backups\cultivation\pre-change-audit-fixes-20260905\manifest.json (147 verified files).

## Observable acceptance transitions

- Fresh path, no talent learned -> open talent tooltip -> path-specific cost/cooldown and description already agree; learning does not change their provenance.
- Celestial/Sha Shadowstep -> actual cast -> 30 sec native cooldown (Celestial Preparation:21), stealth preserved for Celestial, no self-target, +70% speed/3 sec and -50% next-ability threat preserved, stock +20 damage absent; Sha custom +40 remains.
- Sha Kidney, 1..5 CP -> successive real casts -> base 1..5 sec then native half/quarter/immune DR; tooltip lists the same base values.
- Sha Premeditation -> no follow-up -> one expiry after6 sec, exactly granted CP removed at most once. Follow-up/finisher/target change -> old expiry cannot remove new CP.
- Hemorrhage -> successful physical hit -> one visible own charge spent. Miss/dodge/parry -> unchanged. Celestial physical finisher -> bonus without charge consumption. Expiry60 sec or path cleanup -> no stale effect.
- Celestial Shadow Dance -> Garrote periodic damage -> the described -20% applies to damage; no double application.
- Sha stacked direct bonuses -> combined before mitigation -> cap remains60, with player-facing explanation.
- DBC regeneration -> all locale references in bounds -> baseline custom PvP numeric fields preserved.

## Gates

Source/schema regression, data generation with semantic diff, compiled isolated native tests (separate build permission), protocol tests, Lua5.1 mocked lifecycle checks, clone1920x1080 borderless GUI before first learn/cast. No production promotion until clone acceptance; no GitHub release until explicit user acceptance.

Existing audit tests are evidence of the old failure, not implementation prescriptions. New behavior tests must not merely check the names of auras or presence of code strings.

## Source/data implementation and checks

- Source corrections cover the audit contracts above. Sha cap remains 60 in config defaults and the same additive damage calculation; the shared passive now explains it.
- Both generated Spell.dbc copies have identical non-string semantics across ALL records, not just Cultivation IDs. All locale offsets are validated. 42 foreign description/aura references restored from the verified Twin Peaks donor; numeric data unchanged.
- Native Dance cost auras use flat SPELLMOD_COST (-20 on Backstab/Ambush, -15 on Garrote/Cheap Shot), with removal during normal and technical/path cleanup. The previous cost-hook deduction was removed to avoid double discounts.
- Premeditation finalization moved from per-target AfterHit to once-per-cast AfterCast: the spell has an enemy CP effect AND a self aura. Energy restoration/retention must not run twice. Actual retained points are clamped to the observed grant at 0/4/5 CP.
- 96 Python source/data contract tests passed. These do not prove runtime combat behavior.
- 5 Lua 5.1 tests execute the actual native header: initial Sha Preparation, Ghostly cost/CD, Step 30 -> learn Preparation -> 21 -> reset -> 30, passive Preparation metadata, and a late/replaced talent button handler. Unknown custom spell info deliberately errors in the fixture. Native DBC body is unchanged.
- SQL base verified with `--sql-check-only`; no SQL/database writes. Production client/server files and running process remain untouched.

## Authorized build and isolated tests

Candidate: `v2.0.0-audit-candidate5`, unaccepted. User authorized the C++ build and isolated server tests. Build completed; only test-server `20260904-cultivation-v1` (8099, separate cultivation_test databases, 200 bots) and test-client `20260831-rogue-paths-v3` were updated. Production processes and files were not changed. No GitHub publication.

- 102 Python/data/Lua checks passed after the final test changes.
- Shadowstep: 84 native checks passed (30/21 before cast, reset, real friendly/enemy/self casts, speed, threat, stealth); protocol confirms native modifier delivery and no post-cast correction packet.
- Extended Sha/common harness: 68 checks passed. Real Hemorrhage casts expose 5/20 charges for60 seconds; calculation and foreign hits preserve them, own hit consumes one, Celestial finisher preserves the charge. Native Dance costs change by20/15 before first attack and restore on removal. Real Sha Kidney casts at1..5 CP produce1000..5000ms before DR.
- Resources: 51 checks passed. Includes Combat Potency ranks1..5, Mutilate upfront cost/refund, Honor reserve, Celestial Premeditation30s, Sha0/4/5 CP grants and retention, one40-energy award per cast, preservation of old points, continuation, and real6-second expiry.
- Ordinary-player protocol cycle/relog passed: path persistence, action slots, rank chains, passive Preparation suppression, retained cooldowns, class/level negative cases.
- Complete X/Z owner copies were packaged with exact replacements and SHA-256 readback. X's existing `FrameXML.toc -> CustomItemTooltips.lua` route is unchanged; only the verified old header suffix was replaced, not the unrelated prefix. Full embedded Lua compiles under5.1. No archive reconstruction or compact. Both MPQs installed only in closed clone after backup/patch-chain preflight. Clone config remains1920x1080 borderless.

### Rejected startup candidate and open checks

Candidate4 registered AuraScript proc hooks for non-aura spells through the shared SQL loader. `Load()` filtering was too late for `_Init -> Register -> Validate`. Test binary/DBC/logs were preserved under `F:\JestokyCraft Backups\cultivation\failed-audit-candidate4-20260905`, test binary/DBC rolled back, a pre-Load regression added, then registration guarded by initialized script ID. Candidate5 startup has no new Cultivation script validation errors; unrelated existing loot-data warnings remain.

One full Celestial run had3 Ghostly Strike assertion failures (missing dodge aura, unchanged dodge statistic,0 CP). Fourteen subsequent fresh-fixture runs passed; later runs also captured actual SPELL_GO hit/miss outcomes. The first failing run lacked that detail, so its root cause is **unresolved**, not silently declared fixed by reruns. Further investigation must preserve a failing cast result/hit outcome before changing gameplay.

Remaining acceptance: fresh-client GUI before learning/casting; actual PvP half/quarter/immune DR sequence; Hemorrhage miss/dodge/parry and damage-bonus magnitude; Garrote periodic health delta during Dance and no double reduction; Premeditation after target change/finisher. Current native tests cover only the cases explicitly listed above.

GUI tooling is blocked: computer-use initialization failed twice (including kernel reset) with `failed to write kernel assets ... os error 3`. No GUI screenshot/cast/tooltip acceptance is claimed. Status: **candidate installed, client acceptance pending**. Test client was not launched automatically. Production promotion and publication remain blocked until required acceptance, not merely compilation/static PASS.

## User acceptance and production promotion, 2026-09-05

The preceding GUI-blocked statement describes the earlier state. After restarting Codex, Computer Use worked. The correct test executable is `C:\Solo WotLK\test-client\20260831-rogue-paths-v3\Wow-NWQ.exe`; launching stock Wow.exe was an operator mistake, not evidence of a failed NWQ candidate. The agent observed the logged-in rogue and opened the talent tree. Detailed tooltip checking was not independently replayed by the agent.

User explicitly accepted the tested candidate: «Крч всё окей. Ставь на основной сервер и клиент». Promotion is authorized to `C:\Games\JestokyCraft` and the production server. The outstanding edge-case checks and the first Ghostly harness failure remain documented above; user acceptance does not convert unexecuted cases into test passes.

Pre-promotion regression: all 102 checks passed with the existing Lua 5.1 runtime. Default Python alone lacked `lupa.lua51`; rerunning with the established local dependency path resolved the test-environment import error without changing gameplay.

Deployment evidence: `C:\Solo WotLK\work\cultivation-audit-20260905\production-install.json`. Pre-change backup and restore verification: `F:\JestokyCraft Backups\cultivation\pre-production-audit5-20260905\manifest.json`. Transfer scope: complete verified X/Z MPQs, compiled worldserver, server Spell.dbc. All other generated server DBCs match production. Runtime DLL hashes match the tested server. Client EXE, WTF, server configuration and SQL are not replaced; the Sha direct bonus cap remains 60. No GitHub publication is part of this deployment.
