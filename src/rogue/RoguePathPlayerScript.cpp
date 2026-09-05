// Match Boost.Asio's existing Windows 7 target explicitly for this translation unit.
#if defined(_WIN32) && !defined(_WIN32_WINNT)
#define _WIN32_WINNT 0x0601
#endif
#include "CultivationRogue.h"
#include "RoguePathMechanics.h"

#include "GameTime.h"
#include "Log.h"
#include "ObjectAccessor.h"
#include "Player.h"
#include "PlayerScript.h"
#include "SpellAuras.h"
#include "SpellMgr.h"
#include "Timer.h"
#include "Unit.h"
#include "WorldScript.h"
#include "WorldSession.h"
#include "generated/RoguePathGeneratedSpells.h"

#include <algorithm>

namespace Cultivation::Rogue
{
class RoguePathWorldScript : public WorldScript
{
public:
    RoguePathWorldScript() : WorldScript("RoguePathWorldScript") { }

    void OnAfterConfigLoad(bool /*reload*/) override
    {
        LoadConfig();
    }

    void OnStartup() override
    {
        std::string error;
        bool valid = GetConfig().enable && sCultivationRogueSpellService.ValidateMappings(error);
        SetDataValid(valid);
        if (valid)
            LOG_INFO("module", "mod-cultivation: startup validation completed; disabled replacement groups={}", sCultivationRogueSpellService.DisabledGroupCount());
        else if (GetConfig().enable)
            LOG_ERROR("module", "mod-cultivation: startup validation failed: {}. Spell synchronization is disabled.", error);
    }
};

class RoguePathPlayerScript : public PlayerScript
{
public:
    RoguePathPlayerScript() : PlayerScript("RoguePathPlayerScript") { }

    void OnPlayerLogin(Player* player) override
    {
        sCultivationRogueSpellService.LoadPath(player);
        if (IsDataValid())
            sCultivationRogueSpellService.SyncPlayerSpells(player);
    }

    void OnPlayerLogout(Player* player) override
    {
        Mechanics::CleanupSevenEffects(player);
        Mechanics::EraseRuntimeState(player);
        sCultivationRogueSpellService.ForgetPlayer(player);
    }

    void OnPlayerUpdate(Player* player, uint32) override
    {
        if (!player || !player->IsClass(CLASS_ROGUE, CLASS_CONTEXT_ABILITY))
            return;
        RoguePath path = sCultivationRogueSpellService.GetPath(player);
        Mechanics::SyncCelestialPreparationGlyph(player);

        uint32 now = getMSTime();
        Mechanics::PlayerRuntimeState& state = Mechanics::GetRuntimeState(player);
        bool hasHonor = path == RoguePath::Celestial &&
            (Mechanics::HasPathPassiveRank(player, 51698) || Mechanics::HasPathPassiveRank(player, 51700) || Mechanics::HasPathPassiveRank(player, 51701));
        if (!hasHonor)
        {
            if (state.honorTarget) state.targets[state.honorTarget].honorReserve = 0;
            state.honorTarget = state.pendingHonorTarget = 0;
            state.pendingHonorPoints = 0;
        }
        if (path == RoguePath::None)
            return;
        // Dismantle's haste belongs to attacks against this rogue's disarmed
        // victim, not to a global six-second haste window on unrelated targets.
        Unit* victim = player->GetVictim();
        bool dismantleTarget = path == RoguePath::Sha && victim && victim->IsAlive() &&
            victim->HasAura(Generated::ShaDismantleMark, player->GetGUID());
        if (dismantleTarget && !player->HasAura(Generated::ShaDismantleHaste))
            player->CastSpell(player, Generated::ShaDismantleHaste, true);
        else if (!dismantleTarget)
            player->RemoveAurasDueToSpell(Generated::ShaDismantleHaste);
        uint32 stealth = sCultivationRogueSpellService.GetVariantSpell(1784, path);
        bool stealthed = player->HasAura(stealth) || player->HasStealthAura();
        if (stealthed && !state.wasStealthed)
            state.stealthStartedAt = now;
        if (stealthed && path == RoguePath::Celestial && state.stealthStartedAt &&
            getMSTimeDiff(state.stealthStartedAt, now) >= 3000 && !player->HasAura(Generated::CelestialStealthMastery))
            player->CastSpell(player, Generated::CelestialStealthMastery, true);
        if (!stealthed && state.wasStealthed)
        {
            player->RemoveAurasDueToSpell(Generated::CelestialStealthMastery);
        }
        state.wasStealthed = stealthed;

        if (state.pendingHonorPoints)
        {
            if (Unit* target = ObjectAccessor::GetUnit(*player, ObjectGuid(state.pendingHonorTarget)))
                if (target->IsAlive() && (!player->GetSelectedUnit() || player->GetSelectedUnit() == target))
                {
                    state.restoringHonor = true;
                    player->AddComboPoints(target, state.pendingHonorPoints);
                    state.restoringHonor = false;
                }
            state.pendingHonorPoints = 0;
            state.pendingHonorTarget = 0;
        }

        if (state.pendingDiveTarget)
        {
            if (Unit* target = ObjectAccessor::GetUnit(*player, ObjectGuid(state.pendingDiveTarget)))
                if (target->IsAlive() && player->IsValidAttackTarget(target))
                    player->AddComboPoints(target, 1);
            state.pendingDiveTarget = 0;
        }

        if (path == RoguePath::Celestial && state.honorTarget)
        {
            Unit* currentTarget = player->GetComboTarget();
            uint64 currentGuid = currentTarget ? currentTarget->GetGUID().GetRawValue() : 0;
            Unit* reservedTarget = ObjectAccessor::GetUnit(*player, ObjectGuid(state.honorTarget));
            if (currentGuid != state.honorTarget || !reservedTarget || !reservedTarget->IsAlive())
            {
                state.targets[state.honorTarget].honorReserve = 0;
                state.honorTarget = currentGuid;
            }
        }

        for (auto itr = state.delayedDamage.begin(); itr != state.delayedDamage.end();)
        {
            if (int32(now - itr->dueMs) < 0)
            {
                ++itr;
                continue;
            }
            if (Unit* target = ObjectAccessor::GetUnit(*player, ObjectGuid(itr->targetGuid)))
            {
                uint32 dealt = Mechanics::DealDerivedDamage(player, target, itr->spellId, itr->damage);
                if (dealt && itr->triggerMainHandPoison)
                    player->CastItemCombatSpell(target, BASE_ATTACK, PROC_FLAG_TAKEN_SPELL_MELEE_DMG_CLASS | PROC_FLAG_TAKEN_DAMAGE,
                        PROC_EX_NORMAL_HIT, 1u << DISPEL_POISON);
                if (dealt && itr->triggerOffHandPoison)
                    player->CastItemCombatSpell(target, OFF_ATTACK, PROC_FLAG_TAKEN_SPELL_MELEE_DMG_CLASS | PROC_FLAG_TAKEN_DAMAGE,
                        PROC_EX_NORMAL_HIT, 1u << DISPEL_POISON);
            }
            itr = state.delayedDamage.erase(itr);
        }

        if (state.cheatHealTicks && now >= state.cheatHealNextTick)
        {
            uint32 amount = state.cheatHealRemaining / state.cheatHealTicks;
            if (SpellInfo const* info = sSpellMgr->GetSpellInfo(Generated::CelestialCheatDeathHeal))
            {
                HealInfo heal(player, player, amount, info, info->GetSchoolMask());
                player->HealBySpell(heal);
            }
            state.cheatHealRemaining -= amount;
            --state.cheatHealTicks;
            state.cheatHealNextTick = now + 1000;
        }

        if (state.cheatEnergyTicks && now >= state.cheatEnergyNextTick)
        {
            uint32 amount = state.cheatEnergyRemaining / state.cheatEnergyTicks;
            player->ModifyPower(POWER_ENERGY, amount);
            state.cheatEnergyRemaining -= amount;
            --state.cheatEnergyTicks;
            state.cheatEnergyNextTick = now + 1000;
        }

        if (path == RoguePath::Celestial && player->HasAura(63848))
        {
            Unit* target = state.hungerTarget ? ObjectAccessor::GetUnit(*player, ObjectGuid(state.hungerTarget)) : nullptr;
            bool hasBleed = false;
            if (target)
                for (auto const& pair : target->GetAppliedAuras())
                    if (pair.second->GetBase()->GetSpellInfo()->GetAllEffectsMechanicMask() & (1ULL << MECHANIC_BLEED))
                    {
                        hasBleed = true;
                        break;
                    }
            if (!hasBleed)
            {
                player->RemoveAurasDueToSpell(63848);
                state.hungerTarget = 0;
            }
        }

    }

    void OnPlayerLevelChanged(Player* player, uint8 /*oldLevel*/) override
    {
        Sync(player);
    }

    void OnPlayerTalentsReset(Player* player, bool /*noCost*/) override
    {
        Sync(player);
    }

    void OnPlayerAfterSpecSlotChanged(Player* player, uint8 /*newSlot*/) override
    {
        Sync(player);
    }

    bool OnPlayerBeforeLoadActionButton(Player* player, uint8, uint32& action, uint8& type) override
    {
        if (!player || !IsDataValid() || type != ACTION_BUTTON_SPELL ||
            player->GetSession()->PlayerLoading() || !player->IsClass(CLASS_ROGUE, CLASS_CONTEXT_ABILITY))
            return true;
        RoguePath path = sCultivationRogueSpellService.GetPath(player);
        if (path == RoguePath::None)
            return true;
        uint32 base = sCultivationRogueSpellService.GetBaseSpell(action);
        if (path == RoguePath::Celestial && base == 14185)
            return false;
        uint32 destination = sCultivationRogueSpellService.GetVariantSpell(base, path);
        if (destination == base && action == base)
            return true; // Not part of this module's mapping.
        action = destination;
        return player->HasSpell(action);
    }

    void OnPlayerLearnSpell(Player* player, uint32 /*spellId*/) override
    {
        Sync(player);
    }

    void OnPlayerForgotSpell(Player* player, uint32 /*spellId*/) override
    {
        Sync(player);
    }

    void OnPlayerLearnTalents(Player* player, uint32 /*talentId*/, uint32 /*talentRank*/, uint32 /*spellId*/) override
    {
        Sync(player);
    }

private:
    static void Sync(Player* player)
    {
        if (player && IsDataValid() && !sCultivationRogueSpellService.IsSyncing(player) &&
            sCultivationRogueSpellService.GetPath(player) != RoguePath::None)
            sCultivationRogueSpellService.SyncPlayerSpells(player);
    }
};

void AddRoguePathPlayerScripts()
{
    new RoguePathWorldScript();
    new RoguePathPlayerScript();
}
}
