#include "RoguePathMechanics.h"

#include "AllSpellScript.h"
#include "Player.h"
#include "SpellAuras.h"
#include "SpellInfo.h"
#include "SpellAuraEffects.h"
#include "SpellScript.h"
#include "SpellScriptLoader.h"
#include "Random.h"
#include "SpellMgr.h"
#include "Timer.h"
#include "UnitScript.h"
#include "generated/RoguePathGeneratedSpells.h"

namespace Cultivation::Rogue
{
namespace
{
constexpr uint32 SPELL_ROGUE_CHEATING_DEATH = 45182;

class spell_cultivation_rogue_sha_honor : public AuraScript
{
    PrepareAuraScript(spell_cultivation_rogue_sha_honor);

    bool CheckProc(ProcEventInfo& event)
    {
        DamageInfo const* damage = event.GetDamageInfo();
        return !Mechanics::IsModuleTriggered() && damage && damage->GetDamage() > 0 &&
            (event.GetHitMask() & PROC_EX_CRITICAL_HIT) &&
            Mechanics::IsDirectAttack(event.GetSpellInfo()) && event.GetActor() == GetTarget();
    }

    void HandleProc(AuraEffect const*, ProcEventInfo& event)
    {
        PreventDefaultAction();
        Player* rogue = GetTarget()->ToPlayer();
        Unit* target = event.GetActionTarget();
        if (!rogue || !target || !target->IsAlive() || sCultivationRogueSpellService.GetPath(rogue) != RoguePath::Sha)
            return;
        auto& times = Mechanics::GetRuntimeState(rogue).shaHonorProcTimes;
        uint32 now = getMSTime();
        while (!times.empty() && getMSTimeDiff(times.front(), now) >= Generated::HonorAmongThievesShaWindowMs)
            times.pop_front();
        if (times.size() < Generated::HonorAmongThievesShaLimit && roll_chance_i(Generated::HonorAmongThievesShaProcChance))
        {
            rogue->AddComboPoints(target, 1);
            times.push_back(now);
        }
    }

    void Register() override
    {
        DoCheckProc += AuraCheckProcFn(spell_cultivation_rogue_sha_honor::CheckProc);
        OnEffectProc += AuraEffectProcFn(spell_cultivation_rogue_sha_honor::HandleProc, EFFECT_0, SPELL_AURA_DUMMY);
    }
};

class RoguePathSubtletyUnitScript : public UnitScript
{
public:
    RoguePathSubtletyUnitScript() : UnitScript("RoguePathSubtletyUnitScript") { }

    void OnAuraApply(Unit* target, Aura* aura) override
    {
        Player* rogue = target ? target->ToPlayer() : nullptr;
        if (!rogue || !aura || aura->GetId() != SPELL_ROGUE_CHEATING_DEATH)
            return;
        RoguePath path = sCultivationRogueSpellService.GetPath(rogue);
        if (path == RoguePath::Celestial)
        {
            aura->SetMaxDuration(4000);
            aura->SetDuration(4000);
            Mechanics::PlayerRuntimeState& state = Mechanics::GetRuntimeState(rogue);
            state.cheatHealTicks = 4;
            state.cheatHealRemaining = rogue->CountPctFromMaxHealth(10);
            state.cheatHealNextTick = getMSTime() + 1000;
        }
        else if (path == RoguePath::Sha)
        {
            aura->SetMaxDuration(2000);
            aura->SetDuration(2000);
            Mechanics::PlayerRuntimeState& state = Mechanics::GetRuntimeState(rogue);
            state.cheatEnergyTicks = 2;
            state.cheatEnergyRemaining = 60;
            state.cheatEnergyNextTick = getMSTime() + 1000;
            rogue->RemoveSpellCooldown(sCultivationRogueSpellService.GetVariantSpell(36554, RoguePath::Sha), true);
            rogue->CastSpell(rogue, Generated::ShaCheatDeathDamage, true);
        }
    }
};

class RoguePathSubtletyDamageScript : public UnitScript
{
public:
    RoguePathSubtletyDamageScript() : UnitScript("RoguePathSubtletyDamageScript") { }

    void ModifySpellDamageTaken(Unit* target, Unit* attacker, int32& damage, SpellInfo const* spellInfo) override
    {
        uint32 value = damage > 0 ? uint32(damage) : 0;
        ApplyDamage(attacker, target, spellInfo, SPELL_DIRECT_DAMAGE, value);
        damage = int32(value);
    }

    void ModifyPeriodicDamageAurasTick(Unit* target, Unit* attacker, uint32& damage, SpellInfo const* spellInfo) override
    {
        if (!Mechanics::IsPeriodicDamage(spellInfo))
            return;
        ApplyDamage(attacker, target, spellInfo, DOT, damage);
    }

    void ModifyMeleeDamage(Unit* target, Unit* attacker, uint32& damage) override
    {
        ApplyDamage(attacker, target, nullptr, DIRECT_DAMAGE, damage);
    }

    static void ApplyDamage(Unit* attacker, Unit* victim, SpellInfo const* spellInfo, DamageEffectType damageType, uint32& damage)
    {
        Player* rogue = attacker ? attacker->ToPlayer() : nullptr;
        if (!rogue || !victim || damage == 0 || Mechanics::IsModuleTriggered())
            return;
        RoguePath path = sCultivationRogueSpellService.GetPath(rogue);
        if (rogue->HasAura(SPELL_ROGUE_CHEATING_DEATH) && path == RoguePath::Celestial)
            damage = uint32(uint64(damage) * 80 / 100);

        if (!spellInfo)
            return;

        uint32 baseSpell = sCultivationRogueSpellService.GetBaseSpell(spellInfo->Id);
        if (uint32 first = sSpellMgr->GetFirstSpellInChain(baseSpell))
            baseSpell = first;
        uint32 dance = sCultivationRogueSpellService.GetVariantSpell(51713, path);
        if (!rogue->HasAura(dance))
            return;
        if (path == RoguePath::Celestial &&
            ((baseSpell == 8676 && damageType != DOT) || baseSpell == 703))
            damage = uint32(uint64(damage) * 80 / 100);
    }
};
}

void AddRoguePathSubtletyScripts()
{
    RegisterSpellScript(spell_cultivation_rogue_sha_honor);
    new RoguePathSubtletyUnitScript();
    new RoguePathSubtletyDamageScript();
}
}
