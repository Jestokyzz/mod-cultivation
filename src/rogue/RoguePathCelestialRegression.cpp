// Explicit opt-in integration harness. It can run only on the isolated v3 DB,
// localhost test port and a disposable RPTEST_ account, never a normal character.
#include "RoguePathMechanics.h"
#include "generated/RoguePathGeneratedSpells.h"
#include "AccountMgr.h"
#include "Chat.h"
#include "CharmInfo.h"
#include "Config.h"
#include "Creature.h"
#include "ObjectAccessor.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "SpellAuras.h"
#include "SpellAuraEffects.h"
#include "SpellInfo.h"
#include "SpellMgr.h"
#include "TemporarySummon.h"
#include "WorldSession.h"
#include <algorithm>
#include <cmath>
#include <memory>
#include <vector>

namespace Cultivation::Rogue::Mechanics
{
bool RunShaSinisterRegression(Player* player, ChatHandler* chat)
{
    std::string account;
    if (!player || !sConfigMgr->GetOption<bool>("Cultivation.Rogue.Celestial.TestHarness", false) ||
        sConfigMgr->GetOption<uint32>("WorldServerPort", 0) != 8099 ||
        !sConfigMgr->GetOption<std::string>("CharacterDatabaseInfo", "").ends_with(";rogue_paths_test_characters_v3") ||
        !AccountMgr::GetName(player->GetSession()->GetAccountId(), account) || !account.starts_with("RPTEST_") ||
        !player->GetName().starts_with("Rp") || player->GetLevel() != 80)
        return false;

    struct Results
    {
        uint32 attempts = 0;
        uint32 hits = 0;
        uint32 procs = 0;
        uint32 errors = 0;
        uint32 avoided = 0;
    };
    auto result = std::make_shared<Results>();
    uint32 phase = player->GetPhaseMask();
    player->CombatStop(true);
    player->SetPhaseMask(0x40000000, true);
    sCultivationRogueSpellService.SetPath(player, RoguePath::Sha);
    player->learnSpell(48638, false, false);
    sCultivationRogueSpellService.SyncPlayerSpells(player);
    player->EquipNewItem((INVENTORY_SLOT_BAG_0 << 8) | EQUIPMENT_SLOT_MAINHAND, 2092, true);
    player->m_modMeleeHitChance = player->m_modSpellHitChance = 100.0f;
    player->SetFloatValue(PLAYER_EXPERTISE, 100.0f);
    player->SetFloatValue(PLAYER_CRIT_PERCENTAGE, 0.0f);
    TempSummon* target = player->SummonCreature(38, player->GetPositionX() + 2.0f,
        player->GetPositionY(), player->GetPositionZ(), 0, TEMPSUMMON_TIMED_DESPAWN, 30000);
    if (!target)
    {
        player->SetPhaseMask(phase, true);
        return false;
    }
    target->SetReactState(REACT_PASSIVE);
    target->SetFaction(14);
    target->SetPhaseMask(player->GetPhaseMask(), false);
    target->SetLevel(80);
    target->SetMaxHealth(1000000);
    target->SetFullHealth();
    target->SetArmor(0);
    player->SetSelection(target->GetGUID());
    player->SetFacingToObject(target);
    ObjectGuid owner = player->GetGUID();
    ObjectGuid victim = target->GetGUID();
    chat->PSendSysMessage("RPSS|START|2000|86274|{}", uint32(Generated::ShaSinisterExtraAttack));

    // Short batches preserve normal world updates and the delayed-damage queue.
    // These are real non-triggered casts, not a synthetic RNG simulation.
    for (uint32 batch = 0; batch < 125; ++batch)
        player->m_Events.AddEventAtOffset([owner, victim, result]()
        {
            Player* p = ObjectAccessor::FindPlayer(owner);
            Creature* enemy = p ? ObjectAccessor::GetCreature(*p, victim) : nullptr;
            if (!p || !enemy || sCultivationRogueSpellService.GetPath(p) != RoguePath::Sha)
            {
                ++result->errors;
                return;
            }
            for (uint32 index = 0; index < 20 && result->hits < 2000; ++index)
            {
                auto& state = GetRuntimeState(p);
                std::size_t before = state.delayedDamage.size();
                p->AttackStop();
                p->ClearComboPoints();
                p->SetPower(POWER_ENERGY, p->GetMaxPower(POWER_ENERGY));
                p->RemoveSpellCooldown(86274);
                p->GetGlobalCooldownMgr().CancelGlobalCooldown(sSpellMgr->GetSpellInfo(86274));
                enemy->SetFullHealth();
                ++result->attempts;
                SpellCastResult status = p->CastSpell(enemy, 86274, false);
                p->AttackStop();
                if (status != SPELL_CAST_OK)
                {
                    ++result->errors;
                    continue;
                }
                if (enemy->GetHealth() == enemy->GetMaxHealth())
                {
                    ++result->avoided;
                    if (state.delayedDamage.size() != before) ++result->errors;
                    continue;
                }
                ++result->hits;
                std::size_t added = state.delayedDamage.size() - before;
                if (added > 1) ++result->errors;
                for (std::size_t n = before; n < state.delayedDamage.size(); ++n)
                {
                    if (state.delayedDamage[n].spellId != Generated::ShaSinisterExtraAttack)
                        ++result->errors;
                    else
                        ++result->procs;
                }
            }
        }, Milliseconds(100 + batch * 100));

    player->m_Events.AddEventAtOffset([owner, victim, phase, result]()
    {
        Player* p = ObjectAccessor::FindPlayer(owner);
        if (!p) return;
        // Six-sigma envelope for Binomial(2000, .20); reject the 10% hypothesis
        // without redefining a random 20% proc as a deterministic every-fifth hit.
        bool ok = result->hits == 2000 && result->attempts == result->hits + result->avoided && !result->errors &&
            result->procs >= 292 && result->procs <= 508 && GetRuntimeState(p).delayedDamage.empty();
        ChatHandler(p->GetSession()).PSendSysMessage("RPSS|SUMMARY|{}|{}|{}|{}|{}",
            result->attempts, result->hits, result->procs, result->errors, ok ? "PASS" : "FAIL");
        if (Creature* enemy = ObjectAccessor::GetCreature(*p, victim)) enemy->DespawnOrUnsummon();
        p->CombatStop(true);
        p->SetPhaseMask(phase, true);
    }, Milliseconds(14000));
    return true;
}

bool RunShaCandidate41Regression(Player* player, ChatHandler* chat)
{
    std::string account;
    if (!player || !sConfigMgr->GetOption<bool>("Cultivation.Rogue.Celestial.TestHarness", false) ||
        sConfigMgr->GetOption<uint32>("WorldServerPort", 0) != 8099 ||
        !sConfigMgr->GetOption<std::string>("CharacterDatabaseInfo", "").ends_with(";rogue_paths_test_characters_v3") ||
        !AccountMgr::GetName(player->GetSession()->GetAccountId(), account) || !account.starts_with("RPTEST_") ||
        !player->GetName().starts_with("Rp") || player->GetLevel() != 80)
        return false;

    uint32 passed = 0, failed = 0;
    auto check = [&](char const* name, bool ok, int64 actual = 0, int64 expected = 0)
    {
        if (ok) ++passed; else ++failed;
        chat->PSendSysMessage("RPS41|{}|{}|{}|{}", name, ok ? "PASS" : "FAIL", actual, expected);
    };
    Config const c = GetConfig();
    check("config-backstab-cost-stock", c.shaBackstabCost == 0, c.shaBackstabCost, 0);
    check("config-backstab-direct-all-targets", c.shaBackstabPvE == 30, c.shaBackstabPvE, 30);
    check("config-backstab-final-crit", c.shaBackstabCritPvE == 20, c.shaBackstabCritPvE, 20);
    check("config-cheap-all-source", c.shaCheapPvE == 10, c.shaCheapPvE, 10);
    check("config-kidney-all-source", c.shaKidneyPvEDamagePct == 15, c.shaKidneyPvEDamagePct, 15);
    check("config-sap-target-cooldown", c.shaSapICD == 10000, c.shaSapICD, 10000);

    auto spell = [](uint32 id) { return sSpellMgr->GetSpellInfo(id); };
    SpellInfo const* sprint = spell(86206);
    SpellInfo const* evasion = spell(86208);
    SpellInfo const* backstab = spell(86321);
    SpellInfo const* ambush = spell(86294);
    SpellInfo const* expose = spell(86279);
    SpellInfo const* cheap = spell(86309);
    SpellInfo const* blind = spell(86322);
    SpellInfo const* sap = spell(86326);
    SpellInfo const* vanish = spell(86203);
    SpellInfo const* energy = spell(Generated::ShaVanishEnergy);
    SpellInfo const* adrenaline = spell(sCultivationRogueSpellService.GetVariantSpell(13750, RoguePath::Sha));
    SpellInfo const* preparation = spell(sCultivationRogueSpellService.GetVariantSpell(14185, RoguePath::Sha));
    SpellInfo const* shadowDance = spell(sCultivationRogueSpellService.GetVariantSpell(51713, RoguePath::Sha));
    SpellInfo const* ghostly = spell(sCultivationRogueSpellService.GetVariantSpell(14278, RoguePath::Sha));
    SpellInfo const* overkill = spell(Generated::ShaOverkillBonus);
    SpellInfo const* adrenalinePenalty = spell(Generated::ShaAdrenalinePenalty);
    SpellInfo const* ghostlyArmor = spell(Generated::ShaGhostlyStrikeArmor);
    SpellInfo const* cheatDamage = spell(Generated::ShaCheatDeathDamage);
    check("sprint-native-duration-8", sprint && sprint->GetDuration() == 8000, sprint ? sprint->GetDuration() : -1, 8000);
    check("evasion-native-cooldown-120", evasion && evasion->RecoveryTime == 120000, evasion ? evasion->RecoveryTime : -1, 120000);
    check("evasion-native-duration-8", evasion && evasion->GetDuration() == 8000, evasion ? evasion->GetDuration() : -1, 8000);
    check("backstab-native-stock-cost-60", backstab && backstab->ManaCost == 60, backstab ? backstab->ManaCost : -1, 60);
    check("ambush-native-cost-75", ambush && ambush->ManaCost == 75, ambush ? ambush->ManaCost : -1, 75);
    int32 exposeArmor = expose ? expose->Effects[EFFECT_0].CalcValue(player) : 0;
    check("expose-native-armor-minus-35", expose && exposeArmor == -35, exposeArmor, -35);
    check("cheap-native-duration-3", cheap && cheap->GetDuration() == 3000, cheap ? cheap->GetDuration() : -1, 3000);
    check("blind-native-duration-5", blind && blind->GetDuration() == 5000, blind ? blind->GetDuration() : -1, 5000);
    check("sap-native-cost-65", sap && sap->ManaCost == 65, sap ? sap->ManaCost : -1, 65);
    check("sap-native-duration-6", sap && sap->GetDuration() == 6000, sap ? sap->GetDuration() : -1, 6000);
    check("sap-native-cooldown-10", sap && sap->RecoveryTime == 10000, sap ? sap->RecoveryTime : -1, 10000);
    check("sap-no-stealth-stance", sap && !sap->Stances && !sap->StancesNot,
        sap ? int64(sap->Stances) : -1, 0);
    check("adrenaline-native-duration-10", adrenaline && adrenaline->GetDuration() == 10000,
        adrenaline ? adrenaline->GetDuration() : -1, 10000);
    check("adrenaline-penalty-duration-4", adrenalinePenalty && adrenalinePenalty->GetDuration() == 4000,
        adrenalinePenalty ? adrenalinePenalty->GetDuration() : -1, 4000);
    int32 preparationCooldown = preparation ? std::max(preparation->RecoveryTime, preparation->CategoryRecoveryTime) : 0;
    check("preparation-native-cooldown-390", preparation && preparationCooldown == 390000,
        preparationCooldown, 390000);
    check("shadow-dance-native-duration-5", shadowDance && shadowDance->GetDuration() == 5000,
        shadowDance ? shadowDance->GetDuration() : -1, 5000);
    check("ghostly-native-cost-25", ghostly && ghostly->ManaCost == 25,
        ghostly ? ghostly->ManaCost : -1, 25);
    check("overkill-native-duration-8", overkill && overkill->GetDuration() == 8000,
        overkill ? overkill->GetDuration() : -1, 8000);
    check("ghostly-target-armor-minus-20", ghostlyArmor &&
        ghostlyArmor->Effects[EFFECT_0].ApplyAuraName == SPELL_AURA_MOD_RESISTANCE_PCT &&
        ghostlyArmor->Effects[EFFECT_0].CalcValue(player) == -20,
        ghostlyArmor ? ghostlyArmor->Effects[EFFECT_0].CalcValue(player) : 0, -20);
    check("cheat-damage-25-for-2", cheatDamage && cheatDamage->GetDuration() == 2000 &&
        cheatDamage->Effects[EFFECT_0].CalcValue(player) == 25,
        cheatDamage ? cheatDamage->Effects[EFFECT_0].CalcValue(player) : 0, 25);
    int32 vanishCooldown = vanish ? std::max(vanish->RecoveryTime, vanish->CategoryRecoveryTime) : 0;
    check("vanish-native-cooldown-visible", vanish && vanishCooldown == 135000, vanishCooldown, 135000);
    check("vanish-energy-four-seconds", energy && energy->GetDuration() == 4000, energy ? energy->GetDuration() : -1, 4000);
    check("vanish-energy-one-second-ticks", energy && energy->Effects[EFFECT_0].Amplitude == 1000,
        energy ? energy->Effects[EFFECT_0].Amplitude : 0, 1000);
    int32 energyPerTick = energy ? energy->Effects[EFFECT_0].CalcValue(player) : 0;
    check("vanish-energy-ten-per-tick", energy && energyPerTick == 10, energyPerTick, 10);

    uint32 phase = player->GetPhaseMask();
    player->SetPhaseMask(0x40000000, true);
    TempSummon* target = player->SummonCreature(38, player->GetPositionX() + 2.0f,
        player->GetPositionY(), player->GetPositionZ(), 0, TEMPSUMMON_TIMED_DESPAWN, 15000);
    TempSummon* ally = player->SummonCreature(38, player->GetPositionX() + 3.0f,
        player->GetPositionY(), player->GetPositionZ(), 0, TEMPSUMMON_TIMED_DESPAWN, 15000);
    check("fixture-created", target && ally);
    if (target && ally)
    {
        target->SetPhaseMask(player->GetPhaseMask(), false);
        ally->SetPhaseMask(player->GetPhaseMask(), false);
        target->SetFaction(14);
        ally->SetFaction(player->GetFaction());
        if (Aura* mark = player->AddAura(Generated::ShaCheapShotMark, target))
        {
            uint32 melee = 1000;
            int32 direct = 1000;
            uint32 periodic = 1000;
            sScriptMgr->ModifyMeleeDamage(target, ally, melee);
            sScriptMgr->ModifySpellDamageTaken(target, ally, direct, spell(133));
            sScriptMgr->ModifyPeriodicDamageAurasTick(target, ally, periodic, spell(12654));
            sScriptMgr->ModifyPeriodicCombatDamage(target, ally, periodic, spell(12654));
            check("cheap-all-source-melee-110", melee == 1100, melee, 1100);
            check("cheap-all-source-spell-110", direct == 1100, direct, 1100);
            check("cheap-all-source-periodic-110", periodic == 1100, periodic, 1100);
            mark->Remove();
        }
        else check("cheap-mark-applied", false);
        if (Aura* mark = player->AddAura(Generated::ShaKidneyMark, target))
        {
            uint32 melee = 1000;
            int32 direct = 1000;
            uint32 periodic = 1000;
            sScriptMgr->ModifyMeleeDamage(target, ally, melee);
            sScriptMgr->ModifySpellDamageTaken(target, ally, direct, spell(133));
            sScriptMgr->ModifyPeriodicDamageAurasTick(target, ally, periodic, spell(12654));
            sScriptMgr->ModifyPeriodicCombatDamage(target, ally, periodic, spell(12654));
            check("kidney-all-source-melee-115", melee == 1150, melee, 1150);
            check("kidney-all-source-spell-115", direct == 1150, direct, 1150);
            check("kidney-all-source-periodic-115", periodic == 1150, periodic, 1150);
            mark->Remove();
        }
        else check("kidney-mark-applied", false);
        if (Aura* gouge = player->AddAura(86219, target))
        {
            bool ownPoisonBreaks = sScriptMgr->CanRemoveAuraOnDamage(target, gouge, player, spell(2818), DOT);
            bool ownBleedBreaks = sScriptMgr->CanRemoveAuraOnDamage(target, gouge, player, spell(1943), DOT);
            bool otherDamageBreaks = sScriptMgr->CanRemoveAuraOnDamage(target, gouge, ally, spell(133), DIRECT_DAMAGE);
            check("gouge-own-poison-does-not-break", !ownPoisonBreaks, ownPoisonBreaks, 0);
            check("gouge-own-bleed-does-not-break", !ownBleedBreaks, ownBleedBreaks, 0);
            check("gouge-other-direct-damage-breaks", otherDamageBreaks, otherDamageBreaks, 1);
            gouge->Remove();
        }
        else check("gouge-aura-applied", false);
    }
    if (target) target->DespawnOrUnsummon();
    if (ally) ally->DespawnOrUnsummon();
    player->SetPhaseMask(phase, true);
    chat->PSendSysMessage("RPS41|SUMMARY|{}|{}", passed, failed);
    return true;
}

bool RunCelestialResourceRegression(Player* player, ChatHandler* chat)
{
    std::string account;
    if (!player || !sConfigMgr->GetOption<bool>("Cultivation.Rogue.Celestial.TestHarness", false) ||
        sConfigMgr->GetOption<uint32>("WorldServerPort", 0) != 8099 ||
        !sConfigMgr->GetOption<std::string>("CharacterDatabaseInfo", "").ends_with(";rogue_paths_test_characters_v3") ||
        !AccountMgr::GetName(player->GetSession()->GetAccountId(), account) || !account.starts_with("RPTEST_") ||
        !player->GetName().starts_with("Rp") || player->GetLevel() != 80)
        return false;
    struct Results { uint32 passed = 0; uint32 failed = 0; };
    auto result = std::make_shared<Results>();
    ObjectGuid owner = player->GetGUID();
    auto check = [owner, result](char const* name, bool ok, int64 actual = 0, int64 expected = 0)
    {
        if (ok) ++result->passed; else ++result->failed;
        if (Player* current = ObjectAccessor::FindPlayer(owner))
            ChatHandler(current->GetSession()).PSendSysMessage("RPCT|{}|{}|{}|{}", name, ok ? "PASS" : "FAIL", actual, expected);
    };
    uint32 phase = player->GetPhaseMask();
    player->SetPhaseMask(0x40000000, true);
    player->CombatStop(true);
    sCultivationRogueSpellService.SetPath(player, RoguePath::Celestial);
    TempSummon* enemy = player->SummonCreature(38, player->GetPositionX() + 2.0f,
        player->GetPositionY(), player->GetPositionZ(), 0, TEMPSUMMON_TIMED_DESPAWN, 45000);
    if (!enemy) return false;
    enemy->SetReactState(REACT_PASSIVE);
    enemy->SetFaction(14);
    enemy->SetPhaseMask(player->GetPhaseMask(), false);
    enemy->SetMaxHealth(1000000);
    enemy->SetFullHealth();
    player->SetFacingToObject(enemy);
    player->SetSelection(enemy->GetGUID());
    player->m_modMeleeHitChance = player->m_modSpellHitChance = 100.0f;
    player->SetFloatValue(PLAYER_EXPERTISE, 100.0f);
    player->SetFloatValue(PLAYER_OFFHAND_EXPERTISE, 100.0f);
    player->learnSpell(674, false, false);
    player->EquipNewItem((INVENTORY_SLOT_BAG_0 << 8) | EQUIPMENT_SLOT_MAINHAND, 2092, true);
    player->EquipNewItem((INVENTORY_SLOT_BAG_0 << 8) | EQUIPMENT_SLOT_OFFHAND, 2092, true);
    auto cast = [&](Unit* target, uint32 id, bool triggered = false)
    {
        player->RemoveSpellCooldown(id);
        player->GetGlobalCooldownMgr().CancelGlobalCooldown(sSpellMgr->GetSpellInfo(id));
        player->AttackStop();
        return player->CastSpell(target, id, triggered);
    };
    // Real talent-learning lifecycle: never force AddAura to hide a missing passive.
    for (uint8 rank = 1; rank <= 5; ++rank)
    {
        player->LearnTalent(1825, rank - 1, true);
        uint32 id = 86408 + rank;
        check("potency-learned-real-aura", player->HasSpell(id) && player->HasAura(id), id, id);
        auto swing = [&](WeaponAttackType hand) -> int32
        {
            for (uint32 attempt = 0; attempt < 100; ++attempt)
            {
                CalcDamageInfo hit;
                player->CalculateMeleeDamage(enemy, &hit, hand);
                if (hit.hitOutCome != MELEE_HIT_NORMAL) continue;
                player->SetPower(POWER_ENERGY, 0);
                player->SendAttackStateUpdate(&hit);
                player->DealMeleeDamage(&hit, false);
                DamageInfo damage(hit);
                Unit::ProcSkillsAndAuras(player, enemy, hit.procAttacker, hit.procVictim,
                    damage.GetHitMask(), damage.GetDamage(), hand, nullptr, nullptr, -1, nullptr, &damage);
                return player->GetPower(POWER_ENERGY);
            }
            return int32(-1);
        };
        int32 energy = swing(OFF_ATTACK);
        check("potency-offhand-rank-energy", energy == rank, energy, rank);
        energy = swing(BASE_ATTACK);
        check("potency-no-mainhand-energy", energy == 0, energy, 0);
    }
    // Stop its bonus interfering with Mutilate's accounting.
    for (uint32 id = 86409; id <= 86413; ++id) player->RemoveAurasDueToSpell(id);
    player->LearnTalent(1719, 0, true);
    for (uint32 id = 86409; id <= 86413; ++id) player->RemoveAurasDueToSpell(id);
    auto mutilate = [&](uint8 stacks)
    {
        enemy->RemoveAurasDueToSpell(2818);
        if (stacks)
            if (Aura* poison = player->AddAura(2818, enemy)) poison->SetStackAmount(stacks);
        player->SetPower(POWER_ENERGY, 100);
        SpellCastResult status = cast(enemy, 86051);
        check("mutilate-real-cast", status == SPELL_CAST_OK, status, SPELL_CAST_OK);
        player->AttackStop();
        return player->GetPower(POWER_ENERGY);
    };
    int32 ordinary = mutilate(4);
    int32 refunded = mutilate(5);
    check("mutilate-five-doses-one-refund", refunded - ordinary == 10, refunded - ordinary, 10);
    player->SetPower(POWER_ENERGY, 59);
    check("mutilate-requires-full-upfront-energy", cast(enemy, 86051) == SPELL_FAILED_NO_POWER);
    enemy->RemoveAurasDueToSpell(2818);
    player->LearnTalent(2078, 2, true);
    player->ClearComboPoints();
    player->AddComboPoints(enemy, 5);
    player->AddComboPoints(enemy, 3);
    auto& state = GetRuntimeState(player);
    check("honor-native-overflow-cap-two", state.targets[enemy->GetGUID().GetRawValue()].honorReserve == 2);
    // A real finisher must spend 5 before the queued reserve is returned.
    player->SetPower(POWER_ENERGY, 100);
    player->learnSpell(2098, false, false);
    uint32 eviscerate = sCultivationRogueSpellService.GetVariantSpell(2098, RoguePath::Celestial);
    check("honor-finisher-real-cast", cast(enemy, eviscerate) == SPELL_CAST_OK);
    player->AttackStop();
    ObjectGuid victim = enemy->GetGUID();
    player->m_Events.AddEventAtOffset([owner, victim, phase, check, result]()
    {
        Player* current = ObjectAccessor::FindPlayer(owner);
        Creature* target = current ? ObjectAccessor::GetCreature(*current, victim) : nullptr;
        if (!current || !target) return;
        check("honor-return-after-native-finisher", current->GetComboPoints(target) == 2, current->GetComboPoints(target), 2);
        GetRuntimeState(current).targets[victim.GetRawValue()].honorReserve = 0;
        current->ClearComboPoints();
        current->LearnTalent(381, 0, true);
        current->CombatStop(true);
        current->AddAura(86000, current);
        current->RemoveSpellCooldown(86108);
        current->GetGlobalCooldownMgr().CancelGlobalCooldown(sSpellMgr->GetSpellInfo(86108));
        SpellCastResult premed = current->CastSpell(target, 86108, false);
        check("premed-real-cast", premed == SPELL_CAST_OK, premed, SPELL_CAST_OK);
        Aura* retain = current->GetAura(86108);
        check("premed-native-duration-30", retain && retain->GetDuration() == 30000);
        check("premed-grants-three", current->GetComboPoints(target) == 3, current->GetComboPoints(target), 3);
        check("premed-no-module-second-timer", !GetRuntimeState(current).premeditationExpiresAt);
        current->m_Events.AddEventAtOffset([owner, victim, check]()
        {
            Player* p = ObjectAccessor::FindPlayer(owner);
            if (p) check("premed-survives-stock-20-second-deadline", p->GetComboPoints() == 3 && p->GetComboTargetGUID() == victim, p->GetComboPoints(), 3);
        }, Milliseconds(21000));
        current->m_Events.AddEventAtOffset([owner, victim, phase, check, result]()
        {
            Player* p = ObjectAccessor::FindPlayer(owner);
            if (!p) return;
            check("premed-expires-at-30-seconds", p->GetComboPoints() == 0 && !p->HasAura(86108), p->GetComboPoints(), 0);
            if (Creature* target = ObjectAccessor::GetCreature(*p, victim)) target->DespawnOrUnsummon();
            p->CombatStop(true);
            p->SetPhaseMask(phase, true);
            ChatHandler(p->GetSession()).PSendSysMessage("RPCT|SUMMARY|{}|{}", result->passed, result->failed);
        }, Milliseconds(31000));
    }, Milliseconds(250));
    return true;
}

bool RunCelestialRegression(Player* player, ChatHandler* chat)
{
    std::string account;
    if (!player || !sConfigMgr->GetOption<bool>("Cultivation.Rogue.Celestial.TestHarness", false) ||
        sConfigMgr->GetOption<uint32>("WorldServerPort", 0) != 8099 ||
        !sConfigMgr->GetOption<std::string>("CharacterDatabaseInfo", "").ends_with(";rogue_paths_test_characters_v3") ||
        !AccountMgr::GetName(player->GetSession()->GetAccountId(), account) || !account.starts_with("RPTEST_") ||
        !player->GetName().starts_with("Rp") || player->GetLevel() != 80)
        return false;

    uint32 passed = 0, failed = 0;
    auto check = [&](char const* name, bool ok, int64 actual = 0, int64 expected = 0)
    {
        if (ok) ++passed; else ++failed;
        chat->PSendSysMessage("RPCT|{}|{}|{}|{}", name, ok ? "PASS" : "FAIL", actual, expected);
    };
    uint32 oldPhase = player->GetPhaseMask();
    uint32 oldMax = player->GetMaxHealth();
    player->SetPhaseMask(0x40000000, true);
    player->SetMaxHealth(1000000);
    player->SetFullHealth();
    player->CombatStop(true);
    player->m_modMeleeHitChance = player->m_modSpellHitChance = 100.0f;
    player->SetFloatValue(PLAYER_EXPERTISE, 100.0f);
    player->SetFloatValue(PLAYER_OFFHAND_EXPERTISE, 100.0f);
    sCultivationRogueSpellService.SetPath(player, RoguePath::Celestial);
    std::vector<TempSummon*> fixtures;
    auto spawnOffset = [&](float offsetX, float offsetY, uint32 faction) -> TempSummon*
    {
        TempSummon* unit = player->SummonCreature(38, player->GetPositionX() + offsetX,
            player->GetPositionY() + offsetY, player->GetPositionZ(), 0, TEMPSUMMON_TIMED_DESPAWN, 60000);
        if (unit)
        {
            unit->SetReactState(REACT_PASSIVE);
            unit->SetFaction(faction);
            unit->SetPhaseMask(player->GetPhaseMask(), false);
            unit->SetLevel(80);
            unit->SetMaxHealth(1000000);
            unit->SetFullHealth();
            unit->SetArmor(0);
            fixtures.push_back(unit);
        }
        return unit;
    };
    auto spawn = [&](float distance, uint32 faction = 14) -> TempSummon*
    {
        return spawnOffset(distance, 0.0f, faction);
    };
    auto clearSuppression = [&](Unit* target)
    {
        target->RemoveAurasDueToSpell(Generated::CelestialDamageSuppression20);
        target->RemoveAurasDueToSpell(Generated::CelestialDamageSuppression15);
    };
    auto cast = [&](Unit* target, uint32 id, bool triggered = true)
    {
        player->RemoveSpellCooldown(id);
        player->GetGlobalCooldownMgr().CancelGlobalCooldown(sSpellMgr->GetSpellInfo(id));
        return player->CastSpell(target, id, triggered);
    };
    TempSummon* enemy = spawn(2.0f);
    TempSummon* victim = spawn(4.0f, 35);
    if (!enemy || !victim)
    {
        check("fixture-creation", false);
    }
    else
    {
        ApplyCelestialDamageSuppression(player, enemy, 15, 4000);
        Aura* weak = enemy->GetAura(Generated::CelestialDamageSuppression15);
        check("weak-real-aura", weak && weak->GetDuration() == 4000);
        ApplyCelestialDamageSuppression(player, enemy, 15, 1000);
        check("equal-short-preserves-long", weak && weak->GetDuration() == 4000);
        ApplyCelestialDamageSuppression(player, enemy, 20, 6000);
        Aura* strong = enemy->GetAura(Generated::CelestialDamageSuppression20);
        check("strong-replaces-weak", strong && !enemy->HasAura(Generated::CelestialDamageSuppression15));
        ApplyCelestialDamageSuppression(player, enemy, 15, 10000);
        check("weak-cannot-refresh-strong", strong && strong->GetDuration() == 6000 && !enemy->HasAura(Generated::CelestialDamageSuppression15));
        ApplyCelestialDamageSuppression(player, enemy, 20, 4000);
        check("strong-short-preserves-long", strong && strong->GetDuration() == 6000);
        if (strong) strong->SetDuration(1000);
        ApplyCelestialDamageSuppression(player, enemy, 20, 4000);
        check("equal-refresh-max", strong && strong->GetDuration() == 4000);

        // Controlled inputs through the actual damage/absorb/log/health pipeline.
        auto direct = [&](Unit* source, Unit* destination, uint32 id)
        {
            SpellInfo const* info = sSpellMgr->GetSpellInfo(id);
            SpellNonMeleeDamage damage(source, destination, info, info->GetSchoolMask());
            destination->SetFullHealth();
            source->CalculateSpellDamageTaken(&damage, 1000, info, BASE_ATTACK, false);
            source->SendSpellNonMeleeDamageLog(&damage);
            source->DealSpellDamage(&damage, false);
            return destination->GetMaxHealth() - destination->GetHealth();
        };
        for (uint32 spell : {1752u, 133u, 75u})
        {
            clearSuppression(enemy);
            uint32 baseline = direct(enemy, victim, spell);
            ApplyCelestialDamageSuppression(player, enemy, 20, 6000);
            uint32 actual = direct(enemy, victim, spell);
            check(spell == 1752 ? "physical-direct-global-20" : spell == 75 ? "ranged-damage-global-20" : "magic-direct-global-20",
                baseline && std::abs(int(actual) - int(baseline * 80 / 100)) <= 1, actual, baseline * 80 / 100);
            clearSuppression(enemy);
            ApplyCelestialDamageSuppression(player, enemy, 15, 4000);
            actual = direct(enemy, victim, spell);
            check(spell == 1752 ? "physical-direct-global-15" : spell == 75 ? "ranged-damage-global-15" : "magic-direct-global-15",
                baseline && std::abs(int(actual) - int(baseline * 85 / 100)) <= 1, actual, baseline * 85 / 100);
        }
        clearSuppression(enemy);
        enemy->SetFloatValue(UNIT_FIELD_MINDAMAGE, 1000.0f);
        enemy->SetFloatValue(UNIT_FIELD_MAXDAMAGE, 1000.0f);
        auto melee = [&]() -> uint32
        {
            for (uint32 attempt = 0; attempt < 100; ++attempt)
            {
                CalcDamageInfo info;
                enemy->CalculateMeleeDamage(victim, &info, BASE_ATTACK);
                if (info.hitOutCome != MELEE_HIT_NORMAL) continue;
                victim->SetFullHealth();
                enemy->SendAttackStateUpdate(&info);
                enemy->DealMeleeDamage(&info, false);
                return victim->GetMaxHealth() - victim->GetHealth();
            }
            return 0;
        };
        uint32 meleeBase = melee();
        ApplyCelestialDamageSuppression(player, enemy, 20, 6000);
        uint32 meleeReduced = melee();
        check("melee-native-health-global-20", meleeBase && std::abs(int(meleeReduced)-int(meleeBase*80/100)) <= 1, meleeReduced, meleeBase*80/100);
        clearSuppression(enemy);
        for (uint32 spell : {703u, 172u})
        {
            Aura* dot = enemy->AddAura(spell, victim);
            AuraEffect* effect = dot ? dot->GetEffect(EFFECT_0) : nullptr;
            auto tick = [&]() -> uint32
            {
                victim->SetFullHealth();
                if (effect) effect->PeriodicTick(dot->GetApplicationOfTarget(victim->GetGUID()), enemy);
                return victim->GetMaxHealth() - victim->GetHealth();
            };
            uint32 baseline = tick();
            ApplyCelestialDamageSuppression(player, enemy, 20, 6000);
            uint32 actual = tick();
            check(spell == 703 ? "existing-physical-dot-20" : "existing-magic-dot-20",
                baseline && std::abs(int(actual)-int(baseline*80/100)) <= 1, actual, baseline*80/100);
            victim->RemoveAurasDueToSpell(spell);
            dot = enemy->AddAura(spell, victim);
            effect = dot ? dot->GetEffect(EFFECT_0) : nullptr;
            actual = tick();
            check(spell == 703 ? "new-physical-dot-20" : "new-magic-dot-20",
                baseline && std::abs(int(actual)-int(baseline*80/100)) <= 1, actual, baseline*80/100);
            victim->RemoveAurasDueToSpell(spell);
            clearSuppression(enemy);
        }

        // Native AoE avoidance entry and actual aura, no separate cosmetic buff.
        player->SetPower(POWER_ENERGY, 100);
        SpellCastResult feintResult = cast(enemy, 86017, false);
        check("feint-native-target-cast-cost-20", feintResult == SPELL_CAST_OK && player->GetPower(POWER_ENERGY) == 80, player->GetPower(POWER_ENERGY), 80);
        Aura* feint = player->GetAura(Generated::CelestialFeintGuard);
        check("feint-duration-8s", feint && feint->GetDuration() == 8000);
        check("feint-native-aoe-70", player->CalculateAOEDamageReduction(1000, SPELL_SCHOOL_MASK_FIRE, true) == 300);
        uint32 singleWithFeint = direct(enemy, player, 133);
        player->RemoveAurasDueToSpell(Generated::CelestialFeintGuard);
        check("feint-single-target-unchanged", singleWithFeint == direct(enemy, player, 133));

        enemy->AddAura(339, player);
        enemy->AddAura(1715, player);
        Aura* stealthBeforeSprint = player->AddAura(86000, player);
        check("sprint-stealth-fixture", stealthBeforeSprint && player->HasAura(86000));
        check("sprint-variant-owned", player->HasSpell(86006));
        check("preparation-live-transition-before-unlearned", !player->HasTalent(14185, player->GetActiveSpec()) &&
            !player->HasSpell(86107) && !player->HasSpell(86621));
        SpellCastResult sprintBeforeResult = cast(player, 86006, false);
        uint32 sprintBeforeDelay = player->GetSpellCooldownDelay(86006);
        SpellInfo const* sprintInfo = sSpellMgr->GetSpellInfo(86006);
        uint32 fullSprintDelay = sprintInfo ? uint32(std::max(sprintInfo->RecoveryTime, sprintInfo->CategoryRecoveryTime)) : 0;
        check("preparation-live-transition-sprint-before-180s", fullSprintDelay == 180000 &&
            sprintBeforeResult == SPELL_CAST_OK && sprintBeforeDelay <= fullSprintDelay &&
            sprintBeforeDelay + 1000 >= fullSprintDelay, sprintBeforeDelay, 180000);
        check("sprint-preserves-stealth", sprintBeforeResult == SPELL_CAST_OK && player->HasAura(86000));
        check("sprint-before-preparation-cleans-root-slow", sprintBeforeResult == SPELL_CAST_OK &&
            !player->HasAura(339) && !player->HasAura(1715));
        player->RemoveAurasDueToSpell(86000);

        player->RemoveAurasDueToSpell(Generated::CelestialSprintImmunity);
        player->RemoveSpellCooldown(86006, true);
        player->GetGlobalCooldownMgr().CancelGlobalCooldown(sprintInfo);
        player->LearnTalent(284, 0, true);
        check("preparation-live-transition-learned", player->HasTalent(14185, player->GetActiveSpec()) &&
            player->HasSpell(86107) && player->HasAura(86107) && player->HasSpell(86621));
        enemy->AddAura(339, player);
        enemy->AddAura(1715, player);
        player->SetPower(POWER_ENERGY, 100);
        SpellCastResult sprintResult = cast(player, 86006, false);
        uint32 sprintDelay = player->GetSpellCooldownDelay(86006);
        uint32 expectedSprintDelay = fullSprintDelay * 70 / 100;
        check("preparation-live-transition-sprint-after-126s", expectedSprintDelay == 126000 &&
            sprintResult == SPELL_CAST_OK && sprintDelay <= expectedSprintDelay &&
            sprintDelay + 1000 >= expectedSprintDelay, sprintDelay, 126000);
        check("sprint-cleans-root-slow", sprintResult == SPELL_CAST_OK &&
            !player->HasAura(339) && !player->HasAura(1715));
        Aura* freedom = player->GetAura(Generated::CelestialSprintImmunity);
        check("sprint-immunity-duration", freedom && freedom->GetDuration() == 4000);
        enemy->CastSpell(player, 339, true);
        enemy->CastSpell(player, 1715, true);
        check("sprint-rejects-new-root-slow", !player->HasAura(339) && !player->HasAura(1715));
        if (freedom) freedom->Remove(AURA_REMOVE_BY_EXPIRE);
        enemy->AddAura(339, player);
        enemy->AddAura(1715, player);
        check("sprint-after-expiration-vulnerable", player->HasAura(339) && player->HasAura(1715));
        CleanseCelestialVanish(player);

        uint32 physical = direct(enemy, player, 1752);
        uint32 magic = direct(enemy, player, 133);
        cast(player, 86008);
        Aura* evasion = player->GetAura(86008);
        check("evasion-base-duration", evasion && evasion->GetDuration() == 20000);
        uint32 reduced = direct(enemy, player, 1752);
        check("evasion-physical-15", std::abs(int(reduced)-int(physical*85/100)) <= 1, reduced, physical*85/100);
        check("evasion-magic-unchanged", direct(enemy, player, 133) == magic);
        player->RemoveAurasDueToSpell(86008);
        player->AddAura(56799, player); // stock Glyph of Evasion, verified from local Spell.dbc
        cast(player, 86008);
        evasion = player->GetAura(86008);
        check("evasion-glyph-duration", evasion && evasion->GetDuration() == 25000, evasion ? evasion->GetDuration() : -1, 25000);
        player->RemoveAurasDueToSpell(86008);
        player->RemoveAurasDueToSpell(56799);

        // Real casts with two equipped daggers, deterministic hit/expertise.
        // Only disposable RPTEST fixtures may receive these items/stat changes.
        player->CombatStop(true);
        player->SetCanDualWield(true);
        player->DestroyItem(INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_MAINHAND, true);
        player->DestroyItem(INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_OFFHAND, true);
        player->EquipNewItem((INVENTORY_SLOT_BAG_0 << 8) | EQUIPMENT_SLOT_MAINHAND, 2092, true);
        player->EquipNewItem((INVENTORY_SLOT_BAG_0 << 8) | EQUIPMENT_SLOT_OFFHAND, 2092, true);
        player->SetSkill(SKILL_DAGGERS, 0, 400, 400);
        player->m_modMeleeHitChance = player->m_modSpellHitChance = 100.0f;
        player->SetFloatValue(PLAYER_EXPERTISE, 100.0f);
        player->SetFloatValue(PLAYER_OFFHAND_EXPERTISE, 100.0f);

        bool learnedBackstabForFixture = !player->HasSpell(86121);
        if (learnedBackstabForFixture)
            player->learnSpell(86121, false, false);
        player->CombatStop(true);
        player->ClearComboPoints();
        player->SetFacingToObject(enemy);
        enemy->SetFullHealth();
        player->SetPower(POWER_ENERGY, 100);
        SpellCastResult plainBackstab = cast(enemy, 86121, false);
        check("backstab-no-control-cost-60", plainBackstab == SPELL_CAST_OK &&
            player->GetPower(POWER_ENERGY) == 40, player->GetPower(POWER_ENERGY), 40);

        player->CombatStop(true);
        player->ClearComboPoints();
        player->SetFacingToObject(enemy);
        enemy->SetFullHealth();
        Aura* ownGouge = player->AddAura(1776, enemy);
        player->SetPower(POWER_ENERGY, 100);
        SpellCastResult controlledBackstab = cast(enemy, 86121, false);
        check("backstab-own-control-cost-50-refund-10", ownGouge && controlledBackstab == SPELL_CAST_OK &&
            player->GetPower(POWER_ENERGY) == 60, player->GetPower(POWER_ENERGY), 60);
        enemy->RemoveAurasDueToSpell(1776, player->GetGUID());
        if (learnedBackstabForFixture)
            player->removeSpell(86121, SPEC_MASK_ALL, false);

        // Fan has native missile travel time. Its assertions run asynchronously
        // below, after normal world updates, not immediately after CastSpell.
        clearSuppression(enemy);
        player->ClearComboPoints();
        player->SetFacingToObject(enemy);
        player->AddAura(1784, player);
        player->SetPower(POWER_ENERGY, 100);
        SpellCastResult ambushResult = cast(enemy, 86094, false);
        check("ambush-normal-cast", ambushResult == SPELL_CAST_OK, ambushResult, SPELL_CAST_OK);
        check("ambush-native-plus-one-cp", player->GetComboPoints() == 3, player->GetComboPoints(), 3);
        check("ambush-no-retired-suppression", !enemy->HasAura(Generated::CelestialDamageSuppression20));
        clearSuppression(enemy);
        player->ClearComboPoints();
        enemy->ApplySpellImmune(0, IMMUNITY_DAMAGE, SPELL_SCHOOL_MASK_NORMAL, true);
        player->AddAura(1784, player);
        player->SetPower(POWER_ENERGY, 100);
        cast(enemy, 86094, false);
        uint8 immuneCustomCombo = player->GetComboPoints();
        bool immuneCustomDebuff = enemy->HasAura(Generated::CelestialDamageSuppression20);
        player->ClearComboPoints();
        player->AddAura(1784, player);
        player->SetPower(POWER_ENERGY, 100);
        cast(enemy, 48691, false);
        check("ambush-immune-no-extra-vs-stock", immuneCustomCombo == player->GetComboPoints() && !immuneCustomDebuff,
            immuneCustomCombo, player->GetComboPoints());
        enemy->ApplySpellImmune(0, IMMUNITY_DAMAGE, SPELL_SCHOOL_MASK_NORMAL, false);
        player->RemoveAurasByType(SPELL_AURA_MOD_STEALTH);

        TempSummon* rangedAmbush = spawn(7.0f);
        // Spell range is measured edge-to-edge and includes both units'
        // combat reach, so ten centre-to-centre yards is not reliably outside
        // an eight-yard spell range for this creature fixture.
        TempSummon* outsideAmbush = spawn(15.0f);
        if (rangedAmbush && outsideAmbush)
        {
            player->CombatStop(true);
            player->SetFacingToObject(rangedAmbush);
            player->AddAura(1784, player);
            player->SetPower(POWER_ENERGY, 100);
            SpellCastResult rangedResult = cast(rangedAmbush, 86094, false);
            check("ambush-eight-yard-real-cast", rangedResult == SPELL_CAST_OK, rangedResult, SPELL_CAST_OK);
            player->CombatStop(true);
            player->SetFacingToObject(outsideAmbush);
            player->AddAura(1784, player);
            player->SetPower(POWER_ENERGY, 100);
            SpellCastResult outsideResult = cast(outsideAmbush, 86094, false);
            check("ambush-outside-range-rejected", outsideResult == SPELL_FAILED_OUT_OF_RANGE,
                outsideResult, SPELL_FAILED_OUT_OF_RANGE);
            player->RemoveAurasByType(SPELL_AURA_MOD_STEALTH);
        }

        for (uint8 combo = 1; combo <= 5; ++combo)
        {
            TempSummon* kidneyTarget = spawnOffset(0.0f, 3.0f, 14);
            if (!kidneyTarget)
            {
                check("kidney-stock-rank-duration-before-dr", false, combo, combo + 1);
                continue;
            }
            player->CombatStop(true);
            player->ClearComboPoints();
            // This fixture validates combo-point duration, not melee avoidance.
            // A controlled target cannot randomly dodge/parry an otherwise valid cast.
            kidneyTarget->AddUnitState(UNIT_STATE_STUNNED);
            player->AddComboPoints(kidneyTarget, combo);
            player->SetPower(POWER_ENERGY, 100);
            player->SetFacingToObject(kidneyTarget);
            SpellCastResult kidneyResult = cast(kidneyTarget, 86021, false);
            Aura* kidney = kidneyTarget->GetAura(86021, player->GetGUID());
            int32 expected = int32(combo + 1) * IN_MILLISECONDS;
            check("kidney-native-cast-before-dr", kidneyResult == SPELL_CAST_OK, kidneyResult, SPELL_CAST_OK);
            check("kidney-stock-rank-duration-before-dr", kidney && kidney->GetDuration() == expected,
                kidney ? kidney->GetDuration() : -1, expected);
            ++GetRuntimeState(player).cleanupDepth;
            if (kidney) kidney->Remove();
            --GetRuntimeState(player).cleanupDepth;
            fixtures.pop_back();
            kidneyTarget->DespawnOrUnsummon();
        }

        check("ghostly-real-talent-owns-mechanic", player->HasTalent(14278, player->GetActiveSpec()) &&
            player->HasSpell(86127));
        player->CombatStop(true);
        player->ClearComboPoints();
        player->SetPower(POWER_ENERGY, 100);
        float dodgeBeforeGhostly = player->GetFloatValue(PLAYER_DODGE_PERCENTAGE);
        player->SetFacingToObject(enemy);
        SpellCastResult ghostResult = cast(enemy, 86127, false);
        Aura* ghost = player->GetAura(Generated::CelestialGhostlyStrikeTracker);
        AuraEffect* ghostDodge = ghost ? ghost->GetEffect(EFFECT_0) : nullptr;
        check("ghostly-real-hit-dodge-aura", ghostResult == SPELL_CAST_OK && ghost && ghostDodge &&
            ghostDodge->GetAmount() == 30 && ghost->GetDuration() == 10000,
            ghostDodge ? ghostDodge->GetAmount() : -1, 30);
        float expectedDodgeAfterGhostly = dodgeBeforeGhostly + 30.0f;
        if (sConfigMgr->GetOption<bool>("Stats.Limits.Enable", false))
            expectedDodgeAfterGhostly = std::min(expectedDodgeAfterGhostly,
                sConfigMgr->GetOption<float>("Stats.Limits.Dodge", 95.0f));
        check("ghostly-real-player-dodge-plus-30-before-global-cap",
            std::abs(player->GetFloatValue(PLAYER_DODGE_PERCENTAGE) - expectedDodgeAfterGhostly) < 0.01f,
            int64(std::round(player->GetFloatValue(PLAYER_DODGE_PERCENTAGE) * 100)),
            int64(std::round(expectedDodgeAfterGhostly * 100)));
        check("ghostly-stock-combo-point", player->GetComboPoints() == 1, player->GetComboPoints(), 1);
        player->RemoveAurasDueToSpell(Generated::CelestialGhostlyStrikeTracker);

        for (uint32 spell : {86049u, 86109u, 86021u})
        {
            clearSuppression(enemy);
            Aura* control = player->AddAura(spell, enemy);
            check("control-no-suppression-during", control && !enemy->HasAura(Generated::CelestialDamageSuppression20) && !enemy->HasAura(Generated::CelestialDamageSuppression15));
            player->ClearComboPoints();
            if (control) control->Remove(AURA_REMOVE_BY_EXPIRE);
            uint32 debuff = spell == 86109 ? Generated::CelestialDamageSuppression15 : Generated::CelestialDamageSuppression20;
            Aura* suppression = enemy->GetAura(debuff);
            if (spell == 86049)
                check("dismantle-normal-end-weakening", suppression && suppression->GetDuration() == 6000);
            else if (spell == 86109)
                check("cheap-shot-normal-end-weakening", suppression && suppression->GetDuration() == 4000);
            else
                check("kidney-no-weakening-or-refund", !suppression && player->GetComboPoints() == 0);
            clearSuppression(enemy);
            control = player->AddAura(spell, enemy);
            ++GetRuntimeState(player).cleanupDepth;
            if (control) control->Remove();
            --GetRuntimeState(player).cleanupDepth;
            check("control-technical-no-suppression", !enemy->HasAura(Generated::CelestialDamageSuppression20) && !enemy->HasAura(Generated::CelestialDamageSuppression15));
        }

        player->SetPower(POWER_ENERGY, 0);
        Aura* blind = player->AddAura(86122, enemy);
        if (blind) blind->Remove(AURA_REMOVE_BY_EXPIRE);
        check("blind-no-energy-refund", player->GetPower(POWER_ENERGY) == 0);
        player->AddAura(703, enemy);
        victim->AddAura(172, enemy);
        victim->AddAura(702, enemy);
        blind = player->AddAura(86122, enemy);
        check("blind-clears-dot-all-casters", blind && !enemy->HasAura(703) && !enemy->HasAura(172));
        check("blind-keeps-non-dot-debuff", enemy->HasAura(702));
        ++GetRuntimeState(player).cleanupDepth;
        if (blind) blind->Remove();
        --GetRuntimeState(player).cleanupDepth;

        clearSuppression(enemy);
        Aura* sap = player->AddAura(86126, enemy);
        if (sap) sap->Remove(AURA_REMOVE_BY_EXPIRE);
        check("sap-natural-no-posteffect", sap && !enemy->HasAura(Generated::CelestialSapGuard) && !enemy->HasAura(Generated::CelestialDamageSuppression20));
        sap = player->AddAura(86126, enemy);
        if (sap) sap->Remove(AURA_REMOVE_BY_ENEMY_SPELL);
        check("sap-early-two-effects", enemy->HasAura(Generated::CelestialSapGuard) && enemy->HasAura(Generated::CelestialDamageSuppression20));
        clearSuppression(enemy);
        check("sap-slow-independent", enemy->HasAura(Generated::CelestialSapGuard));

        std::vector<uint32> removable = {172,703,2818,55078,1715,339};
        std::vector<uint32> preserved = {702,853,15487};
        CleanseCelestialVanish(player);
        player->RemoveAurasDueToSpell(Generated::CelestialSprintImmunity);
        for (uint32 spell : removable) enemy->AddAura(spell, player);
        for (uint32 spell : preserved) enemy->AddAura(spell, player);
        player->AddAura(1243, player);
        check("vanish-fixture-stunned", player->HasAura(853));
        CleanseCelestialVanish(player);
        for (uint32 spell : removable) check("vanish-periodic-root-slow-removed", !player->HasAura(spell), spell);
        for (uint32 spell : preserved) check("vanish-other-control-preserved", player->HasAura(spell), spell);
        check("vanish-positive-preserved", player->HasAura(1243) && player->HasAura(Generated::CelestialPathPassive));
        check("vanish-no-retired-protection", !player->HasAura(Generated::CelestialVanishDotProtection));

        // The control fixtures above deliberately survive Celestial Vanish.
        // Remove them before the independent real-cast cooldown check.
        for (uint32 spell : {702u, 853u, 15487u, 1243u})
            player->RemoveAurasDueToSpell(spell);

        uint32 celestialPreparation = sCultivationRogueSpellService.GetVariantSpell(14185, RoguePath::Celestial);
        check("preparation-real-talent-owns-passive", player->HasTalent(14185, player->GetActiveSpec()) &&
            player->HasSpell(celestialPreparation) && player->HasAura(celestialPreparation));
        for (uint32 base : {14177u, 36554u, 1856u, 5277u, 2983u})
        {
            uint32 custom = sCultivationRogueSpellService.GetVariantSpell(base, RoguePath::Celestial);
            SpellInfo const* info = sSpellMgr->GetSpellInfo(custom);
            int32 recovery = info ? info->RecoveryTime : 0;
            int32 category = info ? info->CategoryRecoveryTime : 0;
            int32 expectedRecovery = recovery * 70 / 100;
            int32 expectedCategory = category * 70 / 100;
            player->ApplySpellMod(custom, SPELLMOD_COOLDOWN, recovery);
            player->ApplySpellMod(custom, SPELLMOD_COOLDOWN, category);
            check("preparation-passive-base-list-70pct", info && recovery == expectedRecovery && category == expectedCategory,
                recovery, expectedRecovery);
        }
        uint32 coldBlood = sCultivationRogueSpellService.GetVariantSpell(14177, RoguePath::Celestial);
        SpellInfo const* coldBloodInfo = sSpellMgr->GetSpellInfo(coldBlood);
        player->RemoveAurasDueToSpell(coldBlood);
        player->SetPower(POWER_ENERGY, 100);
        SpellCastResult coldBloodResult = cast(player, coldBlood, false);
        uint32 coldBloodDelay = player->GetSpellCooldownDelay(coldBlood);
        uint32 expectedColdBloodDelay = coldBloodInfo ? uint32(coldBloodInfo->RecoveryTime * 70 / 100) : 0;
        check("preparation-real-cast-final-cooldown-70pct", expectedColdBloodDelay > 0 &&
            coldBloodResult == SPELL_CAST_OK && coldBloodDelay <= expectedColdBloodDelay &&
            coldBloodDelay + 1000 >= expectedColdBloodDelay, coldBloodDelay, expectedColdBloodDelay);
        uint32 delayBeforeSync = player->GetSpellCooldownDelay(coldBlood);
        sCultivationRogueSpellService.SyncPlayerSpells(player);
        uint32 delayAfterSync = player->GetSpellCooldownDelay(coldBlood);
        check("preparation-running-cooldown-unchanged", delayAfterSync <= delayBeforeSync &&
            delayAfterSync + 1000 >= delayBeforeSync, delayAfterSync, delayBeforeSync);
        player->RemoveAurasDueToSpell(coldBlood);
        player->RemoveAurasDueToSpell(56819);
        for (uint32 base : {51722u, 1766u, 13877u})
        {
            uint32 custom = sCultivationRogueSpellService.GetVariantSpell(base, RoguePath::Celestial);
            SpellInfo const* info = sSpellMgr->GetSpellInfo(custom);
            int32 recovery = info ? info->RecoveryTime : 0;
            int32 category = info ? info->CategoryRecoveryTime : 0;
            int32 originalRecovery = recovery, originalCategory = category;
            player->ApplySpellMod(custom, SPELLMOD_COOLDOWN, recovery);
            player->ApplySpellMod(custom, SPELLMOD_COOLDOWN, category);
            check("preparation-glyph-list-unchanged-without-glyph", info && recovery == originalRecovery && category == originalCategory);
        }
        player->AddAura(56819, player);
        SyncCelestialPreparationGlyph(player);
        check("preparation-glyph-native-modifier-active", player->HasAura(Generated::CelestialPreparationGlyphCooldown));
        for (uint32 base : {51722u, 1766u, 13877u})
        {
            uint32 custom = sCultivationRogueSpellService.GetVariantSpell(base, RoguePath::Celestial);
            SpellInfo const* info = sSpellMgr->GetSpellInfo(custom);
            int32 recovery = info ? info->RecoveryTime : 0;
            int32 category = info ? info->CategoryRecoveryTime : 0;
            int32 expectedRecovery = recovery * 70 / 100;
            int32 expectedCategory = category * 70 / 100;
            player->ApplySpellMod(custom, SPELLMOD_COOLDOWN, recovery);
            player->ApplySpellMod(custom, SPELLMOD_COOLDOWN, category);
            check("preparation-glyph-list-70pct", info && recovery == expectedRecovery && category == expectedCategory,
                recovery, expectedRecovery);
        }
        uint32 ghostly = sCultivationRogueSpellService.GetVariantSpell(14278, RoguePath::Celestial);
        SpellInfo const* ghostlyInfo = sSpellMgr->GetSpellInfo(ghostly);
        int32 ghostlyRecovery = ghostlyInfo ? ghostlyInfo->RecoveryTime : 0;
        int32 originalGhostlyRecovery = ghostlyRecovery;
        player->ApplySpellMod(ghostly, SPELLMOD_COOLDOWN, ghostlyRecovery);
        check("preparation-glyph-does-not-match-ghostly-strike", ghostlyInfo && ghostlyRecovery == originalGhostlyRecovery);
        player->RemoveAurasDueToSpell(56819);
        SyncCelestialPreparationGlyph(player);
        check("preparation-glyph-native-modifier-removed", !player->HasAura(Generated::CelestialPreparationGlyphCooldown));
    }
    // The corrected Vanish contract intentionally preserved these fixtures.
    // Remove them explicitly before the independent Fan of Knives phase.
    for (uint32 spell : {702u, 853u, 15487u, 1243u})
        player->RemoveAurasDueToSpell(spell);
    CleanupSevenEffects(player);
    for (TempSummon* fixture : fixtures) fixture->DespawnOrUnsummon();
    fixtures.clear();
    CleanseCelestialVanish(player);
    player->CombatStop(true);
    player->RemoveAurasByType(SPELL_AURA_MOD_STEALTH);
    auto firstTarget = spawn(2.0f);
    auto inside = spawn(11.9f);
    auto outside = spawn(12.1f);
    auto absorbed = spawn(6.0f);
    auto immune = spawn(8.0f);
    if (!firstTarget || !inside || !outside || !absorbed || !immune)
    {
        check("fan-fixtures", false);
        for (auto fixture : fixtures) fixture->DespawnOrUnsummon();
        player->SetMaxHealth(oldMax);
        player->SetFullHealth();
        player->SetPhaseMask(oldPhase, true);
        chat->PSendSysMessage("RPCT|SUMMARY|{}|{}", passed, failed);
        return true;
    }
    Aura* shield = absorbed->AddAura(17, absorbed);
    if (shield && shield->GetEffect(EFFECT_0)) shield->GetEffect(EFFECT_0)->ChangeAmount(100000);
    immune->ApplySpellImmune(0, IMMUNITY_DAMAGE, SPELL_SCHOOL_MASK_NORMAL, true);
    uint16 regenField = UNIT_FIELD_POWER_REGEN_FLAT_MODIFIER + uint16(POWER_ENERGY);
    float oldRegen = player->GetFloatValue(regenField);
    player->SetFloatValue(regenField, -10.0f); // cancel ONLY this disposable fixture's base regen during observation
    GetRuntimeState(player).celestialFanEnergyGranted = 0;
    player->SetPower(POWER_ENERGY, 100);
    SpellCastResult fanResult = cast(player, 86048, false);
    check("fan-normal-cast", fanResult == SPELL_CAST_OK, fanResult, SPELL_CAST_OK);
    std::vector<ObjectGuid> ids;
    for (auto fixture : fixtures) ids.push_back(fixture->GetGUID());
    ObjectGuid owner = player->GetGUID();
    player->m_Events.AddEventAtOffset([owner, ids, passed, failed, oldPhase, oldMax, oldRegen, regenField]() mutable
    {
        Player* current = ObjectAccessor::FindPlayer(owner);
        if (!current || !current->GetSession()) return;
        ChatHandler output(current->GetSession());
        auto checkLater = [&](char const* name, bool ok, int64 actual = 0, int64 expected = 0)
        {
            if (ok) ++passed; else ++failed;
            output.PSendSysMessage("RPCT|{}|{}|{}|{}", name, ok ? "PASS" : "FAIL", actual, expected);
        };
        std::vector<Creature*> units;
        for (ObjectGuid id : ids) units.push_back(ObjectAccessor::GetCreature(*current, id));
        if (std::all_of(units.begin(), units.end(), [](Creature* unit) { return unit != nullptr; }))
        {
            checkLater("fan-11.9-inside-after-flight", units[1]->GetHealth() < units[1]->GetMaxHealth());
            checkLater("fan-12.1-outside-after-flight", units[2]->GetHealth() == units[2]->GetMaxHealth());
            checkLater("fan-fully-absorbed-hit-no-health-loss", units[3]->GetHealth() == units[3]->GetMaxHealth());
            checkLater("fan-immune-no-health-loss", units[4]->GetHealth() == units[4]->GetMaxHealth());
            uint32 fanEnergy = GetRuntimeState(current).celestialFanEnergyGranted;
            checkLater("fan-three-unique-hits-two-hands-12-energy", fanEnergy == 12, fanEnergy, 12);
            uint32 before = current->GetPower(POWER_ENERGY);
            current->CastSpell(units[0], 2818, true);
            checkLater("fan-poison-no-extra-energy", current->GetPower(POWER_ENERGY) == before, current->GetPower(POWER_ENERGY), before);

            // Run movement last: the minimal world-protocol client does not
            // implement teleport ACK, so no later mechanic may depend on the
            // fixture player leaving the teleport-pending state.
            TempSummon* friendlyStep = current->SummonCreature(38, current->GetPositionX() + 10.0f,
                current->GetPositionY(), current->GetPositionZ(), 0, TEMPSUMMON_TIMED_DESPAWN, 5000);
            if (friendlyStep)
            {
                friendlyStep->SetReactState(REACT_PASSIVE);
                friendlyStep->SetFaction(current->GetFaction());
                friendlyStep->SetPhaseMask(current->GetPhaseMask(), false);
                current->SetFacingToObject(friendlyStep);
                current->RemoveSpellCooldown(86105);
                current->GetGlobalCooldownMgr().CancelGlobalCooldown(sSpellMgr->GetSpellInfo(86105));
                SpellCastResult stepResult = current->CastSpell(friendlyStep, 86105, false);
                Creature* clone = current->FindNearestCreature(900406, 20.0f, true);
                checkLater("shadowstep-friendly-real-cast", stepResult == SPELL_CAST_OK, stepResult, SPELL_CAST_OK);
                checkLater("shadowstep-friendly-safe-position", current->GetDistance2d(friendlyStep) < 8.0f,
                    int64(current->GetDistance2d(friendlyStep) * 100), 800);
                checkLater("shadowstep-friendly-no-origin-clone", !clone,
                    clone ? int64(clone->GetEntry()) : -1, -1);
                if (clone) clone->DespawnOrUnsummon();
                friendlyStep->DespawnOrUnsummon();
            }
            else
                checkLater("shadowstep-friendly-fixture", false);

        }
        else checkLater("fan-fixtures-survived-flight", false);
        for (auto unit : units) if (unit) unit->DespawnOrUnsummon();
        CleanupSevenEffects(current);
        current->SetFloatValue(regenField, oldRegen);
        current->CombatStop(true);
        current->SetMaxHealth(oldMax);
        current->SetFullHealth();
        current->SetPhaseMask(oldPhase, true);
        output.PSendSysMessage("RPCT|SUMMARY|{}|{}", passed, failed);
    }, Milliseconds(1500));
    return true;
}
}
