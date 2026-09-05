#ifndef MOD_CULTIVATION_ROGUE_MECHANICS_H
#define MOD_CULTIVATION_ROGUE_MECHANICS_H

#include "ObjectGuid.h"
#include "CultivationRogue.h"

#include <optional>
#include <deque>
#include <string_view>
#include <unordered_map>
#include <unordered_set>
#include <vector>

class Aura;
class ChatHandler;
class Player;
class Spell;
class SpellInfo;
class Unit;

namespace Cultivation::Rogue::Mechanics
{
struct VariantInfo
{
    std::string_view logicalName;
    RoguePath path;
    uint32 baseSpell;
};

struct CastSnapshot
{
    uint8 comboPoints = 0;
    int32 powerCost = 0;
    int32 feintPowerBeforeCast = -1;
    uint8 deadlyPoisonStacks = 0;
    ObjectGuid targetGuid;
    ObjectGuid comboTargetGuid;
    bool targetWasCasting = false;
    uint32 interruptedSchoolMask = 0;
    bool stealthWindow = false;
    bool vanishWindow = false;
    bool feintDiscount = false;
    bool shadowstepBonus = false;
    bool coldBloodBonus = false;
    bool bladeFlurryCost = false;
    uint8 eviscerateExtraEnergy = 0;
    uint32 deadlyPoisonRemainingDamage = 0;
    bool celestialColdBlood = false;
    bool celestialEviscerateArmor = false;
    bool shaGarroteArmor = false;
    uint32 openerSpell = 0;
    ObjectGuid openerTarget;
    int32 openerDamagePct = 0;
    bool openerSelected = false;
    bool sevenHit = false;
    bool ownControl = false;
    bool backstabRefunded = false;
    bool mutilateRefunded = false;
    bool diveComboAwarded = false;
    bool shivComboAwarded = false;
    bool shivWindowApplied = false;
    std::unordered_set<uint64> fanEnergyTargets;
    std::unordered_set<uint64> confirmedDamageTargets;
};

struct TargetRuntimeState
{
    uint8 honorReserve = 0;
    bool shaDeadlyPoisonPresent = false;
    uint32 sapCooldownUntil = 0;
    uint32 blindStartedAt = 0;
};

struct DelayedDamage
{
    uint64 targetGuid = 0;
    uint32 damage = 0;
    uint32 dueMs = 0;
    bool triggerMainHandPoison = false;
    bool triggerOffHandPoison = false;
    uint32 spellId = 0;
};

struct PlayerRuntimeState
{
    bool restoringHonor = false;
    uint8 celestialSinisterHits = 0;
    uint32 cheatHealRemaining = 0;
    uint32 cheatEnergyRemaining = 0;
    uint8 sealFateEnergyThisSecond = 0;
    std::deque<uint32> shaHonorProcTimes;
    uint32 sealFateSecond = 0;
    uint32 shaSealFateEmpoweredAt = 0;
    uint32 stealthStartedAt = 0;
    uint32 cheatHealNextTick = 0;
    uint32 cheatEnergyNextTick = 0;
    uint8 cheatHealTicks = 0;
    uint8 cheatEnergyTicks = 0;
    uint64 honorTarget = 0;
    uint64 hungerTarget = 0;
    bool wasStealthed = false;
    bool stealthAttackConsumed = false;
    uint64 pendingHonorTarget = 0;
    uint8 pendingHonorPoints = 0;
    uint64 pendingDiveTarget = 0;
    Spell const* activeMutilateSpell = nullptr;
    Spell const* activeFanSpell = nullptr;
    bool mutilateChildCritical = false;
    uint32 celestialFallCooldownUntil = 0;
    uint32 shaFallCooldownUntil = 0;
    uint32 celestialFanEnergyGranted = 0;
    uint32 cleanupDepth = 0;
    bool forcingShivPoison = false;
    std::unordered_map<uint64, TargetRuntimeState> targets;
    std::vector<DelayedDamage> delayedDamage;
};

std::optional<VariantInfo> FindVariant(uint32 spellId);
bool IsDirectAttack(SpellInfo const* spellInfo);
bool IsPeriodicDamage(SpellInfo const* spellInfo);
bool IsCriticalForTarget(Spell* spell, Unit const* target);
uint8 GetOwnDeadlyPoisonStacks(Unit const* target, ObjectGuid casterGuid);
bool HasPathPassiveRank(Player const* player, uint32 baseSpell);
PlayerRuntimeState& GetRuntimeState(Player const* player);
void EraseRuntimeState(Player const* player);

CastSnapshot& GetCastSnapshot(Spell* spell);
CastSnapshot const* FindCastSnapshot(Spell const* spell);
void EraseCastSnapshot(Spell const* spell);
uint32 DealDerivedDamage(Player* player, Unit* target, uint32 spellId, uint32 calculatedDamage, bool applyModifiers = false);

void TriggerBloodThrill(Player* player);
bool IsModuleTriggered();
void PushModuleTriggered();
void PopModuleTriggered();
void SevenPowerCost(Spell* spell, int32& cost);
void SevenBeforeCast(Spell* spell);
void SevenAfterHit(Spell* spell, Unit* target, bool successful, bool dealtDamage);
void SevenAfterCast(Spell* spell);
void CleanupSevenEffects(Player* player);
bool IsSevenCleanup(Player const* player);
void ResetRuntimeForPathChange(Player* player);
void ApplyCelestialDamageSuppression(Player* rogue, Unit* target, uint8 strength, int32 duration);
void CleanseCelestialVanish(Player* player);
void CleanseBlindPeriodic(Unit* target);
bool IsTechnicalAuraRemoval(Unit const* target, Player const* caster);
void RemoveRetiredCelestialAuras(Player* player);
void SyncCelestialPreparationGlyph(Player* player);
bool RunCelestialRegression(Player* player, ChatHandler* chat);
bool RunShadowstepRegression(Player* player, ChatHandler* chat);
bool RunCelestialResourceRegression(Player* player, ChatHandler* chat);
bool RunShaSinisterRegression(Player* player, ChatHandler* chat);
bool RunShaCandidate41Regression(Player* player, ChatHandler* chat);
}

#endif
