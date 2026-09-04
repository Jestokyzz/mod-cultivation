#include "RoguePathMechanics.h"
#include "RoguePathBalanceMath.h"
#include "AllSpellScript.h"
#include "CreatureScript.h"
#include "DBCStores.h"
#include "Item.h"
#include "ObjectAccessor.h"
#include "Player.h"
#include "Spell.h"
#include "SpellAuraEffects.h"
#include "SpellAuras.h"
#include "SpellInfo.h"
#include "SpellMgr.h"
#include "SpellScript.h"
#include "SpellScriptLoader.h"
#include "ScriptedCreature.h"
#include "Timer.h"
#include "UnitScript.h"
#include "generated/RoguePathGeneratedSpells.h"

#include <algorithm>
#include <cmath>
#include <vector>

namespace Cultivation::Rogue::Mechanics
{
namespace
{
bool Ready(uint32 deadline) { return !deadline || int32(getMSTime() - deadline) >= 0; }
bool PvP(Unit const* target) { return target && target->GetCharmerOrOwnerPlayerOrPlayerItself(); }

Aura* Apply(Player* player, Unit* target, uint32 id, int32 duration, int32 amount = INT32_MIN)
{
    player->CastSpell(target, id, true);
    Aura* aura = target->GetAura(id, player->GetGUID());
    if (aura)
    {
        aura->SetMaxDuration(duration);
        aura->SetDuration(duration);
        if (amount != INT32_MIN)
            if (AuraEffect* effect = aura->GetEffect(EFFECT_0))
                effect->ChangeAmount(amount, false);
    }
    return aura;
}

bool OwnControl(Player* player, Unit* target)
{
    for (auto const& pair : target->GetAppliedAuras())
    {
        Aura const* aura = pair.second->GetBase();
        if (aura->GetCasterGUID() != player->GetGUID())
            continue;
        if (aura->HasEffectType(SPELL_AURA_MOD_STUN) || aura->HasEffectType(SPELL_AURA_MOD_FEAR) ||
            aura->HasEffectType(SPELL_AURA_MOD_CONFUSE) || aura->HasEffectType(SPELL_AURA_TRANSFORM))
            return true;
    }
    return false;
}

void SelectOpener(Player* rogue, Unit* target, CastSnapshot& snapshot)
{
    if (snapshot.openerSelected)
        return;
    snapshot.openerSelected = true;
    Config const config = GetConfig();
    auto consider = [&](uint32 id, Unit* owner, int32 pct)
    {
        if (owner->HasAura(id, rogue->GetGUID()) && BalanceMath::StrongerOpener(snapshot.openerDamagePct, pct))
        {
            snapshot.openerSpell = id;
            snapshot.openerTarget = owner == rogue ? ObjectGuid::Empty : target->GetGUID();
            snapshot.openerDamagePct = pct;
        }
    };
    consider(Generated::ShaSafeFallDive, rogue, config.shaFallPvE);
    consider(Generated::ShaShadowstepDamage, rogue, 40);
    Unit* owner = snapshot.openerSpell == Generated::ShaSafeFallDive ||
        snapshot.openerSpell == Generated::ShaShadowstepDamage ? rogue : target;
    if (Aura* aura = owner->GetAura(snapshot.openerSpell, rogue->GetGUID()))
    {
        aura->Remove();
    }
}

bool IsShivComponent(uint32 id)
{
    return id == Generated::CelestialShivHit || id == Generated::ShaShivHit || id == Generated::ShaShivSecond;
}

Spell* ParentForImpact(Spell* spell, Player* rogue)
{
    SpellInfo const* info = spell->GetSpellInfo();
    if (info->Id == Generated::CelestialFanOffhand || info->Id == Generated::ShaFanOffhand)
        return const_cast<Spell*>(GetRuntimeState(rogue).activeFanSpell);
    if (IsShivComponent(info->Id) || (info->SpellFamilyName == SPELLFAMILY_ROGUE && (info->SpellFamilyFlags[1] & 0x6)))
        return const_cast<Spell*>(GetRuntimeState(rogue).activeMutilateSpell);
    return spell->IsTriggered() ? nullptr : spell;
}

}

bool IsSevenCleanup(Player const* player)
{
    return !player || sCultivationRogueSpellService.IsSyncing(player) || GetRuntimeState(player).cleanupDepth ||
        player->IsBeingTeleported() || !player->IsInWorld();
}

void CleanupSevenEffects(Player* player)
{
    auto& state = GetRuntimeState(player);
    ++state.cleanupDepth;
    std::vector<uint64> targets;
    for (auto const& pair : state.targets)
        targets.push_back(pair.first);
    for (uint64 guid : targets)
        if (Unit* target = ObjectAccessor::GetUnit(*player, ObjectGuid(guid)))
        {
            std::vector<uint32> ids;
            for (auto const& pair : target->GetAppliedAuras())
            {
                Aura const* aura = pair.second->GetBase();
                if (aura->GetCasterGUID() == player->GetGUID() && aura->GetId() >= 86000 && aura->GetId() <= 86999 &&
                    aura->GetId() != Generated::ShaSapIcd)
                    ids.push_back(aura->GetId());
            }
            for (uint32 id : ids)
                target->RemoveAurasDueToSpell(id, player->GetGUID());
        }
    --state.cleanupDepth;
}

void ResetRuntimeForPathChange(Player* player)
{
    auto& state = GetRuntimeState(player);
    PlayerRuntimeState replacement;
    replacement.celestialFallCooldownUntil = state.celestialFallCooldownUntil;
    replacement.shaFallCooldownUntil = state.shaFallCooldownUntil;
    for (auto const& pair : state.targets)
    {
        auto& target = replacement.targets[pair.first];
        target.sapCooldownUntil = pair.second.sapCooldownUntil;
    }
    state = std::move(replacement);
}

void SyncCelestialPreparationGlyph(Player* player)
{
    if (!player)
        return;
    bool active = sCultivationRogueSpellService.GetPath(player) == RoguePath::Celestial &&
        HasPathPassiveRank(player, 14185) && player->HasAura(56819);
    if (active && !player->HasAura(Generated::CelestialPreparationGlyphCooldown))
        player->CastSpell(player, Generated::CelestialPreparationGlyphCooldown, true);
    else if (!active)
        player->RemoveAurasDueToSpell(Generated::CelestialPreparationGlyphCooldown);
}

void SevenPowerCost(Spell* spell, int32& cost)
{
    Player* rogue = spell->GetCaster()->ToPlayer();
    auto variant = FindVariant(spell->GetSpellInfo()->Id);
    if (!rogue || !variant || spell->IsTriggered() || spell->GetSpellInfo()->PowerType != POWER_ENERGY)
        return;
    Config const c = GetConfig();
    bool cel = variant->path == RoguePath::Celestial;
    auto name = variant->logicalName;
    Unit* target = spell->m_targets.GetUnitTarget();
    // Default unconditional deltas are already encoded in the generated DBC,
    // which keeps the native GameTooltip and cast validation aligned. Apply
    // only an administrator's deviation from those documented defaults here.
    if (name == "cheap_shot") cost += cel ? 10 - int32(c.celCheapCost) : 20 - int32(c.shaCheapCost);
    if (name == "backstab")
    {
        if (cel)
        {
            auto& snapshot = GetCastSnapshot(spell);
            snapshot.ownControl = target && OwnControl(rogue, target);
            if (snapshot.ownControl)
                cost -= c.celBackstabCost;
        }
        else
            cost += c.shaBackstabCost;
    }
    if (name == "sap" && !cel) cost += c.shaSapCost;
    if (name == "ghostly_strike") cost += cel ? 10 - int32(c.celGhostCost) : int32(c.shaGhostCost) - 10;
    if (name == "shiv") cost += cel ? 10 - int32(c.celShivCost) : int32(c.shaShivCost) - 15;
    // Preserve explicitly free pre-existing abilities; the new skills have the stated floors.
    if (name == "cheap_shot" || name == "backstab" || name == "sap" || name == "ghostly_strike" || name == "shiv")
        cost = BalanceMath::EnergyCost(cost, 0, (name == "cheap_shot" && !cel) ? 10 :
            ((name == "shiv" || name == "cheap_shot") && cel ? 0 : 5));
}

void SevenBeforeCast(Spell*) { }

void SevenAfterHit(Spell* spell, Unit* target, bool successful, bool dealtDamage)
{
    Player* rogue = spell->GetCaster()->ToPlayer();
    if (!rogue || !target || !successful)
        return;
    auto variant = FindVariant(spell->GetSpellInfo()->Id);
    if (!variant)
        return;
    auto& snapshot = GetCastSnapshot(spell);
    Config const c = GetConfig();
    bool cel = variant->path == RoguePath::Celestial;
    bool controlled = target->HasAura(spell->GetSpellInfo()->Id, rogue->GetGUID());
    if (variant->logicalName == "cheap_shot" && controlled)
    {
        if (cel)
            rogue->AddComboPoints(target, c.celCheapCP - 2);
        else if (Aura* control = target->GetAura(spell->GetSpellInfo()->Id, rogue->GetGUID()))
            Apply(rogue, target, Generated::ShaCheapShotMark, control->GetDuration());
    }
    if (variant->logicalName == "sap" && !cel && controlled)
    {
        auto& state = GetRuntimeState(rogue).targets[target->GetGUID().GetRawValue()];
        state.sapCooldownUntil = getMSTime() + c.shaSapICD;
        Apply(rogue, target, Generated::ShaSapIcd, c.shaSapICD);
        rogue->AddComboPoints(target, c.shaSapCP);
    }
    if (dealtDamage && variant->logicalName == "backstab" && cel)
    {
        rogue->AddComboPoints(target, c.celBackstabCP - 1);
        if (snapshot.ownControl && !snapshot.backstabRefunded)
        {
            snapshot.backstabRefunded = true;
            rogue->ModifyPower(POWER_ENERGY, c.celBackstabEnergy);
        }
    }
    if (variant->logicalName == "ghostly_strike")
    {
        if (cel)
        {
            Apply(rogue, rogue, Generated::CelestialGhostlyStrikeTracker, c.celGhostMs, c.celGhostDodge);
        }
        else
        {
            rogue->AddComboPoints(target, c.shaGhostCP - 1);
            Apply(rogue, rogue, Generated::ShaGhostlyStrikeFury, c.shaGhostMs, c.shaGhostHaste);
            if (Aura* armor = Apply(rogue, target, Generated::ShaGhostlyStrikeArmor, c.shaGhostMs, -c.shaGhostArmor))
                if (AuraEffect* effect = armor->GetEffect(EFFECT_0))
                    effect->ChangeAmount(-c.shaGhostArmor, false);
        }
    }
    if (snapshot.sevenHit && snapshot.openerSpell == Generated::ShaSafeFallDive && !snapshot.diveComboAwarded)
    {
        snapshot.diveComboAwarded = true;
        // Finishers clear CP after AfterHit; the existing post-finish restoration path owns this grant.
        if (target->IsAlive())
        {
            if (spell->GetSpellInfo()->NeedsComboPoints())
            {
                GetRuntimeState(rogue).pendingDiveTarget = target->GetGUID().GetRawValue();
            }
            else
                rogue->AddComboPoints(target, 1);
        }
    }
    rogue->RemoveAurasDueToSpell(Generated::ShaOpenerArmor);
}

void SevenAfterCast(Spell* spell)
{
    Player* rogue = spell->GetCaster()->ToPlayer();
    auto variant = FindVariant(spell->GetSpellInfo()->Id);
    if (!rogue || !variant)
        return;
    Config const c = GetConfig();
    if (variant->logicalName == "blind" && variant->path == RoguePath::Sha)
        rogue->ModifySpellCooldown(spell->GetSpellInfo()->Id, 60000 - c.shaBlindCD);
    if (variant->logicalName == "ghostly_strike" && variant->path == RoguePath::Sha)
        rogue->ModifySpellCooldown(spell->GetSpellInfo()->Id, c.shaGhostCD - 15000);
    if (variant->logicalName == "shadowstep" && variant->path == RoguePath::Sha)
        Apply(rogue, rogue, Generated::ShaShadowstepPosition, 3000);
}
}

namespace Cultivation::Rogue
{
namespace
{
using namespace Mechanics;

class RoguePathSevenAllSpellScript : public AllSpellScript
{
public:
    RoguePathSevenAllSpellScript() : AllSpellScript("RoguePathSevenAllSpellScript") { }

    void ModifyCastRange(Spell* spell, Unit*, float&, float& maximum) override
    {
        auto variant = spell ? FindVariant(spell->GetSpellInfo()->Id) : std::nullopt;
        if (!variant || variant->path != RoguePath::Celestial)
            return;
        if (variant->logicalName == "sap") maximum += 5.0f;
    }

    void BeforeDiminishing(Spell* spell, Unit* target, int32& duration, int32& limit) override
    {
        auto variant = spell ? FindVariant(spell->GetSpellInfo()->Id) : std::nullopt;
        if (!variant || variant->path != RoguePath::Celestial)
            return;
        int32 bonus = 0;
        if (variant->logicalName == "cheap_shot")
            bonus = GetConfig().celCheapDuration;
        else if (variant->logicalName == "sap")
        {
            if (PvP(target))
                bonus = 2000;
            else
            {
                duration = duration * 3 / 2;
                if (limit > 0)
                    limit = limit * 3 / 2;
            }
        }
        if (bonus)
        {
            duration += bonus;
            if (limit > 0)
                limit += bonus;
        }
    }

    void OnSpellCheckCast(Spell* spell, bool, SpellCastResult& result) override
    {
        if (!spell || result != SPELL_CAST_OK || !spell->GetCaster()->IsPlayer())
            return;
        auto variant = FindVariant(spell->GetSpellInfo()->Id);
        if (!variant)
            return;
        Player* rogue = spell->GetCaster()->ToPlayer();
        Unit* target = spell->m_targets.GetUnitTarget();
        if (variant->logicalName == "backstab" && target && target->HasInArc(float(M_PI), rogue) &&
            (variant->path != RoguePath::Sha || !rogue->HasAura(Generated::ShaShadowstepPosition)))
            result = SPELL_FAILED_NOT_BEHIND;
        if (variant->logicalName == "sap" && variant->path == RoguePath::Sha)
        {
            if (!target)
                result = SPELL_FAILED_BAD_TARGETS;
            else if (!Ready(GetRuntimeState(rogue).targets[target->GetGUID().GetRawValue()].sapCooldownUntil) ||
                target->HasAura(Generated::ShaSapIcd, rogue->GetGUID()))
                result = SPELL_FAILED_NOT_READY;
        }
    }

    void OnCalcMaxDuration(Aura const* aura, int32& duration) override
    {
        auto variant = aura ? FindVariant(aura->GetId()) : std::nullopt;
        if (!variant)
            return;
        Config const c = GetConfig();
        if (variant->logicalName == "cheap_shot" && variant->path == RoguePath::Sha)
            duration = c.shaCheapPvEMs;
        if (variant->logicalName == "blind" && variant->path == RoguePath::Sha)
            duration = c.shaBlindPvEMs;
        if (variant->logicalName == "sap" && variant->path == RoguePath::Sha)
            duration = c.shaSapPvEMs;
    }

    bool CanRemoveAuraOnDamage(Unit*, Aura const* aura, Unit* attacker, SpellInfo const*, DamageEffectType type) override
    {
        auto variant = aura ? FindVariant(aura->GetId()) : std::nullopt;
        return !(variant && variant->logicalName == "blind" && variant->path == RoguePath::Sha && type == DOT &&
            attacker && attacker->GetGUID() == aura->GetCasterGUID());
    }

    bool CanDispelAura(Unit* target, Aura const* aura, Unit*, SpellInfo const*) override
    {
        if (!target || !aura || aura->GetSpellInfo()->Dispel != DISPEL_DISEASE)
            return true;
        return !target->HasAura(Generated::CelestialShivProtection);
    }

    void BeforeFallDamage(Player* player, uint32 raw, uint32& damage) override
    {
        if (!player || player->IsInFlight() || player->GetTransport() || player->IsBeingTeleported() ||
            player->HasUnitMovementFlag(MOVEMENTFLAG_FLYING | MOVEMENTFLAG_DISABLE_GRAVITY))
            return;
        RoguePath path = sCultivationRogueSpellService.GetPath(player);
        uint32 passive = sCultivationRogueSpellService.GetVariantSpell(1860, path);
        if (path == RoguePath::None || !sCultivationRogueSpellService.IsGroupEnabled("safe_fall") || !player->HasSpell(passive))
            return;
        damage = path == RoguePath::Celestial ? 0 : BalanceMath::FallDamage(raw, GetConfig().shaFallReduction);
    }

    void AfterFallDamage(Player* player, uint32 raw, uint32) override
    {
        if (!player || !raw || !player->IsAlive() || player->IsInFlight() || player->GetTransport() ||
            player->IsBeingTeleported() || player->HasUnitMovementFlag(MOVEMENTFLAG_FLYING | MOVEMENTFLAG_DISABLE_GRAVITY))
            return;
        RoguePath path = sCultivationRogueSpellService.GetPath(player);
        if (path == RoguePath::None || !sCultivationRogueSpellService.IsGroupEnabled("safe_fall") ||
            !player->HasSpell(sCultivationRogueSpellService.GetVariantSpell(1860, path)))
            return;
        auto& state = GetRuntimeState(player);
        Config const c = GetConfig();
        if (path == RoguePath::Celestial && Ready(state.celestialFallCooldownUntil) && !player->HasAura(Generated::CelestialSafeFallIcd))
        {
            state.celestialFallCooldownUntil = getMSTime() + c.celFallICD;
            Apply(player, player, Generated::CelestialSafeFallIcd, c.celFallICD);
            Apply(player, player, Generated::CelestialSafeFallSpeed, c.celFallSpeedMs, c.celFallSpeed);
            Apply(player, player, Generated::CelestialSafeFallKnockback, c.celFallKnockMs);
        }
        if (path == RoguePath::Sha && BalanceMath::DangerousFall(raw, player->GetMaxHealth(), c.shaFallThreshold) &&
            Ready(state.shaFallCooldownUntil) && !player->HasAura(Generated::ShaSafeFallIcd))
        {
            state.shaFallCooldownUntil = getMSTime() + c.shaFallICD;
            Apply(player, player, Generated::ShaSafeFallIcd, c.shaFallICD);
            player->ModifyPower(POWER_ENERGY, c.shaFallEnergy);
            Apply(player, player, Generated::ShaSafeFallDive, c.shaFallOpenerMs);
        }
    }

    void ModifyItemCombatSpellChance(Player* rogue, Unit*, SpellInfo const* info, float& chance) override
    {
        if (rogue && info && info->SpellFamilyName == SPELLFAMILY_ROGUE && info->Dispel == DISPEL_POISON &&
            GetRuntimeState(rogue).forcingShivPoison)
            chance = 100.0f;
    }

    void ModifySpellImpactDamage(Spell* spell, Unit* target, int32& damage, bool critical) override
    {
        if (!spell || !target || damage <= 0 || IsModuleTriggered() || !spell->GetCaster()->IsPlayer())
            return;
        Player* rogue = spell->GetCaster()->ToPlayer();
        Spell* parent = ParentForImpact(spell, rogue);
        if (!parent || !rogue->IsValidAttackTarget(target) || !IsDirectAttack(parent->GetSpellInfo()))
            return;
        auto variant = FindVariant(parent->GetSpellInfo()->Id);
        if (!variant || sCultivationRogueSpellService.GetPath(rogue) != variant->path)
            return;
        auto& snapshot = GetCastSnapshot(parent);
        snapshot.sevenHit = true;
        Config const c = GetConfig();
        auto name = variant->logicalName;
        if (variant->path == RoguePath::Celestial)
        {
            if (name == "backstab") damage = damage * (100 - c.celBackstabPenalty) / 100;
            if (name == "ghostly_strike") damage = damage * (100 - c.celGhostPenalty) / 100;
            if (name == "shiv") damage = damage * (100 - c.celShivPenalty) / 100;
            return;
        }
        SelectOpener(rogue, target, snapshot);
        bool openerApplies = snapshot.openerTarget.IsEmpty() || snapshot.openerTarget == target->GetGUID();
        int32 bonus = openerApplies ? snapshot.openerDamagePct : 0;
        if (snapshot.openerSpell == Generated::ShaSafeFallDive)
            bonus = c.shaFallPvE;
        if (snapshot.stealthWindow) bonus += 10;
        if (snapshot.eviscerateExtraEnergy) bonus += snapshot.eviscerateExtraEnergy;
        if (rogue->HasAura(Generated::ShaBloodThrill)) bonus += c.shaBloodThrillDirectDamagePct;
        if (rogue->HasAura(Generated::ShaCheatDeathDamage)) bonus += 25;
        if (rogue->HasAura(Generated::ShaHungerBuff)) bonus += 12;
        if (target->HasAura(Generated::ShaKickMark, rogue->GetGUID())) bonus += 10;
        if (target->HasAura(Generated::ShaDismantleMark, rogue->GetGUID())) bonus += 15;
        if (name == "mutilate" && snapshot.deadlyPoisonStacks < 5) bonus += 20;
        if (name == "hemorrhage") bonus += 20;
        if (name == "ambush") bonus += 35;
        if (name == "backstab") bonus += c.shaBackstabPvE;
        if (name == "ghostly_strike") bonus += c.shaGhostPvE;
        if ((name == "ambush" || name == "backstab") && rogue->HasAura(sCultivationRogueSpellService.GetVariantSpell(51713, RoguePath::Sha)))
            bonus += c.shaShadowDancePvEDamagePct;
        damage = BalanceMath::DirectDamage(damage, bonus, c.shaDirectCapPvE);
        if (critical)
        {
            if (name == "ambush") damage = damage * 120 / 100;
            if (name == "backstab")
                damage = damage * (100 + c.shaBackstabCritPvE) / 100;
            if (snapshot.vanishWindow) damage = damage * 130 / 100;
            if (snapshot.coldBloodBonus) damage = damage * 140 / 100;
        }
        if (spell->GetSpellInfo()->Id == Generated::ShaShivSecond)
            damage = damage * c.shaShivSecondPct / 100;
    }
};

class RoguePathSevenUnitScript : public UnitScript
{
public:
    RoguePathSevenUnitScript() : UnitScript("RoguePathSevenUnitScript") { }

    void OnAuraApply(Unit* target, Aura* aura) override
    {
        if (!target || !aura)
            return;
        Player* rogue = aura->GetCaster() ? aura->GetCaster()->ToPlayer() : nullptr;
        if (!rogue)
            return;
        auto variant = FindVariant(aura->GetId());
        if (variant && target != rogue)
            GetRuntimeState(rogue).targets[target->GetGUID().GetRawValue()];
        if (variant && variant->logicalName == "blind")
        {
            GetRuntimeState(rogue).targets[target->GetGUID().GetRawValue()].blindStartedAt = getMSTime();
        }
        if (variant && variant->logicalName == "gouge" && variant->path == RoguePath::Celestial)
            CleanseBlindPeriodic(target);
    }

    void OnAuraRemove(Unit* target, AuraApplication* application, AuraRemoveMode mode) override
    {
        Aura* aura = application ? application->GetBase() : nullptr;
        Player* rogue = aura && aura->GetCaster() ? aura->GetCaster()->ToPlayer() : nullptr;
        if (!target || !aura || !rogue)
            return;
        auto variant = FindVariant(aura->GetId());
        if (IsSevenCleanup(rogue) || !target->IsInWorld() ||
            (variant && variant->path == RoguePath::Celestial && IsTechnicalAuraRemoval(target, rogue)) ||
            (target->IsPlayer() && target->ToPlayer()->IsBeingTeleported()))
            return;
        Config const c = GetConfig();
        if (variant && variant->logicalName == "cheap_shot" && variant->path == RoguePath::Celestial &&
            target->IsAlive() && mode != AURA_REMOVE_BY_DEATH)
            ApplyCelestialDamageSuppression(rogue, target, 15, 4000);
        if (variant && variant->logicalName == "cheap_shot" && variant->path == RoguePath::Sha)
            target->RemoveAurasDueToSpell(Generated::ShaCheapShotMark, rogue->GetGUID());
        if (variant && variant->logicalName == "blind")
        {
            auto& state = GetRuntimeState(rogue).targets[target->GetGUID().GetRawValue()];
            state.blindStartedAt = 0;
            target->RemoveAurasDueToSpell(Generated::ShaBlindStrike, rogue->GetGUID());
        }
        if (variant && variant->logicalName == "sap")
        {
            if (variant->path == RoguePath::Celestial &&
                (mode == AURA_REMOVE_BY_DEFAULT || mode == AURA_REMOVE_BY_CANCEL || mode == AURA_REMOVE_BY_ENEMY_SPELL))
            {
                Apply(rogue, target, Generated::CelestialSapGuard, 4000, -70);
                ApplyCelestialDamageSuppression(rogue, target, 20, 4000);
            }
            target->RemoveAurasDueToSpell(Generated::ShaSapStrike, rogue->GetGUID());
        }
        if (aura->GetId() == Generated::ShaShivVulnerability && rogue->IsAlive() &&
            sCultivationRogueSpellService.GetPath(rogue) == RoguePath::Sha)
            Apply(rogue, rogue, Generated::ShaShivRegenPenalty, c.shaShivPenaltyMs, -c.shaShivRegenPenalty);
    }

};

class npc_rogue_path_shadowstep_clone : public CreatureScript
{
public:
    npc_rogue_path_shadowstep_clone() : CreatureScript("npc_rogue_path_shadowstep_clone") { }

    struct npc_rogue_path_shadowstep_cloneAI : public ScriptedAI
    {
        npc_rogue_path_shadowstep_cloneAI(Creature* creature) : ScriptedAI(creature) { }
        bool attacked = false;
        void UpdateAI(uint32) override
        {
            if (attacked || !UpdateVictim())
                return;
            if (me->isAttackReady(BASE_ATTACK) && me->IsWithinMeleeRange(me->GetVictim()))
            {
                me->AttackerStateUpdate(me->GetVictim(), BASE_ATTACK);
                attacked = true;
                me->AttackStop();
            }
        }
    };

    CreatureAI* GetAI(Creature* creature) const override { return new npc_rogue_path_shadowstep_cloneAI(creature); }
};

class spell_cultivation_rogue_blind : public AuraScript
{
    PrepareAuraScript(spell_cultivation_rogue_blind);
    void CleanPeriodic(AuraEffect const*, AuraEffectHandleModes)
    {
        Player* rogue = GetCaster() ? GetCaster()->ToPlayer() : nullptr;
        if (!rogue)
            return;
        CleanseBlindPeriodic(GetTarget());
    }
    void Register() override
    {
        OnEffectApply += AuraEffectApplyFn(spell_cultivation_rogue_blind::CleanPeriodic, EFFECT_1, SPELL_AURA_MOD_CONFUSE, AURA_EFFECT_HANDLE_REAL);
    }
};

class spell_cultivation_rogue_ghostly_dodge : public AuraScript
{
    PrepareAuraScript(spell_cultivation_rogue_ghostly_dodge);
    bool _used = false;
    bool Check(ProcEventInfo& event)
    {
        return !_used && event.GetDamageInfo() && (event.GetHitMask() & PROC_HIT_DODGE) &&
            GetTarget()->IsPlayer() && event.GetActionTarget() == GetTarget();
    }
    void Proc(ProcEventInfo&)
    {
        PreventDefaultAction();
        _used = true;
        Player* rogue = GetTarget()->ToPlayer();
        Config const c = GetConfig();
        rogue->ModifyPower(POWER_ENERGY, c.celGhostEnergy);
    }
    void Refresh(AuraEffect const*, AuraEffectHandleModes) { _used = false; }
    void Register() override
    {
        DoCheckProc += AuraCheckProcFn(spell_cultivation_rogue_ghostly_dodge::Check);
        OnProc += AuraProcFn(spell_cultivation_rogue_ghostly_dodge::Proc);
        AfterEffectApply += AuraEffectApplyFn(spell_cultivation_rogue_ghostly_dodge::Refresh, EFFECT_0, SPELL_AURA_MOD_DODGE_PERCENT, AURA_EFFECT_HANDLE_REAL_OR_REAPPLY_MASK);
    }
};

class spell_cultivation_rogue_shiv : public SpellScript
{
    PrepareSpellScript(spell_cultivation_rogue_shiv);
    void Hit(SpellEffIndex index)
    {
        PreventHitDefaultEffect(index);
        Player* rogue = GetCaster()->ToPlayer();
        auto variant = FindVariant(GetSpellInfo()->Id);
        if (!rogue || !GetHitUnit() || !variant)
            return;
        rogue->CastSpell(GetHitUnit(), variant->path == RoguePath::Celestial ? Generated::CelestialShivHit : Generated::ShaShivHit, true);
        if (variant->path == RoguePath::Sha && GetHitUnit()->IsAlive())
            rogue->CastSpell(GetHitUnit(), Generated::ShaShivSecond, true);
    }
    void Register() override
    {
        OnEffectHitTarget += SpellEffectFn(spell_cultivation_rogue_shiv::Hit, EFFECT_0, SPELL_EFFECT_DUMMY);
    }
};

class spell_cultivation_rogue_shiv_component : public SpellScript
{
    PrepareSpellScript(spell_cultivation_rogue_shiv_component);
    bool _success = false;
    void Before(SpellMissInfo miss) { _success = miss == SPELL_MISS_NONE; }
    void After()
    {
        Player* rogue = GetCaster()->ToPlayer();
        Unit* target = GetHitUnit();
        if (!_success || !rogue || !target || GetHitDamage() <= 0 || !target->IsAlive())
            return;
        auto& runtime = GetRuntimeState(rogue);
        Spell* parent = const_cast<Spell*>(runtime.activeMutilateSpell);
        if (!parent)
            return;
        bool cel = GetSpellInfo()->Id == Generated::CelestialShivHit;
        Config const c = GetConfig();
        auto& snapshot = GetCastSnapshot(parent);
        if (!snapshot.shivComboAwarded)
        {
            snapshot.shivComboAwarded = true;
            rogue->AddComboPoints(target, 1);
        }
        if (!cel && !snapshot.shivWindowApplied)
        {
            snapshot.shivWindowApplied = true;
            Apply(rogue, target, Generated::ShaShivVulnerability, c.shaShivWindowMs);
        }
        // Exactly one guaranteed native poison attempt per successful weapon component.
        // The component DBC suppresses native item procs, preventing a duplicate attempt.
        runtime.forcingShivPoison = true;
        rogue->CastItemCombatSpell(target, OFF_ATTACK, PROC_FLAG_TAKEN_SPELL_MELEE_DMG_CLASS | PROC_FLAG_TAKEN_DAMAGE,
            PROC_EX_NORMAL_HIT, 1u << DISPEL_POISON);
        runtime.forcingShivPoison = false;
        if (cel)
            Apply(rogue, target, Generated::CelestialShivProtection, 8000);
        rogue->RemoveAurasDueToSpell(Generated::ShaOpenerArmor);
    }
    void Register() override
    {
        BeforeHit += BeforeSpellHitFn(spell_cultivation_rogue_shiv_component::Before);
        AfterHit += SpellHitFn(spell_cultivation_rogue_shiv_component::After);
    }
};
}

void AddRoguePathSevenScripts()
{
    new RoguePathSevenAllSpellScript();
    new RoguePathSevenUnitScript();
    new npc_rogue_path_shadowstep_clone();
    RegisterSpellScript(spell_cultivation_rogue_blind);
    RegisterSpellScript(spell_cultivation_rogue_ghostly_dodge);
    RegisterSpellScript(spell_cultivation_rogue_shiv);
    RegisterSpellScript(spell_cultivation_rogue_shiv_component);
}
}
