#include "RoguePathMechanics.h"

#include "AllSpellScript.h"
#include "GameTime.h"
#include "DBCStores.h"
#include "Item.h"
#include "Log.h"
#include "ObjectAccessor.h"
#include "Player.h"
#include "Spell.h"
#include "SpellAuraEffects.h"
#include "SpellAuras.h"
#include "SpellInfo.h"
#include "SpellMgr.h"
#include "SpellScript.h"
#include "SpellScriptLoader.h"
#include "ScriptMgr.h"
#include "Timer.h"
#include "UnitScript.h"
#include "WorldSession.h"
#include "generated/RoguePathGeneratedSpells.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <unordered_map>
#include <unordered_set>

namespace Cultivation::Rogue::Mechanics
{
namespace
{
std::unordered_map<Spell const*, CastSnapshot> CastSnapshots;
std::unordered_map<uint32, PlayerRuntimeState> RuntimeStates;
// Map updates can run on different map-worker threads. Container access is
// locked; a player's contents remain owned by its serialized map/session flow.
std::mutex RuntimeMutex;
std::mutex SnapshotMutex;
thread_local uint32 ModuleTriggeredDepth = 0;
thread_local uint32 TechnicalAuraRemovalDepth = 0;

}

std::optional<VariantInfo> FindVariant(uint32 spellId)
{
    if (spellId == Generated::CelestialFanOffhand)
        return VariantInfo{ "fan_of_knives_offhand", RoguePath::Celestial, 52874 };
    if (spellId == Generated::ShaFanOffhand)
        return VariantInfo{ "fan_of_knives_offhand", RoguePath::Sha, 52874 };
    for (Generated::SpellVariantRow const& row : Generated::SpellVariants)
    {
        if (spellId == row.celestialSpell)
            return VariantInfo{ row.logicalName, RoguePath::Celestial, row.baseSpell };
        if (spellId == row.shaSpell)
            return VariantInfo{ row.logicalName, RoguePath::Sha, row.baseSpell };
    }
    return std::nullopt;
}

bool IsDirectAttack(SpellInfo const* spellInfo)
{
    if (!spellInfo || spellInfo->IsPassive() || spellInfo->SpellFamilyName != SPELLFAMILY_ROGUE || spellInfo->Dispel == DISPEL_POISON)
        return false;
    if (spellInfo->Id == 5938)
        return true; // Shiv spends its resource on a parent which triggers 5940.
    if (auto variant = FindVariant(spellInfo->Id); variant &&
        (variant->logicalName == "mutilate" || variant->logicalName == "shiv"))
        return true; // The parent triggers two separate weapon-damage spells.
    for (SpellEffectInfo const& effect : spellInfo->Effects)
        if (effect.Effect == SPELL_EFFECT_SCHOOL_DAMAGE || effect.Effect == SPELL_EFFECT_WEAPON_DAMAGE ||
            effect.Effect == SPELL_EFFECT_WEAPON_DAMAGE_NOSCHOOL || effect.Effect == SPELL_EFFECT_NORMALIZED_WEAPON_DMG ||
            effect.Effect == SPELL_EFFECT_WEAPON_PERCENT_DAMAGE)
            return true;
    return false;
}

bool IsCriticalForTarget(Spell* spell, Unit const* target)
{
    if (!spell || !target)
        return false;
    for (TargetInfo const& info : *spell->GetUniqueTargetInfo())
        if (info.targetGUID == target->GetGUID())
            return info.crit;
    return false;
}

bool IsPeriodicDamage(SpellInfo const* info)
{
    return info && (info->HasAura(SPELL_AURA_PERIODIC_DAMAGE) || info->HasAura(SPELL_AURA_PERIODIC_DAMAGE_PERCENT) ||
        info->HasAura(SPELL_AURA_PERIODIC_LEECH));
}

bool IsTechnicalAuraRemoval(Unit const* target, Player const* caster)
{
    auto unavailable = [](Unit const* unit)
    {
        if (!unit || !unit->IsAlive() || !unit->IsInWorld() || unit->IsDuringRemoveFromWorld())
            return true;
        Player const* player = unit->ToPlayer();
        return player && (player->IsBeingTeleported() || player->GetSession()->PlayerLogout() ||
            player->isBeingLoaded() || sCultivationRogueSpellService.IsSyncing(player) ||
            GetRuntimeState(player).cleanupDepth);
    };
    return TechnicalAuraRemovalDepth || unavailable(target) || unavailable(caster);
}

void ApplyCelestialDamageSuppression(Player* rogue, Unit* target, uint8 strength, int32 duration)
{
    if (!rogue || !target || IsTechnicalAuraRemoval(target, rogue) ||
        sCultivationRogueSpellService.GetPath(rogue) != RoguePath::Celestial || duration <= 0 ||
        (strength != 15 && strength != 20))
        return;
    uint32 incoming = strength == 20 ? Generated::CelestialDamageSuppression20 : Generated::CelestialDamageSuppression15;
    Aura* strong = target->GetAura(Generated::CelestialDamageSuppression20);
    Aura* weak = target->GetAura(Generated::CelestialDamageSuppression15);
    if (strong && strength == 15)
        return; // discarded, never queued and never refreshed by a weaker source
    Aura* current = strength == 20 ? strong : weak;
    if (current)
    {
        int32 remaining = std::max(current->GetDuration(), duration);
        current->SetMaxDuration(std::max(current->GetMaxDuration(), remaining));
        current->SetDuration(remaining);
        return;
    }
    if (weak)
    {
        ++TechnicalAuraRemovalDepth;
        target->RemoveAurasDueToSpell(Generated::CelestialDamageSuppression15);
        --TechnicalAuraRemovalDepth;
    }
    rogue->CastSpell(target, incoming, true);
    if (Aura* applied = target->GetAura(incoming, rogue->GetGUID()))
    {
        applied->SetMaxDuration(duration);
        applied->SetDuration(duration);
        GetRuntimeState(rogue).targets[target->GetGUID().GetRawValue()];
    }
}

namespace
{
void RemoveNegativeAuras(Unit* target, bool vanishCleanse)
{
    // Keep application identity: removing by spell ID would also remove another
    // caster's positive application. Removal callbacks can invalidate iterators.
    std::vector<std::pair<uint32, ObjectGuid>> applications;
    for (auto const& pair : target->GetAppliedAuras())
    {
        Aura const* aura = pair.second->GetBase();
        SpellInfo const* info = aura->GetSpellInfo();
        bool selected = IsPeriodicDamage(info);
        if (vanishCleanse)
            selected = selected || info->HasAura(SPELL_AURA_MOD_DECREASE_SPEED) || info->HasAura(SPELL_AURA_MOD_ROOT) ||
                (info->GetAllEffectsMechanicMask() & ((1ULL << MECHANIC_SNARE) | (1ULL << MECHANIC_ROOT)));
        if (!pair.second->IsPositive() && selected)
            applications.emplace_back(pair.second->GetBase()->GetId(), pair.second->GetBase()->GetCasterGUID());
    }
    ++TechnicalAuraRemovalDepth;
    for (auto const& [id, caster] : applications)
        if (AuraApplication* application = target->GetAuraApplication(id, caster))
            target->RemoveAura(application, AURA_REMOVE_BY_CANCEL);
    --TechnicalAuraRemovalDepth;
}
}

void CleanseCelestialVanish(Player* player) { RemoveNegativeAuras(player, true); }
void CleanseBlindPeriodic(Unit* target) { RemoveNegativeAuras(target, false); }

void RemoveRetiredCelestialAuras(Player* player)
{
    ++TechnicalAuraRemovalDepth;
    for (uint32 id : Generated::RetiredCelestialAuras)
        player->RemoveAurasDueToSpell(id);
    auto& state = GetRuntimeState(player);
    for (auto const& pair : state.targets)
        if (Unit* target = ObjectAccessor::GetUnit(*player, ObjectGuid(pair.first)))
            for (uint32 id : Generated::RetiredCelestialAuras)
                target->RemoveAurasDueToSpell(id, player->GetGUID());
    --TechnicalAuraRemovalDepth;
}

uint8 GetOwnDeadlyPoisonStacks(Unit const* target, ObjectGuid casterGuid)
{
    if (!target)
        return 0;
    if (AuraEffect const* effect = target->GetAuraEffect(SPELL_AURA_PERIODIC_DAMAGE, SPELLFAMILY_ROGUE,
        0x10000, 0x80000, 0, casterGuid))
        return effect->GetBase()->GetStackAmount();
    return 0;
}

bool HasPathPassiveRank(Player const* player, uint32 baseSpell)
{
    if (!player)
        return false;
    uint32 custom = sCultivationRogueSpellService.GetVariantSpell(baseSpell, sCultivationRogueSpellService.GetPath(player));
    return custom != baseSpell && player->HasSpell(custom);
}

PlayerRuntimeState& GetRuntimeState(Player const* player)
{
    std::lock_guard<std::mutex> lock(RuntimeMutex);
    return RuntimeStates[player->GetGUID().GetCounter()];
}

void EraseRuntimeState(Player const* player)
{
    std::lock_guard<std::mutex> lock(RuntimeMutex);
    if (player)
        RuntimeStates.erase(player->GetGUID().GetCounter());
}

CastSnapshot& GetCastSnapshot(Spell* spell)
{
    std::lock_guard<std::mutex> lock(SnapshotMutex);
    return CastSnapshots[spell];
}

CastSnapshot const* FindCastSnapshot(Spell const* spell)
{
    std::lock_guard<std::mutex> lock(SnapshotMutex);
    auto itr = CastSnapshots.find(spell);
    return itr == CastSnapshots.end() ? nullptr : &itr->second;
}

void EraseCastSnapshot(Spell const* spell)
{
    std::lock_guard<std::mutex> lock(SnapshotMutex);
    CastSnapshots.erase(spell);
}

void TriggerBloodThrill(Player* player)
{
    if (!player || sCultivationRogueSpellService.GetPath(player) != RoguePath::Sha ||
        player->HasAura(Generated::ShaBloodThrillIcd))
        return;
    player->CastSpell(player, Generated::ShaBloodThrill, true);
    player->CastSpell(player, Generated::ShaBloodThrillIcd, true);
    if (Aura* aura = player->GetAura(Generated::ShaBloodThrill))
        if (AuraEffect* effect = aura->GetEffect(EFFECT_0))
            effect->ChangeAmount(GetConfig().shaBloodThrillEnergyRegenPct, false);
    if (Aura* aura = player->GetAura(Generated::ShaBloodThrillIcd))
    {
        aura->SetMaxDuration(GetConfig().shaBloodThrillInternalCooldownMs);
        aura->SetDuration(GetConfig().shaBloodThrillInternalCooldownMs);
    }
}

bool IsModuleTriggered() { return ModuleTriggeredDepth != 0; }
void PushModuleTriggered() { ++ModuleTriggeredDepth; }
void PopModuleTriggered() { if (ModuleTriggeredDepth) --ModuleTriggeredDepth; }

uint32 DealDerivedDamage(Player* player, Unit* target, uint32 spellId, uint32 calculatedDamage, bool applyModifiers)
{
    SpellInfo const* info = sSpellMgr->GetSpellInfo(spellId);
    if (!player || !target || !info || !calculatedDamage || !player->IsAlive() || !target->IsAlive() ||
        !player->IsValidAttackTarget(target))
        return 0;
    if (target->IsImmunedToDamage(player, info))
    {
        player->SendSpellMiss(target, spellId, SPELL_MISS_IMMUNE);
        return 0;
    }
    // Copies already contain the parent's crit/outgoing modifiers and armor.
    // Poison detonation starts from the un-ticked aura snapshot instead.
    if (applyModifiers)
    {
        int32 value = int32(std::min<uint32>(calculatedDamage, INT32_MAX));
        sScriptMgr->ModifySpellDamageTaken(target, player, value, info);
        calculatedDamage = uint32(std::max(0, value));
    }
    struct Guard
    {
        Guard() { PushModuleTriggered(); }
        ~Guard() { PopModuleTriggered(); }
    } guard;
    SpellNonMeleeDamage log(player, target, info, info->GetSchoolMask());
    DamageInfo damage(player, target, calculatedDamage, info, info->GetSchoolMask(), SPELL_DIRECT_DAMAGE);
    Unit::CalcAbsorbResist(damage);
    log.damage = damage.GetDamage();
    log.absorb = damage.GetAbsorb();
    log.resist = damage.GetResist();
    Unit::DealDamageMods(target, log.damage, &log.absorb);
    player->SendSpellNonMeleeDamageLog(&log);
    player->DealSpellDamage(&log, true);
    return log.damage;
}
}

namespace Cultivation::Rogue
{
namespace
{
using namespace Mechanics;

class TriggerGuard
{
public:
    TriggerGuard() { PushModuleTriggered(); }
    ~TriggerGuard() { PopModuleTriggered(); }
};

bool HasAuraFrom(Unit const* unit, uint32 spellId, ObjectGuid caster)
{
    return unit && unit->GetAura(spellId, caster);
}

uint32 BaseChainSpell(uint32 spellId)
{
    uint32 base = sCultivationRogueSpellService.GetBaseSpell(spellId);
    if (uint32 first = sSpellMgr->GetFirstSpellInChain(base))
        return first;
    return base;
}

std::optional<VariantInfo> GetCastVariant(Spell const* spell)
{
    if (auto variant = FindVariant(spell->GetSpellInfo()->Id))
        return variant;
    Player const* player = spell->GetCaster() ? spell->GetCaster()->ToPlayer() : nullptr;
    RoguePath path = sCultivationRogueSpellService.GetPath(player);
    if (path == RoguePath::None)
        return std::nullopt;
    return std::nullopt;
}

class RoguePathAllSpellScript : public AllSpellScript
{
public:
    RoguePathAllSpellScript() : AllSpellScript("RoguePathAllSpellScript") { }

    void ModifySpellImpactDamage(Spell* spell, Unit* target, int32& damage, bool) override
    {
        // Core calls this after final hit/damage-immunity checks and before
        // absorption. An absorbed weapon hit still counts; poison never does.
        if (!spell || !target || damage <= 0 || !spell->GetCaster()->IsPlayer())
            return;
        Player* rogue = spell->GetCaster()->ToPlayer();
        // Mutilate's parent pays the cost; its two stock weapon components
        // deliver the hits. Refund once, after a confirmed weapon impact.
        Spell const* mutilate = GetRuntimeState(rogue).activeMutilateSpell;
        if (mutilate && spell != mutilate && spell->GetSpellInfo()->SpellFamilyName == SPELLFAMILY_ROGUE &&
            (spell->GetSpellInfo()->SpellFamilyFlags[1] & 0x6))
        {
            auto parent = FindVariant(mutilate->GetSpellInfo()->Id);
            if (parent && parent->path == RoguePath::Celestial && parent->logicalName == "mutilate" &&
                FindCastSnapshot(mutilate))
            {
                CastSnapshot& snapshot = GetCastSnapshot(const_cast<Spell*>(mutilate));
                if (!snapshot.mutilateRefunded && snapshot.deadlyPoisonStacks == 5 && snapshot.targetGuid == target->GetGUID())
                {
                    snapshot.mutilateRefunded = true;
                    rogue->ModifyPower(POWER_ENERGY, 10);
                }
            }
        }
        auto variant = FindVariant(spell->GetSpellInfo()->Id);
        if (!variant || variant->path != RoguePath::Celestial)
            return;
        if (variant->logicalName == "ambush")
            GetCastSnapshot(spell).confirmedDamageTargets.insert(target->GetGUID().GetRawValue());
        if (variant->logicalName != "fan_of_knives" && variant->logicalName != "fan_of_knives_offhand")
            return;
        Spell const* parent = variant->logicalName == "fan_of_knives" ? spell : GetRuntimeState(rogue).activeFanSpell;
        if (parent && FindCastSnapshot(parent))
            if (GetCastSnapshot(const_cast<Spell*>(parent)).fanEnergyTargets.insert(target->GetGUID().GetRawValue()).second)
            {
                rogue->ModifyPower(POWER_ENERGY, 4);
                GetRuntimeState(rogue).celestialFanEnergyGranted += 4;
            }
    }

    bool CanPrepare(Spell* spell, SpellCastTargets const*, AuraEffect const*) override
    {
        if (spell && spell->GetCaster() && spell->GetCaster()->IsPlayer() &&
            (spell->GetSpellInfo()->Id == 14189 || spell->GetSpellInfo()->Id == 51699))
            GetCastSnapshot(spell).comboPoints = spell->GetCaster()->ToPlayer()->GetComboPoints();
        return true;
    }

    void OnSpellCheckCast(Spell* spell, bool, SpellCastResult& result) override
    {
        if (!spell || result != SPELL_CAST_OK || !spell->GetCaster() || !spell->GetCaster()->IsPlayer())
            return;
        Player* player = spell->GetCaster()->ToPlayer();
        uint32 baseSpell = BaseChainSpell(spell->GetSpellInfo()->Id);
        RoguePath path = sCultivationRogueSpellService.GetPath(player);
        if (baseSpell == 1833 && path == RoguePath::Sha &&
            player->HasAura(sCultivationRogueSpellService.GetVariantSpell(51713, path)))
        {
            result = SPELL_FAILED_NOT_READY;
            return;
        }

        auto variant = FindVariant(spell->GetSpellInfo()->Id);
        if (variant && variant->logicalName == "shadowstep" && variant->path == RoguePath::Sha)
        {
            Unit* target = spell->m_targets.GetUnitTarget();
            if (!target || player->IsFriendlyTo(target))
                result = SPELL_FAILED_BAD_TARGETS;
            return;
        }
        if (!variant || variant->logicalName != "hunger_for_blood")
            return;
        Unit* target = spell->m_targets.GetUnitTarget();
        if (!target || target == player)
            target = player->GetSelectedUnit();
        bool hasBleed = false;
        if (target)
        {
            for (auto const& pair : target->GetAppliedAuras())
            {
                Aura const* aura = pair.second->GetBase();
                if (aura->GetSpellInfo()->GetAllEffectsMechanicMask() & (1ULL << MECHANIC_BLEED))
                {
                    hasBleed = true;
                    break;
                }
            }
        }
        if (!hasBleed)
            result = SPELL_FAILED_TARGET_AURASTATE;
    }

    void ModifyPowerCost(Spell* spell, int32& cost) override
    {
        if (!spell || !spell->GetCaster() || !spell->GetCaster()->IsPlayer() || spell->GetSpellInfo()->IsPassive())
            return;
        Player* player = spell->GetCaster()->ToPlayer();
        RoguePath selectedPath = sCultivationRogueSpellService.GetPath(player);
        auto variant = GetCastVariant(spell);

        uint32 baseSpell = BaseChainSpell(spell->GetSpellInfo()->Id);
        bool danceAbility = baseSpell == 8676 || baseSpell == 703 || baseSpell == 53 || baseSpell == 1833;
        uint32 dance = sCultivationRogueSpellService.GetVariantSpell(51713, selectedPath);
        if (danceAbility && player->HasAura(dance))
        {
            if (selectedPath == RoguePath::Celestial && (baseSpell == 703 || baseSpell == 1833))
                cost -= 15;
            else if (selectedPath == RoguePath::Sha && (baseSpell == 8676 || baseSpell == 53))
                cost -= 20;
        }

        if (!variant)
        {
            if (selectedPath == RoguePath::Sha && spell->GetSpellInfo()->PowerType == POWER_ENERGY &&
                player->HasAura(sCultivationRogueSpellService.GetVariantSpell(13877, selectedPath)))
                cost = int32(std::ceil(float(cost) * 1.2f));
            cost = std::max<int32>(0, cost);
            return;
        }

        CastSnapshot& snapshot = GetCastSnapshot(spell);
        Unit* target = spell->m_targets.GetUnitTarget();
        snapshot.targetGuid = target ? target->GetGUID() : ObjectGuid::Empty;
        snapshot.deadlyPoisonStacks = GetOwnDeadlyPoisonStacks(target, player->GetGUID());

        bool direct = IsDirectAttack(spell->GetSpellInfo());
        PlayerRuntimeState& runtime = GetRuntimeState(player);
        bool shaStealthMasteryReady = player->HasAura(Generated::ShaStealthWindow) || player->HasStealthAura() ||
            (runtime.wasStealthed && !runtime.stealthAttackConsumed);
        if (direct && variant->path == RoguePath::Sha && shaStealthMasteryReady)
        {
            cost -= 20;
            snapshot.stealthWindow = true;
        }
        if (direct && variant->path == RoguePath::Sha && player->HasAura(Generated::ShaFeintDiscount))
        {
            cost -= 15;
            snapshot.feintDiscount = true;
        }
        if (direct && variant->path == RoguePath::Sha && player->HasAura(Generated::ShaShadowstepDamage))
            snapshot.shadowstepBonus = true;
        if (direct && variant->path == RoguePath::Sha && player->HasAura(Generated::ShaVanishWindow))
            snapshot.vanishWindow = true;
        if (direct && variant->path == RoguePath::Sha && player->HasAura(Generated::ShaColdBloodWindow))
            snapshot.coldBloodBonus = true;
        if (variant->path == RoguePath::Sha && player->HasAura(sCultivationRogueSpellService.GetVariantSpell(13877, RoguePath::Sha)))
        {
            cost = int32(std::ceil(float(cost) * 1.2f));
            snapshot.bladeFlurryCost = true;
        }
        if (variant->path == RoguePath::Sha && variant->logicalName == "eviscerate")
        {
            // Optional energy is counted after mandatory cost modifiers, so
            // Blade Flurry cannot make the selected extra amount unaffordable.
            int32 availableAfterBaseCost = std::max<int32>(0, player->GetPower(POWER_ENERGY) - std::max<int32>(0, cost));
            snapshot.eviscerateExtraEnergy = uint8(std::min<int32>(30, availableAfterBaseCost));
            cost += snapshot.eviscerateExtraEnergy;
        }
        SevenPowerCost(spell, cost);
        snapshot.powerCost = std::max<int32>(0, cost);
        cost = snapshot.powerCost;
    }

    void ModifyCritChance(Spell* spell, Unit* target, float& critChance) override
    {
        if (!spell || !target || !spell->GetCaster() || !spell->GetCaster()->IsPlayer())
            return;
        Player* player = spell->GetCaster()->ToPlayer();
        auto variant = GetCastVariant(spell);
        if (!variant && spell->GetSpellInfo()->SpellFamilyName == SPELLFAMILY_ROGUE &&
            ((spell->GetSpellInfo()->SpellFamilyFlags[1] & 0x6) || spell->GetSpellInfo()->Id == 5940 ||
                spell->GetSpellInfo()->Id == Generated::CelestialShivHit || spell->GetSpellInfo()->Id == Generated::ShaShivHit ||
                spell->GetSpellInfo()->Id == Generated::ShaShivSecond))
        {
            if (CastSnapshot const* parent = FindCastSnapshot(GetRuntimeState(player).activeMutilateSpell))
            {
                if (parent->coldBloodBonus)
                    critChance = 100.0f;
                else if (parent->celestialColdBlood)
                    critChance += 100.0f;
            }
            return;
        }
        if (!variant || !IsDirectAttack(spell->GetSpellInfo()))
            return;

        CastSnapshot& snapshot = GetCastSnapshot(spell);
        if (variant->path == RoguePath::Sha && player->HasAura(Generated::ShaColdBloodWindow))
        {
            snapshot.coldBloodBonus = true;
            critChance = 100.0f;
        }
        else if (variant->path == RoguePath::Celestial && player->HasAura(Generated::CelestialColdBloodWindow) &&
            !spell->IsTriggered() && player->IsValidAttackTarget(target))
        {
            snapshot.celestialColdBlood = true;
            critChance += 100.0f;
        }
    }

    void OnCritResult(Spell* spell, Unit*, bool critical) override
    {
        if (spell && spell->GetCaster() && spell->GetCaster()->IsPlayer() &&
            spell->GetSpellInfo()->SpellFamilyName == SPELLFAMILY_ROGUE &&
            ((spell->GetSpellInfo()->SpellFamilyFlags[1] & 0x6) || spell->GetSpellInfo()->Id == 5940 ||
                spell->GetSpellInfo()->Id == Generated::CelestialShivHit || spell->GetSpellInfo()->Id == Generated::ShaShivHit ||
                spell->GetSpellInfo()->Id == Generated::ShaShivSecond))
            GetRuntimeState(spell->GetCaster()->ToPlayer()).mutilateChildCritical = critical;
    }

    void OnSpellCastCancel(Spell* spell, Unit*, SpellInfo const*, bool) override
    {
        if (spell && spell->GetCaster() && spell->GetCaster()->IsPlayer())
        {
            PlayerRuntimeState& state = GetRuntimeState(spell->GetCaster()->ToPlayer());
            if (state.activeMutilateSpell == spell)
                state.activeMutilateSpell = nullptr;
            if (state.activeFanSpell == spell)
                state.activeFanSpell = nullptr;
        }
        EraseCastSnapshot(spell);
    }

    void OnSpellCast(Spell* spell, Unit* caster, SpellInfo const* spellInfo, bool) override
    {
        if (!spell || !caster || !caster->IsPlayer() || !spellInfo)
            return;
        Player* player = caster->ToPlayer();
        CastSnapshot const* procSnapshot = FindCastSnapshot(spell);
        bool comboOverflow = procSnapshot && procSnapshot->comboPoints >= 5;
        if (spellInfo->Id == 14189 && (HasPathPassiveRank(player, 14186) || HasPathPassiveRank(player, 14190) ||
            HasPathPassiveRank(player, 14193) || HasPathPassiveRank(player, 14194) || HasPathPassiveRank(player, 14195)))
        {
            PlayerRuntimeState& state = GetRuntimeState(player);
            uint32 now = getMSTime();
            RoguePath path = sCultivationRogueSpellService.GetPath(player);
            if (path == RoguePath::Celestial && comboOverflow)
            {
                uint32 second = now / 1000;
                if (state.sealFateSecond != second)
                {
                    state.sealFateSecond = second;
                    state.sealFateEnergyThisSecond = 0;
                }
                uint8 gain = std::min<uint8>(5, 10 - state.sealFateEnergyThisSecond);
                player->ModifyPower(POWER_ENERGY, gain);
                state.sealFateEnergyThisSecond += gain;
            }
            else if (path == RoguePath::Sha && getMSTimeDiff(state.shaSealFateEmpoweredAt, now) >= 2000)
            {
                uint8 rank = 0;
                uint8 currentRank = 0;
                for (uint32 baseRank : { 14186u, 14190u, 14193u, 14194u, 14195u })
                {
                    ++currentRank;
                    if (HasPathPassiveRank(player, baseRank))
                        rank = currentRank;
                }
                if (rank && roll_chance_i(20 * rank))
                {
                    if (Unit* target = player->GetComboTarget())
                        player->AddComboPoints(target, 1);
                    state.shaSealFateEmpoweredAt = now;
                }
            }
        }
        if (spellInfo->Id == 14189 || spellInfo->Id == 51699)
            EraseCastSnapshot(spell);
        auto variant = GetCastVariant(spell);
        if (!variant)
            return;
        if (variant->logicalName == "vanish" && variant->path == RoguePath::Sha)
            player->ModifySpellCooldown(spellInfo->Id, 45000 - int32(GetConfig().shaVanishCooldownReductionMs));

        if (CastSnapshot const* snapshot = FindCastSnapshot(spell))
        {
            if (snapshot->stealthWindow)
                player->RemoveAurasDueToSpell(Generated::ShaStealthWindow);
            if (snapshot->feintDiscount)
                player->RemoveAurasDueToSpell(Generated::ShaFeintDiscount);
        }
        if (variant->path == RoguePath::Sha && (variant->logicalName == "cold_blood" ||
            variant->logicalName == "adrenaline_rush" || variant->logicalName == "killing_spree" ||
            variant->logicalName == "shadow_dance"))
            TriggerBloodThrill(player);
    }

    void OnCalcMaxDuration(Aura const* aura, int32& maxDuration) override
    {
        if (!aura)
            return;
        auto variant = FindVariant(aura->GetId());
        if (!variant)
            return;
        if (variant->logicalName == "rupture" && variant->path == RoguePath::Celestial)
        {
            int32 amplitude = int32(aura->GetSpellInfo()->Effects[EFFECT_0].Amplitude);
            if (amplitude <= 0)
                amplitude = 2000;
            int32 ticks = std::max<int32>(1, (maxDuration + amplitude - 1) / amplitude);
            maxDuration = int32(std::ceil(float(ticks) * 1.4f)) * amplitude;
        }
        else if (variant->logicalName == "rupture" && variant->path == RoguePath::Sha)
            maxDuration = maxDuration * 3 / 5;
        else if (variant->logicalName == "slice_and_dice")
            maxDuration = variant->path == RoguePath::Celestial ? maxDuration * 3 / 2 : maxDuration / 2;
        else if (variant->logicalName == "garrote" && variant->path == RoguePath::Celestial)
            maxDuration += 6000;
        else if (variant->logicalName == "garrote" && variant->path == RoguePath::Sha)
            maxDuration = 9000;
        else if (variant->logicalName == "envenom" && variant->path == RoguePath::Celestial)
            maxDuration *= 2;
    }

    bool CanRemoveAuraOnDamage(Unit* victim, Aura const* aura, Unit* attacker, SpellInfo const* damageSpell,
        DamageEffectType damageType) override
    {
        if (!victim || !aura)
            return true;
        auto variant = FindVariant(aura->GetId());
        if (!variant)
            return true;

        if (variant->logicalName == "gouge" && variant->path == RoguePath::Sha && attacker &&
            aura->GetCasterGUID() == attacker->GetGUID())
        {
            bool ownPeriodic = damageType == DOT && damageSpell &&
                (damageSpell->GetAllEffectsMechanicMask() & (1ULL << MECHANIC_BLEED));
            bool ownPoison = damageSpell && damageSpell->Dispel == DISPEL_POISON;
            if (ownPeriodic || ownPoison)
                return false;
        }
        return true;
    }

    static void ApplyPathDamage(Unit* attacker, Unit* victim, SpellInfo const* spellInfo, DamageEffectType damageType, uint32& damage)
    {
        if (!attacker || !victim || damage == 0 || IsModuleTriggered())
            return;
        Player* rogue = attacker->ToPlayer();
        if (!rogue || !rogue->IsClass(CLASS_ROGUE, CLASS_CONTEXT_ABILITY))
            return;

        auto variant = spellInfo ? FindVariant(spellInfo->Id) : std::nullopt;
        if (variant && variant->logicalName == "fan_of_knives_offhand" && variant->path == RoguePath::Sha)
            damage = uint32(uint64(damage) * 65 / 100);
        bool direct = damageType != DOT && IsDirectAttack(spellInfo) && !IsModuleTriggered();
        if (!direct)
        {
            int32 passiveBonus = 0;
            if (rogue->HasAura(Generated::ShaHungerBuff)) passiveBonus += 12;
            if (rogue->HasAura(Generated::ShaCheatDeathDamage)) passiveBonus += 25;
            damage = uint32(uint64(damage) * (100 + passiveBonus) / 100);
        }
        // Direct path bonuses are combined once with the cast context before mitigation.
        if (!direct && HasAuraFrom(victim, Generated::ShaDismantleMark, rogue->GetGUID()))
            damage = uint32(uint64(damage) * 115 / 100);
        if (direct && spellInfo->GetSchoolMask() & SPELL_SCHOOL_MASK_NORMAL && !spellInfo->NeedsComboPoints())
        {
            TargetRuntimeState& state = GetRuntimeState(rogue).targets[victim->GetGUID().GetRawValue()];
            if (state.hemorrhageExpiresAt && int32(getMSTime() - state.hemorrhageExpiresAt) >= 0)
            {
                state.hemorrhageCharges = 0;
                state.hemorrhageExpiresAt = 0;
            }
            if (state.hemorrhageCharges && state.hemorrhageBonusDamage > 0)
            {
                damage += state.hemorrhageBonusDamage;
                --state.hemorrhageCharges;
            }
        }
    }

};

class spell_cultivation_rogue_active : public SpellScript
{
    PrepareSpellScript(spell_cultivation_rogue_active);

    SpellMissInfo _miss = SPELL_MISS_NONE;
    uint8 _comboPoints = 0;
    Spell const* _castKey = nullptr;

public:
    ~spell_cultivation_rogue_active() override
    {
        if (_castKey && GetCaster() && GetCaster()->IsPlayer())
        {
            auto& state = GetRuntimeState(GetCaster()->ToPlayer());
            if (state.activeFanSpell == _castKey)
                state.activeFanSpell = nullptr;
        }
        EraseCastSnapshot(_castKey);
    }

private:

    bool Load() override
    {
        _castKey = GetSpell();
        return GetCaster() && GetCaster()->IsPlayer() && GetCastVariant(GetSpell()).has_value();
    }

    void BeforeCastHandler()
    {
        SevenBeforeCast(GetSpell());
        Player* player = GetCaster()->ToPlayer();
        _comboPoints = player->GetComboPoints();
        CastSnapshot& snapshot = GetCastSnapshot(GetSpell());
        snapshot.comboPoints = _comboPoints;
        snapshot.comboTargetGuid = player->GetComboTargetGUID();
        snapshot.targetGuid = GetExplTargetUnit() ? GetExplTargetUnit()->GetGUID() : ObjectGuid::Empty;
        snapshot.deadlyPoisonStacks = GetOwnDeadlyPoisonStacks(GetExplTargetUnit(), player->GetGUID());
        snapshot.targetWasCasting = GetExplTargetUnit() && GetExplTargetUnit()->IsNonMeleeSpellCast(false);
        if (GetExplTargetUnit())
        {
            Spell* current = GetExplTargetUnit()->GetCurrentSpell(CURRENT_GENERIC_SPELL);
            if (!current)
                current = GetExplTargetUnit()->GetCurrentSpell(CURRENT_CHANNELED_SPELL);
            if (current)
                snapshot.interruptedSchoolMask = current->GetSpellInfo()->GetSchoolMask();
        }
        if (AuraEffect const* poison = GetExplTargetUnit() ? GetExplTargetUnit()->GetAuraEffect(SPELL_AURA_PERIODIC_DAMAGE,
            SPELLFAMILY_ROGUE, 0x10000, 0x80000, 0, player->GetGUID()) : nullptr)
        {
            int32 amplitude = std::max<int32>(1, poison->GetAmplitude());
            uint32 ticks = uint32(std::max<int32>(0, poison->GetBase()->GetDuration()) + amplitude - 1) / uint32(amplitude);
            // AuraEffect::CalculateAmount already includes the stack multiplier.
            uint32 tickDamage = GetExplTargetUnit()->SpellDamageBonusTaken(player, poison->GetSpellInfo(),
                uint32(std::max<int32>(0, poison->GetAmount())), DOT, poison->GetBase()->GetStackAmount());
            snapshot.deadlyPoisonRemainingDamage = tickDamage * ticks;
        }

        auto variant = GetCastVariant(GetSpell());
        if (!variant)
            return;
        if (variant->logicalName == "feint" && variant->path == RoguePath::Celestial && !GetSpell()->IsTriggered())
            snapshot.feintPowerBeforeCast = player->GetPower(POWER_ENERGY);
        if (variant->logicalName == "vanish" && variant->path == RoguePath::Celestial)
            CleanseCelestialVanish(player); // committed cast, before native Vanish effects
        if (variant->path == RoguePath::Celestial && IsDirectAttack(GetSpellInfo()) && !GetSpell()->IsTriggered() &&
            player->HasAura(Generated::CelestialColdBloodWindow))
            snapshot.celestialColdBlood = true;
        if (variant->logicalName == "mutilate" || variant->logicalName == "shiv")
            GetRuntimeState(player).activeMutilateSpell = GetSpell();
        if (variant->logicalName == "fan_of_knives" && !GetSpell()->IsTriggered())
            GetRuntimeState(player).activeFanSpell = GetSpell();
        if (snapshot.stealthWindow && !player->HasAura(Generated::ShaStealthWindow))
            GetRuntimeState(player).stealthAttackConsumed = true;
        if (variant->logicalName == "eviscerate" && variant->path == RoguePath::Celestial && _comboPoints == 5)
        {
            player->CastSpell(player, Generated::CelestialEviscerateArmor, true);
            snapshot.celestialEviscerateArmor = true;
        }
        if (variant->logicalName == "eviscerate" && variant->path == RoguePath::Sha && GetExplTargetUnit() &&
            GetExplTargetUnit()->HasAura(Generated::ShaGarroteWindow, player->GetGUID()))
        {
            player->CastSpell(player, Generated::ShaGarroteEviscerateArmor, true);
            snapshot.shaGarroteArmor = true;
        }
    }

    void BeforeHitHandler(SpellMissInfo missInfo)
    {
        _miss = missInfo;
    }

    void OnHitHandler()
    {
        if (_miss != SPELL_MISS_NONE || !GetHitUnit())
            return;
        Player* player = GetCaster()->ToPlayer();
        Unit* target = GetHitUnit();
        auto variant = GetCastVariant(GetSpell());
        CastSnapshot const* snapshot = FindCastSnapshot(GetSpell());
        if (!variant || !snapshot)
            return;

        int32 damage = GetHitDamage();
        if (damage > 0)
        {
            if (variant->logicalName == "envenom" && variant->path == RoguePath::Celestial)
                damage = damage * 90 / 100;
            if (variant->logicalName == "hemorrhage" && variant->path == RoguePath::Celestial)
                damage = damage * 90 / 100;
            if (variant->logicalName == "deadly_throw" && variant->path == RoguePath::Sha)
                damage = damage * 50 / 100;
            if (variant->logicalName == "fan_of_knives" && variant->path == RoguePath::Sha)
                damage = damage * 65 / 100;
            SetHitDamage(damage);
        }
    }

    void AfterHitHandler()
    {
        SevenAfterHit(GetSpell(), GetHitUnit(), _miss == SPELL_MISS_NONE, GetHitDamage() > 0);
        if (_miss != SPELL_MISS_NONE || !GetHitUnit())
            return;
        Player* player = GetCaster()->ToPlayer();
        Unit* target = GetHitUnit();
        auto variant = GetCastVariant(GetSpell());
        CastSnapshot const* snapshot = FindCastSnapshot(GetSpell());
        if (!variant || !snapshot)
            return;

        if (_comboPoints == 5 && GetSpellInfo()->NeedsComboPoints() && variant->path == RoguePath::Celestial)
        {
            player->CastSpell(player, Generated::CelestialFinisherRegen, true);
            player->CastSpell(player, Generated::CelestialFinisherGuard, true);
        }
        if (GetSpellInfo()->NeedsComboPoints() && variant->path == RoguePath::Celestial)
        {
            TargetRuntimeState& state = GetRuntimeState(player).targets[snapshot->comboTargetGuid.GetRawValue()];
            if (state.honorReserve)
            {
                // Core clears the spent combo points in _handle_finish_phase,
                // after AfterHit. Restore only after that phase has completed.
                PlayerRuntimeState& runtime = GetRuntimeState(player);
                runtime.pendingHonorTarget = snapshot->comboTargetGuid.GetRawValue();
                runtime.pendingHonorPoints = state.honorReserve;
                state.honorReserve = 0;
            }
        }
        if (GetSpellInfo()->NeedsComboPoints())
        {
            PlayerRuntimeState& state = GetRuntimeState(player);
            if (state.premeditationTarget == snapshot->comboTargetGuid.GetRawValue())
            {
                state.premeditationExpiresAt = 0;
                state.premeditationPoints = 0;
                state.premeditationTarget = 0;
            }
        }
        if (variant->logicalName == "eviscerate" && variant->path == RoguePath::Celestial && _comboPoints == 5)
            player->ModifyPower(POWER_ENERGY, 10);
        if (variant->logicalName == "mutilate" && variant->path == RoguePath::Sha && snapshot->deadlyPoisonStacks < 5)
        {
            // Use the equipped poison's real rank and native stacking rules, including
            // the zero-stack case. Never borrow another rogue's poison or invent a rank.
            uint32 poisonId = 0;
            Item* poisonWeapon = nullptr;
            for (uint8 slot : { uint8(EQUIPMENT_SLOT_MAINHAND), uint8(EQUIPMENT_SLOT_OFFHAND) })
                if (Item* item = player->GetItemByPos(INVENTORY_SLOT_BAG_0, slot))
                    if (SpellItemEnchantmentEntry const* enchant = sSpellItemEnchantmentStore.LookupEntry(item->GetEnchantmentId(TEMP_ENCHANTMENT_SLOT)))
                        for (uint8 index = 0; index < 3; ++index)
                            if (enchant->type[index] == ITEM_ENCHANTMENT_TYPE_COMBAT_SPELL)
                                if (SpellInfo const* info = sSpellMgr->GetSpellInfo(enchant->spellid[index]))
                                    if (info->SpellFamilyName == SPELLFAMILY_ROGUE && info->Dispel == DISPEL_POISON &&
                                        info->SpellFamilyFlags.IsEqual(0x10000, 0x80000, 0))
                                    {
                                        poisonId = info->Id;
                                        poisonWeapon = item;
                                    }
            if (poisonId)
                for (uint8 dose = 0; dose < 2 && GetOwnDeadlyPoisonStacks(target, player->GetGUID()) < 5; ++dose)
                {
                    TriggerGuard guard;
                    player->CastSpell(target, poisonId, true, poisonWeapon);
                }
        }
        if (variant->logicalName == "gouge" && variant->path == RoguePath::Sha)
            player->AddComboPoints(target, 1);
        if (variant->logicalName == "kidney_shot" && variant->path == RoguePath::Sha &&
            target->HasAura(GetSpellInfo()->Id, player->GetGUID()))
            player->CastSpell(target, Generated::ShaKidneyMark, true);
        if (variant->logicalName == "ambush" && variant->path == RoguePath::Celestial &&
            snapshot->confirmedDamageTargets.contains(target->GetGUID().GetRawValue()))
            player->AddComboPoints(target, 1);
        if (variant->logicalName == "kick" && snapshot->targetWasCasting && !target->IsNonMeleeSpellCast(false))
        {
            if (variant->path == RoguePath::Celestial)
                player->ModifyPower(POWER_ENERGY, std::min<int32>(snapshot->powerCost, player->GetMaxPower(POWER_ENERGY) - player->GetPower(POWER_ENERGY)));
            else
                player->CastSpell(target, Generated::ShaKickMark, true);
        }
        if (variant->logicalName == "deadly_throw" && variant->path == RoguePath::Sha && GetHitDamage() > 0)
        {
            PlayerRuntimeState& state = GetRuntimeState(player);
            state.delayedDamage.push_back({ target->GetGUID().GetRawValue(), uint32(GetHitDamage()), getMSTime() + 1000, false, false, Generated::ShaDeadlyThrowBlade });
            state.delayedDamage.push_back({ target->GetGUID().GetRawValue(), uint32(GetHitDamage()), getMSTime() + 2000, false, false, Generated::ShaDeadlyThrowBlade });
        }
        if (variant->logicalName == "deadly_throw" && variant->path == RoguePath::Celestial && _comboPoints == 5 &&
            snapshot->targetWasCasting && snapshot->interruptedSchoolMask)
        {
            target->InterruptNonMeleeSpells(false);
            target->ProhibitSpellSchool(SpellSchoolMask(snapshot->interruptedSchoolMask), 3000);
        }
        if (variant->logicalName == "sinister_strike")
        {
            PlayerRuntimeState& state = GetRuntimeState(player);
            if (variant->path == RoguePath::Celestial)
            {
                if (++state.celestialSinisterHits >= 3)
                {
                    state.celestialSinisterHits = 0;
                    player->ModifyPower(POWER_ENERGY, 10);
                    player->AddComboPoints(target, 1);
                }
            }
            else if (roll_chance_i(20) && GetHitDamage() > 0)
            {
                state.delayedDamage.push_back({ target->GetGUID().GetRawValue(), uint32(GetHitDamage() * 60 / 100), getMSTime(), true, false, Generated::ShaSinisterExtraAttack });
            }
        }
        if (variant->logicalName == "riposte")
        {
            if (variant->path == RoguePath::Celestial)
                player->CastSpell(target, Generated::CelestialRiposteDisarm, true);
            else
            {
                player->ModifyPower(POWER_ENERGY, 20);
                player->CastSpell(player, Generated::ShaRiposteHaste, true);
            }
        }
        if (variant->logicalName == "dismantle" && target->HasAura(GetSpellInfo()->Id, player->GetGUID()))
        {
            if (variant->path == RoguePath::Sha)
            {
                player->CastSpell(target, Generated::ShaDismantleMark, true);
            }
        }
        if (variant->logicalName == "tricks_of_the_trade")
        {
            // The inherited proc and cleanup scripts own the stock redirect token.
            player->GetThreatMgr().UnregisterRedirectThreat(GetSpellInfo()->Id);
            if (Unit* ally = GetExplTargetUnit())
                player->GetThreatMgr().RegisterRedirectThreat(57934, ally->GetGUID(), 100);
        }
        if (variant->logicalName == "expose_armor")
        {
            if (Aura* aura = target->GetAura(GetSpellInfo()->Id, player->GetGUID()))
            {
                int32 duration = int32(_comboPoints) * (variant->path == RoguePath::Celestial ? 12000 : 2000);
                aura->SetMaxDuration(duration);
                aura->SetDuration(duration);
            }
            if (variant->path == RoguePath::Celestial && _comboPoints == 5)
                player->ModifyPower(POWER_ENERGY, 10);
        }
        if (variant->logicalName == "hemorrhage")
        {
            TargetRuntimeState& state = GetRuntimeState(player).targets[target->GetGUID().GetRawValue()];
            state.hemorrhageCharges = variant->path == RoguePath::Celestial ? 20 : 5;
            state.hemorrhageExpiresAt = getMSTime() + 60000;
            SpellInfo const* baseInfo = sSpellMgr->GetSpellInfo(variant->baseSpell);
            state.hemorrhageBonusDamage = baseInfo ? baseInfo->Effects[EFFECT_2].CalcValue(player) : 0;
            if (variant->path == RoguePath::Sha)
                state.hemorrhageBonusDamage *= 3;
        }
        if (variant->logicalName == "garrote")
        {
            player->CastSpell(target, 1330, true);
            if (Aura* silence = target->GetAura(1330, player->GetGUID()))
            {
                int32 duration = variant->path == RoguePath::Celestial ?
                    silence->GetMaxDuration() + 1000 : 1000;
                silence->SetMaxDuration(duration);
                silence->SetDuration(duration);
            }
            if (variant->path == RoguePath::Sha)
                player->CastSpell(target, Generated::ShaGarroteWindow, true);
        }
        if (variant->logicalName == "premeditation" && variant->path == RoguePath::Sha)
        {
            PlayerRuntimeState& state = GetRuntimeState(player);
            state.premeditationTarget = target->GetGUID().GetRawValue();
            state.premeditationPoints = 2;
            state.premeditationExpiresAt = getMSTime() + 6000;
            player->ModifyPower(POWER_ENERGY, 40);
        }
        if (variant->logicalName == "envenom" && variant->path == RoguePath::Sha)
        {
            if (snapshot->deadlyPoisonRemainingDamage)
            {
                uint32 detonation = uint32(uint64(snapshot->deadlyPoisonRemainingDamage) * GetConfig().shaEnvenomDetonationPct / 100);
                DealDerivedDamage(player, target, Generated::ShaEnvenomDetonation, detonation, true);
            }
            std::unordered_set<uint32> poisonSpellIds;
            for (auto const& pair : target->GetAppliedAuras())
            {
                Aura* aura = pair.second->GetBase();
                if (aura->GetCasterGUID() == player->GetGUID() && aura->GetSpellInfo()->Dispel == DISPEL_POISON &&
                    aura->GetEffect(EFFECT_0) && aura->GetEffect(EFFECT_0)->GetAuraType() == SPELL_AURA_PERIODIC_DAMAGE)
                    poisonSpellIds.insert(aura->GetId());
            }
            for (uint32 spellId : poisonSpellIds)
                target->RemoveAurasDueToSpell(spellId, player->GetGUID());
        }
        if (snapshot->shaGarroteArmor)
            target->RemoveAurasDueToSpell(Generated::ShaGarroteWindow, player->GetGUID());
    }

    void AfterCastHandler()
    {
        Player* player = GetCaster()->ToPlayer();
        auto variant = GetCastVariant(GetSpell());
        if (variant)
        {
            if (variant->logicalName == "vanish")
            {
                player->RemoveAurasDueToSpell(1784);
                player->CastSpell(player, sCultivationRogueSpellService.GetVariantSpell(1784, variant->path), true);
                if (variant->path == RoguePath::Sha)
                {
                    player->CastSpell(player, Generated::ShaVanishWindow, true);
                    player->CastSpell(player, Generated::ShaVanishEnergy, true);
                }
            }
            else if (variant->logicalName == "sprint" && variant->path == RoguePath::Celestial)
            {
                // Stealth itself contains SPELL_AURA_MOD_DECREASE_SPEED. A
                // blanket RemoveAurasByType for slows therefore removed the
                // whole Stealth aura. The mechanic-filtered removal clears
                // hostile roots/snares without deleting the rogue's own
                // positive movement penalty.
                player->RemoveAurasWithMechanic((1ULL << MECHANIC_ROOT) | (1ULL << MECHANIC_SNARE));
                player->CastSpell(player, Generated::CelestialSprintImmunity, true);
            }
            else if (variant->logicalName == "feint" && variant->path == RoguePath::Sha)
            {
                player->CastSpell(player, Generated::ShaFeintGuard, true);
                player->CastSpell(player, Generated::ShaFeintDiscount, true);
            }
            else if (variant->logicalName == "feint" && variant->path == RoguePath::Celestial)
            {
                // The self guard succeeds even when the threat target is immune/missed.
                // Do not let native miss-refund make that successful defensive buff free.
                // These hooks bracket TakePower synchronously; Feint has no energy-grant effect.
                if (!GetSpell()->IsTriggered() && !player->GetCommandStatus(CHEAT_POWER))
                    if (CastSnapshot const* snapshot = FindCastSnapshot(GetSpell()); snapshot && snapshot->feintPowerBeforeCast >= 0)
                    {
                        int32 spent = std::max<int32>(0, snapshot->feintPowerBeforeCast - int32(player->GetPower(POWER_ENERGY)));
                        if (spent < snapshot->powerCost)
                            player->ModifyPower(POWER_ENERGY, -(snapshot->powerCost - spent));
                    }
                player->CastSpell(player, Generated::CelestialFeintGuard, true);
            }
            else if (variant->logicalName == "shadowstep")
            {
                if (variant->path == RoguePath::Sha)
                {
                    // The teleport has already resolved; discard the stock movement
                    // boost and stock +20% attack bonus for the Sha version.
                    player->RemoveAurasDueToSpell(36563);
                    player->RemoveAurasDueToSpell(44373);
                    player->RemoveAurasDueToSpell(GetSpellInfo()->Id);
                    player->CastSpell(player, Generated::ShaShadowstepDamage, true);
                }
                else
                {
                    player->RemoveAurasWithMechanic((1ULL << MECHANIC_ROOT) | (1ULL << MECHANIC_SNARE));
                    player->RemoveAurasByType(SPELL_AURA_MOD_ROOT);
                    player->RemoveAurasByType(SPELL_AURA_MOD_DECREASE_SPEED);
                    // Keep the stock 70% movement window, but remove the
                    // stock next-attack +20% damage component.
                    player->RemoveAurasDueToSpell(44373);
                }
            }
            else if (variant->logicalName == "cold_blood")
            {
                player->RemoveAurasDueToSpell(GetSpellInfo()->Id);
                player->CastSpell(player, variant->path == RoguePath::Celestial ?
                    Generated::CelestialColdBloodWindow : Generated::ShaColdBloodWindow, true);
                if (variant->path == RoguePath::Celestial)
                    if (Aura* window = player->GetAura(Generated::CelestialColdBloodWindow))
                        window->SetStackAmount(2);
            }
            else if (variant->logicalName == "hunger_for_blood")
            {
                if (variant->path == RoguePath::Celestial)
                {
                    Unit* target = GetExplTargetUnit();
                    if (!target || target == player)
                        target = player->GetSelectedUnit();
                    GetRuntimeState(player).hungerTarget = target ? target->GetGUID().GetRawValue() : 0;
                    player->CastSpell(player, 63848, true);
                    if (Aura* aura = player->GetAura(63848))
                    {
                        aura->SetMaxDuration(120000);
                        aura->SetDuration(120000);
                    }
                }
                else
                {
                    player->RemoveAurasDueToSpell(63848);
                    player->CastSpell(player, Generated::ShaHungerBuff, true);
                }
            }
            else if (variant->logicalName == "adrenaline_rush" && variant->path == RoguePath::Celestial)
                player->CastSpell(player, Generated::CelestialAdrenalineMaxEnergy, true);
            else if (variant->logicalName == "killing_spree")
            {
                if (variant->path == RoguePath::Celestial)
                {
                    player->CastSpell(player, Generated::CelestialKillingSpreeGuard, true);
                    if (Aura* guard = player->GetAura(Generated::CelestialKillingSpreeGuard))
                        if (Aura* spree = player->GetAura(GetSpellInfo()->Id))
                        {
                            guard->SetMaxDuration(spree->GetMaxDuration());
                            guard->SetDuration(spree->GetDuration());
                        }
                }
                else
                    player->CastSpell(player, Generated::ShaKillingSpreeExposure, true);
                if (variant->path == RoguePath::Sha)
                    if (Aura* aura = player->GetAura(GetSpellInfo()->Id))
                    {
                        int32 duration = int32(GetConfig().shaKillingSpreeAttackCount) * 500;
                        aura->SetMaxDuration(duration);
                        aura->SetDuration(duration);
                    }
            }
            else if (variant->logicalName == "preparation")
            {
                if (variant->path == RoguePath::Sha)
                {
                    for (uint32 base : { 51713u, 36554u, 1766u, 51722u })
                        player->RemoveSpellCooldown(sCultivationRogueSpellService.GetVariantSpell(base, variant->path), true);
                    player->ModifyPower(POWER_ENERGY, 40);
                }
            }
        }
        if (CastSnapshot const* snapshot = FindCastSnapshot(GetSpell()))
        {
            if (snapshot->stealthWindow)
                player->RemoveAurasDueToSpell(Generated::ShaStealthWindow);
            if (snapshot->feintDiscount)
                player->RemoveAurasDueToSpell(Generated::ShaFeintDiscount);
            if (snapshot->vanishWindow)
            {
                player->RemoveAurasDueToSpell(Generated::ShaVanishWindow);
                player->CastSpell(player, Generated::ShaVanishExposure, true);
            }
            if (snapshot->coldBloodBonus)
            {
                player->RemoveAurasDueToSpell(Generated::ShaColdBloodWindow);
                player->CastSpell(player, Generated::ShaColdBloodExposure, true);
            }
            if (snapshot->celestialColdBlood)
                if (Aura* window = player->GetAura(Generated::CelestialColdBloodWindow))
                {
                    if (window->GetStackAmount() > 1)
                        window->SetStackAmount(window->GetStackAmount() - 1);
                    else
                        player->RemoveAurasDueToSpell(Generated::CelestialColdBloodWindow);
                }
            if (snapshot->celestialEviscerateArmor)
                player->RemoveAurasDueToSpell(Generated::CelestialEviscerateArmor);
            if (snapshot->shaGarroteArmor)
                player->RemoveAurasDueToSpell(Generated::ShaGarroteEviscerateArmor);
        }
        // Projectile impacts occur after AfterCast; keep the snapshot until the
        // SpellScript is destroyed, not merely until the cast leaves the caster.
        SevenAfterCast(GetSpell());
        if (GetRuntimeState(player).activeMutilateSpell == GetSpell())
            GetRuntimeState(player).activeMutilateSpell = nullptr;
    }

    void Register() override
    {
        BeforeCast += SpellCastFn(spell_cultivation_rogue_active::BeforeCastHandler);
        BeforeHit += BeforeSpellHitFn(spell_cultivation_rogue_active::BeforeHitHandler);
        OnHit += SpellHitFn(spell_cultivation_rogue_active::OnHitHandler);
        AfterHit += SpellHitFn(spell_cultivation_rogue_active::AfterHitHandler);
        AfterCast += SpellCastFn(spell_cultivation_rogue_active::AfterCastHandler);
    }
};

class RoguePathUnitScript : public UnitScript
{
public:
    RoguePathUnitScript() : UnitScript("RoguePathUnitScript") { }

    void OnComboPointsGain(Unit* unit, Unit* target, uint8, uint8 overflow) override
    {
        Player* rogue = unit->ToPlayer();
        if (!rogue || !target->IsAlive() || sCultivationRogueSpellService.GetPath(rogue) != RoguePath::Celestial ||
            !(HasPathPassiveRank(rogue, 51698) || HasPathPassiveRank(rogue, 51700) || HasPathPassiveRank(rogue, 51701)))
            return;
        PlayerRuntimeState& state = GetRuntimeState(rogue);
        uint64 guid = target->GetGUID().GetRawValue();
        if (state.honorTarget && state.honorTarget != guid)
        {
            state.targets[state.honorTarget].honorReserve = 0;
            state.pendingHonorPoints = 0;
            state.pendingHonorTarget = 0;
        }
        state.honorTarget = guid;
        if (!state.restoringHonor)
            state.targets[guid].honorReserve = std::min<uint8>(2, state.targets[guid].honorReserve + overflow);
    }

    void ModifyMeleeDamage(Unit* target, Unit* attacker, uint32& damage) override
    {
        if (attacker && attacker->GetEntry() == 900406)
        {
            damage = 1;
            return;
        }
        if (Player* rogue = attacker ? attacker->ToPlayer() : nullptr)
        {
            TargetRuntimeState& state = GetRuntimeState(rogue).targets[target->GetGUID().GetRawValue()];
            if (state.hemorrhageExpiresAt && int32(getMSTime() - state.hemorrhageExpiresAt) >= 0)
            {
                state.hemorrhageCharges = 0;
                state.hemorrhageExpiresAt = 0;
            }
            if (state.hemorrhageCharges && state.hemorrhageBonusDamage > 0)
            {
                damage += state.hemorrhageBonusDamage;
                --state.hemorrhageCharges;
            }
        }
        ModifyIncoming(target, attacker, damage, nullptr);
        RoguePathAllSpellScript::ApplyPathDamage(attacker, target, nullptr, DIRECT_DAMAGE, damage);
    }

    void OnBeforeRollMeleeOutcomeAgainst(Unit const* attacker, Unit const*, WeaponAttackType,
        int32& attackerMaxSkillValueForLevel, int32& victimMaxSkillValueForLevel,
        int32& attackerWeaponSkill, int32& victimDefenseSkill, int32& critChance,
        int32& missChance, int32& dodgeChance, int32& parryChance, int32& blockChance) override
    {
        if (!attacker || attacker->GetEntry() != 900406)
            return;
        attackerMaxSkillValueForLevel = victimMaxSkillValueForLevel;
        attackerWeaponSkill = victimDefenseSkill;
        critChance = missChance = dodgeChance = parryChance = blockChance = 0;
    }

    void ModifySpellDamageTaken(Unit* target, Unit* attacker, int32& damage, SpellInfo const* spellInfo) override
    {
        if (damage <= 0)
            return;
        uint32 value = uint32(damage);
        ModifyIncoming(target, attacker, value, spellInfo);
        RoguePathAllSpellScript::ApplyPathDamage(attacker, target, spellInfo, SPELL_DIRECT_DAMAGE, value);
        damage = int32(value);
    }

    void ModifyPeriodicDamageAurasTick(Unit* target, Unit* attacker, uint32& damage, SpellInfo const* spellInfo) override
    {
        if (!IsPeriodicDamage(spellInfo))
            return; // This legacy hook is also invoked by periodic healing.
        ModifyIncoming(target, attacker, damage, spellInfo, false);
        RoguePathAllSpellScript::ApplyPathDamage(attacker, target, spellInfo, DOT, damage);
    }

    void ModifyPeriodicCombatDamage(Unit* target, Unit* attacker, uint32& damage, SpellInfo const* info) override
    {
        ModifyCelestialDamage(target, attacker, damage, info);
    }

    void OnAuraApply(Unit* target, Aura* aura) override
    {
        if (!target || !aura)
            return;
        auto variant = FindVariant(aura->GetId());
        if (variant && variant->logicalName == "cloak_of_shadows" && variant->path == RoguePath::Sha)
            target->CastSpell(target, Generated::ShaCloakPoisonPenetration, true);
        if (variant && variant->logicalName == "stealth" && target->IsPlayer())
        {
            PlayerRuntimeState& state = GetRuntimeState(target->ToPlayer());
            state.wasStealthed = true;
            state.stealthStartedAt = getMSTime();
            state.stealthAttackConsumed = false;
        }
        if (variant && variant->logicalName == "blade_flurry" && variant->path == RoguePath::Sha)
            if (AuraEffect* effect = aura->GetEffect(EFFECT_0))
                effect->ChangeAmount(GetConfig().shaBladeFlurryHastePct, false);
        if (aura->GetId() == Generated::CelestialStealthMastery)
        {
            uint32 stealth = sCultivationRogueSpellService.GetVariantSpell(1784, RoguePath::Celestial);
            if (Aura* stealthAura = target->GetAura(stealth))
                for (SpellEffIndex index : { EFFECT_0, EFFECT_1, EFFECT_2 })
                    if (AuraEffect* effect = stealthAura->GetEffect(index))
                        if (effect->GetAuraType() == SPELL_AURA_MOD_DECREASE_SPEED)
                            effect->ChangeAmount(0, false);
        }
        if (variant && variant->logicalName == "kidney_shot" && variant->path == RoguePath::Sha)
        {
            int32 duration = std::max<int32>(1000, aura->GetDuration() - 1000);
            aura->SetMaxDuration(duration);
            aura->SetDuration(duration);
        }
        if (aura->GetId() == 57933)
        {
            Player* rogue = aura->GetCaster() ? aura->GetCaster()->ToPlayer() : nullptr;
            if (rogue)
            {
                RoguePath path = sCultivationRogueSpellService.GetPath(rogue);
                if (path == RoguePath::Celestial || path == RoguePath::Sha)
                {
                    aura->Remove();
                    rogue->CastSpell(target, path == RoguePath::Celestial ?
                        Generated::CelestialTricksBoost : Generated::ShaTricksBoost, true);
                }
            }
        }
        if (aura->GetId() == Generated::CelestialTricksBoost || aura->GetId() == Generated::ShaTricksBoost)
        {
            bool celestial = aura->GetId() == Generated::CelestialTricksBoost;
            int32 duration = 1000 * (celestial ? GetConfig().celestialTricksDurationSeconds : GetConfig().shaTricksDurationSeconds);
            aura->SetMaxDuration(duration);
            aura->SetDuration(duration);
            if (AuraEffect* effect = aura->GetEffect(EFFECT_0))
                effect->ChangeAmount(celestial ? GetConfig().celestialTricksDamagePct : GetConfig().shaTricksDamagePct, false);
        }
        if (aura->GetId() == 61851 && target->HasAura(sCultivationRogueSpellService.GetVariantSpell(51690, RoguePath::Sha)))
            if (AuraEffect* effect = aura->GetEffect(EFFECT_0))
                effect->ChangeAmount(30, false);
    }

    void OnAuraRemove(Unit* target, AuraApplication* application, AuraRemoveMode mode) override
    {
        if (!target || !application)
            return;
        Aura* aura = application->GetBase();
        Player* owner = aura->GetCaster() ? aura->GetCaster()->ToPlayer() : nullptr;
        auto removedVariant = FindVariant(aura->GetId());
        if (removedVariant && removedVariant->path == RoguePath::Celestial &&
            (IsTechnicalAuraRemoval(target, owner) || mode == AURA_REMOVE_BY_DEATH))
            return;
        if ((owner && sCultivationRogueSpellService.IsSyncing(owner)) ||
            (target->IsPlayer() && sCultivationRogueSpellService.IsSyncing(target->ToPlayer())))
            return;
        if (aura->GetId() == Generated::ShaOverkillBonus)
            return;
        if (aura->GetId() == Generated::ShaHungerBuff)
        {
            target->CastSpell(target, Generated::ShaHungerPenalty, true);
            return;
        }
        auto variant = FindVariant(aura->GetId());
        if (!variant)
            return;
        if (variant->logicalName == "stealth" && target->IsPlayer())
        {
            Player* rogue = target->ToPlayer();
            PlayerRuntimeState& state = GetRuntimeState(rogue);
            rogue->RemoveAurasDueToSpell(Generated::CelestialStealthMastery);
            if (variant->path == RoguePath::Sha)
            {
                if (!state.stealthAttackConsumed)
                    rogue->CastSpell(rogue, Generated::ShaStealthWindow, true);
                TriggerBloodThrill(rogue);
                if (HasPathPassiveRank(rogue, 58426))
                {
                    rogue->RemoveAurasDueToSpell(Generated::ShaOverkillPenalty);
                    rogue->CastSpell(rogue, Generated::ShaOverkillBonus, true);
                }
            }
            else if (HasPathPassiveRank(rogue, 58426))
                rogue->CastSpell(rogue, Generated::CelestialOverkillBonus, true);
            state.wasStealthed = false;
        }
        if (variant->logicalName == "dismantle" && variant->path == RoguePath::Celestial)
        {
            if (Player* rogue = ObjectAccessor::FindConnectedPlayer(aura->GetCasterGUID()))
                ApplyCelestialDamageSuppression(rogue, target, 20, 6000);
        }
        else if (variant->logicalName == "dismantle" && variant->path == RoguePath::Sha)
        {
            target->RemoveAurasDueToSpell(Generated::ShaDismantleMark, aura->GetCasterGUID());
            if (Player* rogue = ObjectAccessor::FindConnectedPlayer(aura->GetCasterGUID()))
                rogue->RemoveAurasDueToSpell(Generated::ShaDismantleHaste);
        }
        else if (variant->logicalName == "kidney_shot" && variant->path == RoguePath::Sha)
            target->RemoveAurasDueToSpell(Generated::ShaKidneyMark, aura->GetCasterGUID());
        else if (variant->logicalName == "cloak_of_shadows" && variant->path == RoguePath::Celestial)
            target->CastSpell(target, Generated::CelestialCloakGuard, true);
        else if (variant->logicalName == "cloak_of_shadows" && variant->path == RoguePath::Sha)
            target->RemoveAurasDueToSpell(Generated::ShaCloakPoisonPenetration);
        else if (variant->logicalName == "adrenaline_rush")
        {
            if (variant->path == RoguePath::Celestial)
            {
                target->RemoveAurasDueToSpell(Generated::CelestialAdrenalineMaxEnergy);
                if (target->GetPower(POWER_ENERGY) > target->GetMaxPower(POWER_ENERGY))
                    target->SetPower(POWER_ENERGY, target->GetMaxPower(POWER_ENERGY));
            }
            else
                target->CastSpell(target, Generated::ShaAdrenalinePenalty, true);
        }
        else if (variant->logicalName == "killing_spree")
        {
            if (variant->path == RoguePath::Celestial)
                target->RemoveAurasDueToSpell(Generated::CelestialKillingSpreeGuard);
            else
                target->CastSpell(target, Generated::ShaKillingSpreeExposure, true);
        }
    }

private:
    static void ModifyCelestialDamage(Unit* target, Unit* attacker, uint32& damage, SpellInfo const* spellInfo)
    {
        if (!target || !damage)
            return;
        // Exactly one pre-packet modifier per event; no native percent-done
        // aura and no owner redirection. Old and new DoT ticks use this too.
        if (attacker && attacker->HasAura(Generated::CelestialDamageSuppression20))
            damage = uint32(uint64(damage) * 80 / 100);
        else if (attacker && attacker->HasAura(Generated::CelestialDamageSuppression15))
            damage = uint32(uint64(damage) * 85 / 100);
        if (!spellInfo || spellInfo->GetSchoolMask() == SPELL_SCHOOL_MASK_NORMAL)
            for (Generated::SpellVariantRow const& row : Generated::SpellVariants)
                if (row.logicalName == "evasion" && target->HasAura(row.celestialSpell))
                {
                    damage = uint32(uint64(damage) * 85 / 100);
                    break;
                }
    }

    static void ModifyIncoming(Unit* target, Unit* attacker, uint32& damage, SpellInfo const* spellInfo, bool celestial = true)
    {
        if (celestial)
            ModifyCelestialDamage(target, attacker, damage, spellInfo);
        if (!target || !attacker || !damage)
            return;
        if (target->HasAura(Generated::ShaCheapShotMark))
            damage = uint32(uint64(damage) * (100 + GetConfig().shaCheapPvE) / 100);
        if (target->HasAura(Generated::ShaKidneyMark))
            damage = uint32(uint64(damage) * (100 + GetConfig().shaKidneyPvEDamagePct) / 100);

        Player* rogue = target->ToPlayer();
        if (rogue)
        {
            if (rogue->HasAura(Generated::ShaBloodThrill))
                damage = uint32(uint64(damage) * (100 + GetConfig().shaBloodThrillIncomingDamagePct) / 100);
            if (rogue->HasAura(45182) && sCultivationRogueSpellService.GetPath(rogue) != RoguePath::None)
                damage = uint32(uint64(damage) * (sCultivationRogueSpellService.GetPath(rogue) == RoguePath::Celestial ? 10 : 20) / 100);
            if (rogue->HasAura(Generated::ShaVanishExposure) || rogue->HasAura(Generated::ShaColdBloodExposure))
                damage = uint32(uint64(damage) * 110 / 100);
            if (rogue->HasAura(Generated::CelestialCloakGuard) && spellInfo &&
                !(spellInfo->GetSchoolMask() & SPELL_SCHOOL_MASK_NORMAL))
                damage = uint32(uint64(damage) * 80 / 100);
        }
    }
};

class spell_cultivation_rogue_celestial_fan : public SpellScript
{
    PrepareSpellScript(spell_cultivation_rogue_celestial_fan);
    void Filter(std::list<WorldObject*>& targets)
    {
        targets.remove_if([this](WorldObject* target) { return GetCaster()->GetExactDist(target) > 12.0f; });
    }
    void Register() override
    {
        OnObjectAreaTargetSelect += SpellObjectAreaTargetSelectFn(spell_cultivation_rogue_celestial_fan::Filter, EFFECT_0, TARGET_UNIT_DEST_AREA_ENEMY);
    }
};

class spell_cultivation_rogue_evasion : public AuraScript
{
    PrepareAuraScript(spell_cultivation_rogue_evasion);

    bool CheckProc(ProcEventInfo& eventInfo)
    {
        Player* rogue = GetTarget()->ToPlayer();
        return rogue && sCultivationRogueSpellService.GetPath(rogue) == RoguePath::Sha &&
            (eventInfo.GetHitMask() & PROC_HIT_DODGE);
    }

    void HandleProc(ProcEventInfo&)
    {
        PreventDefaultAction();
        Player* rogue = GetTarget()->ToPlayer();
        if (!rogue)
            return;
        rogue->ModifyPower(POWER_ENERGY, 5);
    }

    void Register() override
    {
        DoCheckProc += AuraCheckProcFn(spell_cultivation_rogue_evasion::CheckProc);
        OnProc += AuraProcFn(spell_cultivation_rogue_evasion::HandleProc);
    }
};
}

void AddRoguePathCommonSpellScripts()
{
    new RoguePathAllSpellScript();
    new RoguePathUnitScript();
    RegisterSpellScript(spell_cultivation_rogue_active);
    RegisterSpellScript(spell_cultivation_rogue_celestial_fan);
    RegisterSpellScript(spell_cultivation_rogue_evasion);
}
}
