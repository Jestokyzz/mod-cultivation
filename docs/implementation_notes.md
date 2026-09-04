# Cultivation / Rogue — implementation invariants

Audit baseline: AzerothCore commit `7c8ed00e7f654617a47bdf728b49707f60aa1aae`, branch `release/solitary-1.4.5-rc1`.

## Durable state and synchronization

- `character_cultivation_rogue` in the characters database is the only durable source of truth.
- `RoguePath::None`, `Celestial`, and `Sha` are the only valid values.
- Login, level, trainer learning, talent learning/reset, active spec change, command sync, path switch, and reset run the same idempotent synchronization service.
- A synchronization transaction learns the destination spell first, copies the complete cooldown record, preserves the action-button type and slot, removes the source spell, and sends one action-bar update.
- Standard, Celestial, and Sha active variants are mutually exclusive. Passive talent ranks stay represented in the talent system, while only the replaced proc component is suppressed.

## Mechanical invariants

- Effects described as personal are keyed by both rogue GUID and target GUID.
- Direct damage excludes auto attacks, periodic damage, poison damage, reflected damage, item procs, and module-triggered secondary damage unless explicitly allowed.
- Miss, dodge, parry, immune, evade, or an aborted cast cannot trigger successful-hit mechanics.
- Finishers use the combo points captured for the actual cast; energy refunds never exceed the energy spent.
- Every secondary attack carries a recursion guard.
- Internal cooldowns and post-burst penalties are independent of Preparation.
- PvP values apply when the victim is a player or is controlled by a player.
- Celestial Preparation is a native pre-cast percentage spell modifier, never a post-cast cooldown correction. Its learned mechanic aura uses `SPELL_AURA_ADD_PCT_MODIFIER = -30%`, `SPELLMOD_COOLDOWN`, and an exact base-family mask. Glyph additions use a separate conditional aura and a unique otherwise-unused Rogue family marker, so Blade Flurry cannot accidentally match Ghostly Strike.
- Learning Preparation changes the calculated base cooldown and client tooltip immediately; it does not recalculate a cooldown that was already running before the talent was learned.

## Integration points

- `PlayerScript`: persistence and event-driven spell synchronization.
- `CommandScript`: the `.cultivation` root router and the RBAC-protected `rogue` subsystem commands.
- `SpellScript`/`AuraScript`: exact cast, hit, periodic, absorb, apply, and remove semantics.
- `AllSpellScript` and `UnitScript`: cross-cutting cost/damage/threat/aura behavior and GUID-scoped state.
- A single universal spell-cost hook is permitted only if the audited core has no equivalent hook.

## Cultivation namespace migration

- The module boundary is `mod-cultivation`; `rogue` is its first class subsystem under `src/rogue`.
- The public command is a native nested command tree: `.cultivation rogue <action>`. Manual token splitting in a root handler is forbidden because the command framework consumes hierarchy tokens before dispatch.
- Schema 6 preserves existing choices and suppressed action slots by renaming the two characters tables. It also migrates RBAC, world command metadata, and every active ScriptName.
- The legacy `.roguepath` name exists only in versioned migration/rollback history and is never registered by active C++.

## Negative scenarios

- Non-rogues, under-level characters, dead players, teleporting players, and disallowed combat/BG/arena states cannot change paths.
- Invalid or incomplete generated data prevents synchronization before any standard spell is removed.
- A missing technical spell disables the module with a precise validation error instead of leaving a mixed spellbook.
- Relog, restart, dual-spec changes, failed hits, multiple rogues on one target, and path switching during cooldown must not duplicate effects or reset cooldowns.
- A server-only remainder, `SMSG_MODIFY_COOLDOWN`, warmed spell cache, or correct tooltip only after the first talent learn cannot satisfy a pre-cast/base-cooldown requirement.
- AddOn/TalentUI hooks are not an allowed substitute for a native gameplay record when the requested scope is game files. A new Lua/FrameXML error, duplicate description, signed Blizzard UI `Corrupted` status, or different 0/1 and 1/1 descriptions blocks the candidate.

## Root-cause and repeated-failure protocol

- Before editing, restate the request as one observable invariant and an explicit `before -> action -> after` transition.
- Identify the authoritative layer before choosing an implementation: DBC/native modifier for client-visible base mechanics, server code for authoritative gameplay, and FrameXML only for presentation the stock UI does not render.
- Test a fresh client state before the first talent learn; then learn, cast, reset, relearn, and relog. A warmed cache is a separate state, not a valid substitute.
- After the second report of the same symptom, mark the candidate and architecture failed. Do not produce another variation of the same hook, AddOn, or packet until root cause and a regression that reproduces the failure exist.
- Do not claim a fix from compilation or automated tests alone. Until the exact user-visible scenario passes, report only that a candidate is installed and GUI acceptance is pending.

## Acceptance matrix

The required runtime matrix is maintained in `test_plan.md` and the per-spell compatibility matrix. A candidate is not accepted until clean build, isolated SQL migration, generated DBC semantic comparison, MPQ round-trip extraction, and the 1920x1080 borderless clone-client tests pass.

## Candidate35 confirmed causes

- `combat_potency` used `{rank}` inside an inline replacement string. The generator previously resolved placeholders only in the appended delta, so the literal token entered both the custom row and the native stock talent branch used at `0/5`. Inline replacement output now resolves the rank before replacement, and generated tests reject every unresolved token; ruRU ranks 1–5 must say 1–5 energy.
- Celestial Sprint used `RemoveAurasByType(SPELL_AURA_MOD_DECREASE_SPEED)`. Rogue Stealth has its own positive movement-speed penalty of that aura type, so the blanket cleanup removed Stealth. Sprint now removes only `MECHANIC_ROOT` and `MECHANIC_SNARE`; the real-cast regression proves Stealth remains while hostile root/snare are removed and the four-second immunity still works.

## Candidate41 Sha contract

- Player-controlled targets no longer select weaker hidden branches for Backstab, Ambush, Shadow Dance, Ghostly Strike, Shiv, Cheap Shot, Sap, Safe Fall, or Kidney Shot. The configured creature values are authoritative for every target.
- Cheap Shot and Kidney Shot use duration-bound target marks in the common incoming-damage pipeline, so the stated 10%/15% applies to every attacker and every supported damage path.
- Gouge ignores the caster's poison damage and periodic bleeds for its whole duration; the retired 1.5-second protection aura is not part of the implementation.
- Evasion has native 120-second cooldown metadata and returns 5 energy on every real dodge with no one-second gate. Sprint has only its 100%/8-second benefit and no post-expiry slow.
- Backstab retains the stock 60-energy cost and uses one +30% direct modifier plus a 1.20 final critical multiplier for every target. Shadowstep changes only the positional requirement for three seconds.
- Ambush has an intentional non-stock 75-energy DBC cost, +35% direct damage, and a 1.20 final critical multiplier. The changed cost must be path-colored in the generated tooltip.
- Expose Armor owns a native 35% armor-reduction value. Cheap Shot lasts 3 seconds, Blind 5 seconds, and Sap 6 seconds for both creatures and players; Sap costs 65, accepts an in-combat target, awards +2 combo points, and gates the same target for 10 seconds.
- Deadly Throw schedules blades at 0/1/2 seconds. Vanish applies a four-tick 10-energy periodic aura. The two Stealth Mastery display records use the user-supplied center art with separate Celestial/Sha grades.
- Installed test configuration is part of the candidate. It must be regenerated from the current `.conf.dist`; obsolete overrides are rejected before launch.

## Candidate48 Celestial Stealth Mastery frame correction

- Candidate47's unframed SpellIcon 6196 was rejected by GUI acceptance.
- `celestial_stealth_mastery` now uses the same Celestial framed SpellIcon 6192 / `ability_rogue_surpriseattack2_celestial` as its display passive. The exact `Мастерство незаметности` / `Stealth Mastery` name and all gameplay fields remain unchanged.
- `celestial_shiv_protection` keeps candidate47's accepted stock `Ability_Creature_Poison_06` mapping.
- Candidate48 startup validation reports zero disabled replacement groups and no new server errors versus the candidate47 baseline; GUI frame acceptance remains pending.

## Candidate47 Celestial technical-aura presentation (GUI-rejected icon choice)

- Gameplay and all candidate46 mechanics remain unchanged.
- `celestial_shiv_protection` now copies stock spell 31226 / SpellIcon 1960, resolving to `Interface\\Icons\\Ability_Creature_Poison_06`.
- `celestial_stealth_mastery` was named correctly, but its unframed SpellIcon 6196 was rejected in GUI; candidate48 replaces it with the Celestial framed icon 6192.
- Candidate47 native protocol result: 40 checks passed, 0 failed. GUI aura acceptance remains pending.

## Candidate46 Sha mechanics and aura icons

- `SpellIconID` keeps the path-framed spellbook/talent art. `ActiveIconID` of every active Celestial/Sha variant points to the exact stock base-rank icon, so its buff/debuff is standard while its AuraDescription remains path-correct.
- Visible technical auras copy the standard `icon_source_spell` presentation. The approved exceptions are shared vulnerability icon 6194 for Dismantle/Cheap Shot/Kidney Shot marks, Blood Thrill icon 6195, and the unframed Stealth Mastery aura icon 6196. Stealth Mastery resources are named `ability_rogue_surpriseattack2`, `ability_rogue_surpriseattack2_celestial` and `ability_rogue_surpriseattack2_sha`.
- Sha Sap has both DBC stance masks cleared and no server `HasStealthAura` gate. Sha Ghostly Strike keeps haste on the rogue and applies the armor reduction to the struck target. Master Poisoner starts its window only on the first own Deadly Poison application.
- Sha Seal Fate uses 20/40/60/80/100% by learned rank with a two-second empowered-proc interval. Overkill is only +100% energy regeneration for 8 seconds. Cheat Death restores 60 energy in two one-second ticks and grants +25% damage for the two-second protection window.
- Candidate46 native protocol result: 40 checks passed, 0 failed. GUI acceptance remains pending.
## Seal Fate rollback candidate

Небожительская «Печать судьбы» снова сохраняет стандартное срабатывание и превращает каждый потерянный приём серии сверх максимума 5 в 5 энергии, но не более 10 энергии в секунду. Восстановлена прежняя стандартная иконка Seal Fate для всех пяти display-only рангов; временная привязка к `INV_Qiraj_JewelGlyphed` и SpellIcon row 6192 удалены. Путь Ша не изменён.
