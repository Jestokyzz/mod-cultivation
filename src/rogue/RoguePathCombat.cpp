#include "RoguePathMechanics.h"

#include "AllSpellScript.h"
#include "CellImpl.h"
#include "GridNotifiersImpl.h"
#include "ObjectAccessor.h"
#include "Player.h"
#include "Random.h"
#include "SpellAuraEffects.h"
#include "SpellScript.h"
#include "SpellScriptLoader.h"
#include "SpellInfo.h"
#include "SpellMgr.h"
#include "Unit.h"
#include "Timer.h"
#include "generated/RoguePathGeneratedSpells.h"

#include <algorithm>
#include <cmath>
#include <limits>

namespace Cultivation::Rogue
{
namespace
{
class RoguePathCombatAllSpellScript : public AllSpellScript
{
public:
    RoguePathCombatAllSpellScript() : AllSpellScript("RoguePathCombatAllSpellScript") { }

    void ModifyDamage(Unit* attacker, Unit* victim, SpellInfo const* spellInfo, DamageEffectType damageType, uint32& damage) override
    {
        if (!attacker || !victim || damage == 0 || damageType == DOT || Mechanics::IsModuleTriggered())
            return;
        Player* rogue = attacker->ToPlayer();
        if (!rogue || (spellInfo && !Mechanics::IsDirectAttack(spellInfo)))
            return;
        auto variant = spellInfo ? Mechanics::FindVariant(spellInfo->Id) : std::nullopt;
        if (variant && variant->path == RoguePath::Sha &&
            (variant->logicalName == "fan_of_knives" || variant->logicalName == "fan_of_knives_offhand"))
        {
            bool offhand = variant->logicalName == "fan_of_knives_offhand";
            Mechanics::GetRuntimeState(rogue).delayedDamage.push_back({ victim->GetGUID().GetRawValue(), damage, getMSTime(), !offhand, offhand, Generated::ShaFanExtraAttack });
        }
        RoguePath path = sCultivationRogueSpellService.GetPath(rogue);
        uint32 bladeFlurry = sCultivationRogueSpellService.GetVariantSpell(13877, path);
        if (path == RoguePath::None || !rogue->HasAura(bladeFlurry))
            return;
        std::list<Unit*> targets;
        Acore::AnyUnfriendlyNoTotemUnitInObjectRangeCheck check(rogue, rogue, NOMINAL_MELEE_RANGE);
        Acore::UnitListSearcher<Acore::AnyUnfriendlyNoTotemUnitInObjectRangeCheck> searcher(rogue, targets, check);
        Cell::VisitObjects(rogue, searcher, NOMINAL_MELEE_RANGE);
        targets.remove_if([rogue, victim](Unit* target)
        {
            return target == victim || !target->IsAlive() || !rogue->IsWithinLOSInMap(target) || !rogue->IsValidAttackTarget(target);
        });
        targets.sort([rogue](Unit* left, Unit* right)
        {
            float leftDistance = rogue->GetDistance(left);
            float rightDistance = rogue->GetDistance(right);
            if (std::abs(leftDistance - rightDistance) > 0.001f)
                return leftDistance < rightDistance;
            return left->GetGUID().GetRawValue() < right->GetGUID().GetRawValue();
        });
        uint32 copySpell = path == RoguePath::Celestial ? Generated::CelestialBladeFlurryCopy : Generated::ShaBladeFlurryCopy;
        if (path == RoguePath::Celestial && targets.size() > 4)
            targets.resize(4);
        else if (path == RoguePath::Sha && targets.size() > 1)
            targets.resize(1);
        uint32 count = uint32(targets.size());
        if (!count)
            return;
        uint32 copied = path == RoguePath::Celestial ? damage / count : damage;
        uint32 remainder = path == RoguePath::Celestial ? damage % count : 0;
        for (Unit* target : targets)
        {
            Mechanics::DealDerivedDamage(rogue, target, copySpell, copied + (remainder ? 1 : 0));
            if (remainder)
                --remainder;
        }
    }
};

class spell_cultivation_rogue_combat_potency : public AuraScript
{
    PrepareAuraScript(spell_cultivation_rogue_combat_potency);

    bool CheckProc(ProcEventInfo& eventInfo)
    {
        DamageInfo const* damageInfo = eventInfo.GetDamageInfo();
        return damageInfo && damageInfo->GetDamage() > 0 && damageInfo->GetAttackType() == OFF_ATTACK;
    }

    void HandleProc(AuraEffect const*, ProcEventInfo&)
    {
        PreventDefaultAction();
        Player* rogue = GetTarget()->ToPlayer();
        if (!rogue)
            return;
        RoguePath path = sCultivationRogueSpellService.GetPath(rogue);
        if (path == RoguePath::Celestial)
            rogue->ModifyPower(POWER_ENERGY, std::clamp<int32>(int32(GetId()) - 86408, 1, 5));
        else if (path == RoguePath::Sha)
        {
            if (!roll_chance_i(Generated::CombatPotencyShaProcChance))
                return;
            // Energy and haste are one proc, never independent rolls or unconditional haste.
            rogue->ModifyPower(POWER_ENERGY, Generated::CombatPotencyShaEnergy);
            rogue->CastSpell(rogue, Generated::ShaCombatPotencyHaste, true);
            if (Aura* aura = rogue->GetAura(Generated::ShaCombatPotencyHaste))
            {
                aura->SetStackAmount(std::min<uint8>(Generated::CombatPotencyShaMaxStacks, aura->GetStackAmount()));
                aura->RefreshDuration();
            }
        }
    }

    void Register() override
    {
        DoCheckProc += AuraCheckProcFn(spell_cultivation_rogue_combat_potency::CheckProc);
        OnEffectProc += AuraEffectProcFn(spell_cultivation_rogue_combat_potency::HandleProc, EFFECT_0, SPELL_AURA_PROC_TRIGGER_SPELL);
    }
};
}

void AddRoguePathCombatScripts()
{
    new RoguePathCombatAllSpellScript();
    RegisterSpellScript(spell_cultivation_rogue_combat_potency);
}
}
