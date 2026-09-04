#ifndef MOD_CULTIVATION_ROGUE_SEVEN_BALANCE_H
#define MOD_CULTIVATION_ROGUE_SEVEN_BALANCE_H

// One declaration drives the cached fields and ConfigMgr loading. No per-hit config I/O.
#define CULTIVATION_ROGUE_SEVEN_BALANCE(X) \
    X(shaDirectCapPvE, "Sha.DirectDamageBonusCapPvE", 60, 0, 500) \
    X(celCheapCost, "Celestial.CheapShot.CostReduction", 10, 0, 100) \
    X(celCheapDuration, "Celestial.CheapShot.DurationBonusMs", 500, 0, 10000) \
    X(celCheapCP, "Celestial.CheapShot.ComboPoints", 3, 0, 5) \
    X(shaCheapCost, "Sha.CheapShot.CostReduction", 20, 0, 100) \
    X(shaCheapPvEMs, "Sha.CheapShot.PvEDurationMs", 3000, 1, 60000) \
    X(shaCheapPvE, "Sha.CheapShot.PvEDamagePct", 10, 0, 100) \
    X(celBackstabCost, "Celestial.Backstab.ControlCostReduction", 10, 0, 100) \
    X(celBackstabPenalty, "Celestial.Backstab.DamagePenaltyPct", 10, 0, 100) \
    X(celBackstabCP, "Celestial.Backstab.ComboPoints", 2, 0, 5) \
    X(celBackstabEnergy, "Celestial.Backstab.ControlEnergyReturn", 10, 0, 100) \
    X(shaBackstabCost, "Sha.Backstab.CostIncrease", 0, 0, 100) \
    X(shaBackstabPvE, "Sha.Backstab.PvEDamagePct", 30, 0, 100) \
    X(shaBackstabCritPvE, "Sha.Backstab.PvECritDamagePct", 20, 0, 100) \
    X(shaBlindCD, "Sha.Blind.CooldownReductionMs", 60000, 0, 180000) \
    X(shaBlindPvEMs, "Sha.Blind.PvEDurationMs", 5000, 1, 60000) \
    X(celFallSpeed, "Celestial.SafeFall.SpeedPct", 30, 0, 200) \
    X(celFallSpeedMs, "Celestial.SafeFall.SpeedDurationMs", 4000, 1, 60000) \
    X(celFallKnockMs, "Celestial.SafeFall.KnockbackImmunityMs", 2000, 1, 60000) \
    X(celFallICD, "Celestial.SafeFall.InternalCooldownMs", 10000, 1, 300000) \
    X(shaFallReduction, "Sha.SafeFall.DamageReductionPct", 70, 0, 100) \
    X(shaFallThreshold, "Sha.SafeFall.TriggerHealthPct", 10, 0, 100) \
    X(shaFallEnergy, "Sha.SafeFall.EnergyGain", 30, 0, 100) \
    X(shaFallOpenerMs, "Sha.SafeFall.OpenerDurationMs", 5000, 1, 60000) \
    X(shaFallPvE, "Sha.SafeFall.PvEDamagePct", 20, 0, 100) \
    X(shaFallICD, "Sha.SafeFall.InternalCooldownMs", 20000, 1, 300000) \
    X(shaSapCost, "Sha.Sap.CostIncrease", 0, 0, 100) \
    X(shaSapPvEMs, "Sha.Sap.PvEDurationMs", 6000, 1, 60000) \
    X(shaSapCP, "Sha.Sap.ComboPoints", 2, 0, 5) \
    X(shaSapICD, "Sha.Sap.TargetInternalCooldownMs", 10000, 1, 300000) \
    X(celGhostCost, "Celestial.GhostlyStrike.CostReduction", 10, 0, 100) \
    X(celGhostPenalty, "Celestial.GhostlyStrike.DamagePenaltyPct", 20, 0, 100) \
    X(celGhostDodge, "Celestial.GhostlyStrike.DodgePct", 30, 0, 100) \
    X(celGhostMs, "Celestial.GhostlyStrike.DurationMs", 10000, 1, 60000) \
    X(celGhostEnergy, "Celestial.GhostlyStrike.DodgeEnergyGain", 20, 0, 100) \
    X(shaGhostCost, "Sha.GhostlyStrike.CostIncrease", 10, 0, 100) \
    X(shaGhostCD, "Sha.GhostlyStrike.CooldownMs", 15000, 1, 300000) \
    X(shaGhostPvE, "Sha.GhostlyStrike.PvEDamagePct", 40, 0, 100) \
    X(shaGhostCP, "Sha.GhostlyStrike.ComboPoints", 2, 0, 5) \
    X(shaGhostHaste, "Sha.GhostlyStrike.AttackSpeedPct", 20, 0, 200) \
    X(shaGhostArmor, "Sha.GhostlyStrike.ArmorPenaltyPct", 20, 0, 100) \
    X(shaGhostMs, "Sha.GhostlyStrike.EffectDurationMs", 6000, 1, 60000) \
    X(celShivCost, "Celestial.Shiv.CostReduction", 10, 0, 100) \
    X(celShivPenalty, "Celestial.Shiv.WeaponDamagePenaltyPct", 0, 0, 100) \
    X(shaShivCost, "Sha.Shiv.CostIncrease", 15, 0, 100) \
    X(shaShivSecondPct, "Sha.Shiv.SecondHitDamagePct", 50, 0, 100) \
    X(shaShivPoisonPvE, "Sha.Shiv.PvEPoisonDamagePct", 20, 0, 20) \
    X(shaShivWindowMs, "Sha.Shiv.PoisonWindowMs", 4000, 1, 60000) \
    X(shaShivRegenPenalty, "Sha.Shiv.EnergyRegenPenaltyPct", 20, 0, 100) \
    X(shaShivPenaltyMs, "Sha.Shiv.EnergyRegenPenaltyMs", 3000, 1, 60000)

#endif
