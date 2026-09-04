#include "RoguePathMechanics.h"
#include "RoguePathBalanceMath.h"

#include "AllSpellScript.h"
#include "Player.h"
#include "Spell.h"
#include "SpellAuras.h"
#include "SpellInfo.h"
#include "SpellAuraEffects.h"
#include "UnitScript.h"
#include "generated/RoguePathGeneratedSpells.h"

#include <algorithm>

namespace Cultivation::Rogue
{
namespace
{
bool HasMasterPoisoner(Player const* player)
{
    return Mechanics::HasPathPassiveRank(player, 31226) || Mechanics::HasPathPassiveRank(player, 31227) ||
        Mechanics::HasPathPassiveRank(player, 58410);
}

bool IsDeadlyPoison(SpellInfo const* spellInfo)
{
    return spellInfo && spellInfo->Dispel == DISPEL_POISON && spellInfo->SpellFamilyName == SPELLFAMILY_ROGUE &&
        spellInfo->SpellFamilyFlags.IsEqual(0x10000, 0x80000, 0);
}

void ApplyPoisonDamage(Unit* attacker, Unit* victim, SpellInfo const* spellInfo, uint32& damage)
{
    if (!attacker || !victim || !spellInfo || !damage || Mechanics::IsModuleTriggered() ||
        spellInfo->Dispel != DISPEL_POISON || spellInfo->SpellFamilyName != SPELLFAMILY_ROGUE)
        return;
    Player* rogue = attacker->ToPlayer();
    if (!rogue || sCultivationRogueSpellService.GetPath(rogue) != RoguePath::Sha)
        return;
    int32 groupBonus = 0;
    if (victim->HasAura(Generated::ShaMasterPoisonerWindow, rogue->GetGUID()))
        groupBonus = Generated::MasterPoisonerShaDamagePercent;
    int shiv = victim->HasAura(Generated::ShaShivVulnerability, rogue->GetGUID()) ?
        GetConfig().shaShivPoisonPvE : 0;
    int cloak = rogue->HasAura(sCultivationRogueSpellService.GetVariantSpell(31224, RoguePath::Sha)) ? 20 : 0;
    groupBonus = BalanceMath::PoisonBonus(groupBonus, shiv, cloak);
    damage = uint32(uint64(damage) * (100 + groupBonus) / 100);
}

class RoguePathAssassinationUnitScript : public UnitScript
{
public:
    RoguePathAssassinationUnitScript() : UnitScript("RoguePathAssassinationUnitScript") { }

    void ModifySpellDamageTaken(Unit* target, Unit* attacker, int32& damage, SpellInfo const* spellInfo) override
    {
        uint32 value = uint32(std::max(0, damage));
        ApplyPoisonDamage(attacker, target, spellInfo, value);
        damage = int32(value);
    }

    void ModifyPeriodicDamageAurasTick(Unit* target, Unit* attacker, uint32& damage, SpellInfo const* spellInfo) override
    {
        if (!Mechanics::IsPeriodicDamage(spellInfo))
            return;
        ApplyPoisonDamage(attacker, target, spellInfo, damage);
    }

    void OnAuraApply(Unit* target, Aura* aura) override
    {
        if (!target || !aura || aura->GetSpellInfo()->Dispel != DISPEL_POISON)
            return;
        Player* rogue = aura->GetCaster() ? aura->GetCaster()->ToPlayer() : nullptr;
        if (!rogue || !HasMasterPoisoner(rogue))
            return;

        RoguePath path = sCultivationRogueSpellService.GetPath(rogue);
        if (path == RoguePath::Sha)
        {
            Mechanics::TargetRuntimeState& state = Mechanics::GetRuntimeState(rogue).targets[target->GetGUID().GetRawValue()];
            if (IsDeadlyPoison(aura->GetSpellInfo()) && !state.shaDeadlyPoisonPresent)
            {
                state.shaDeadlyPoisonPresent = true;
                rogue->CastSpell(target, Generated::ShaMasterPoisonerWindow, true);
            }

            if (target->HasAura(Generated::ShaMasterPoisonerWindow, rogue->GetGUID()))
                for (SpellEffIndex index : { EFFECT_0, EFFECT_1, EFFECT_2 })
                    if (AuraEffect* effect = aura->GetEffect(index))
                        if (effect->GetAuraType() == SPELL_AURA_MOD_DECREASE_SPEED)
                            effect->ChangeAmount(-int32(Generated::MasterPoisonerShaSlowPercent), false);
        }
    }

    void OnAuraRemove(Unit* target, AuraApplication* application, AuraRemoveMode) override
    {
        if (!target || !application || application->GetBase()->GetSpellInfo()->Dispel != DISPEL_POISON)
            return;
        Aura* removed = application->GetBase();
        Player* rogue = removed->GetCaster() ? removed->GetCaster()->ToPlayer() : nullptr;
        if (!rogue || sCultivationRogueSpellService.GetPath(rogue) != RoguePath::Sha)
            return;

        if (!IsDeadlyPoison(removed->GetSpellInfo()))
            return;
        bool anotherOwnDeadlyPoison = false;
        for (auto const& pair : target->GetAppliedAuras())
        {
            Aura* existing = pair.second->GetBase();
            if (existing != removed && existing->GetCasterGUID() == rogue->GetGUID() &&
                IsDeadlyPoison(existing->GetSpellInfo()))
            {
                anotherOwnDeadlyPoison = true;
                break;
            }
        }
        if (!anotherOwnDeadlyPoison)
            Mechanics::GetRuntimeState(rogue).targets[target->GetGUID().GetRawValue()].shaDeadlyPoisonPresent = false;
    }
};

class RoguePathAssassinationAllSpellScript : public AllSpellScript
{
public:
    RoguePathAssassinationAllSpellScript() : AllSpellScript("RoguePathAssassinationAllSpellScript") { }

    void OnCalcMaxDuration(Aura const* aura, int32& duration) override
    {
        if (!aura || duration <= 0 || aura->GetSpellInfo()->Dispel != DISPEL_POISON)
            return;
        Player* rogue = aura->GetCaster() ? aura->GetCaster()->ToPlayer() : nullptr;
        if (!rogue || !HasMasterPoisoner(rogue))
            return;

        duration = sCultivationRogueSpellService.GetPath(rogue) == RoguePath::Celestial ? duration * 3 / 2 : duration / 2;
    }

    void ModifyItemCombatSpellChance(Player* player, Unit*, SpellInfo const* spellInfo, float& chance) override
    {
        if (player && spellInfo && spellInfo->Dispel == DISPEL_POISON && HasMasterPoisoner(player) &&
            sCultivationRogueSpellService.GetPath(player) == RoguePath::Sha)
            chance = std::min(100.0f, chance + float(Generated::MasterPoisonerShaApplicationPercentagePoints));
    }

    void ModifySpellHitResult(Spell* spell, Unit*, SpellMissInfo& missInfo) override
    {
        if (!spell || (missInfo != SPELL_MISS_MISS && missInfo != SPELL_MISS_RESIST))
            return;
        Player* rogue = spell->GetCaster() ? spell->GetCaster()->ToPlayer() : nullptr;
        if (!rogue || !spell->GetSpellInfo() || spell->GetSpellInfo()->Dispel != DISPEL_POISON ||
            sCultivationRogueSpellService.GetPath(rogue) != RoguePath::Sha)
            return;
        uint32 cloak = sCultivationRogueSpellService.GetVariantSpell(31224, RoguePath::Sha);
        if (rogue->HasAura(cloak))
            missInfo = SPELL_MISS_NONE;
    }

};
}

void AddRoguePathAssassinationScripts()
{
    new RoguePathAssassinationUnitScript();
    new RoguePathAssassinationAllSpellScript();
}
}
