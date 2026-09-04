#if defined(_WIN32) && !defined(_WIN32_WINNT)
#define _WIN32_WINNT 0x0601
#endif
#include "CultivationRogue.h"

#include "Config.h"
#include "Log.h"

#include <algorithm>
#include <atomic>
#include <mutex>

namespace Cultivation::Rogue
{
namespace
{
Config Settings;
std::mutex SettingsMutex;
std::atomic<bool> DataValid{false};

template <typename T>
T Bounded(std::string const& key, T defaultValue, T minimum, T maximum)
{
    T value = sConfigMgr->GetOption<T>(key, defaultValue);
    return std::clamp(value, minimum, maximum);
}
}

Config GetConfig()
{
    std::lock_guard<std::mutex> lock(SettingsMutex);
    return Settings;
}

bool IsDataValid()
{
    return DataValid;
}

void SetDataValid(bool valid)
{
    DataValid = valid;
}

void LoadConfig()
{
    std::lock_guard<std::mutex> lock(SettingsMutex);
    Settings.enable = sConfigMgr->GetOption<bool>("Cultivation.Rogue.Enable", true);
#define RP_BALANCE_LOAD(name, key, value, low, high) Settings.name = Bounded<int32>("Cultivation.Rogue." key, value, low, high);
    CULTIVATION_ROGUE_SEVEN_BALANCE(RP_BALANCE_LOAD)
#undef RP_BALANCE_LOAD
    Settings.minLevel = Bounded<uint8>("Cultivation.Rogue.MinLevel", 80, 1, 80);
    Settings.allowPlayerCommand = sConfigMgr->GetOption<bool>("Cultivation.Rogue.AllowPlayerCommand", true);
    Settings.allowSwitching = sConfigMgr->GetOption<bool>("Cultivation.Rogue.AllowSwitching", true);
    Settings.allowInCombat = sConfigMgr->GetOption<bool>("Cultivation.Rogue.AllowInCombat", false);
    Settings.allowInBattleground = sConfigMgr->GetOption<bool>("Cultivation.Rogue.AllowInBattleground", false);
    Settings.allowInArena = sConfigMgr->GetOption<bool>("Cultivation.Rogue.AllowInArena", false);
    Settings.debugLog = sConfigMgr->GetOption<bool>("Cultivation.Rogue.DebugLog", false);

    Settings.shaKidneyPvEDamagePct = Bounded<uint8>("Cultivation.Rogue.Sha.KidneyShot.PvEDamagePct", 15, 0, 100);
    Settings.shaShadowDancePvEDamagePct = Bounded<uint8>("Cultivation.Rogue.Sha.ShadowDance.PvEDamagePct", 30, 0, 100);
    Settings.shaEnvenomDetonationPct = Bounded<uint8>("Cultivation.Rogue.Sha.Envenom.DetonationPct", 40, 0, 100);
    Settings.shaVanishCooldownReductionMs = Bounded<uint32>("Cultivation.Rogue.Sha.Vanish.CooldownReductionMs", 45000, 0, 120000);
    Settings.shaBladeFlurryHastePct = Bounded<uint8>("Cultivation.Rogue.Sha.BladeFlurry.HastePct", 50, 0, 100);
    Settings.shaKillingSpreeAttackCount = Bounded<uint8>("Cultivation.Rogue.Sha.KillingSpree.AttackCount", 7, 1, 20);
    Settings.celestialTricksDamagePct = Bounded<uint8>("Cultivation.Rogue.Celestial.Tricks.DamagePct", 10, 0, 100);
    Settings.celestialTricksDurationSeconds = Bounded<uint8>("Cultivation.Rogue.Celestial.Tricks.DurationSeconds", 10, 1, 60);
    Settings.shaTricksDamagePct = Bounded<uint8>("Cultivation.Rogue.Sha.Tricks.DamagePct", 25, 0, 100);
    Settings.shaTricksDurationSeconds = Bounded<uint8>("Cultivation.Rogue.Sha.Tricks.DurationSeconds", 4, 1, 60);
    Settings.shaBloodThrillDirectDamagePct = Bounded<uint8>("Cultivation.Rogue.Sha.BloodThrill.DirectDamagePct", 8, 0, 100);
    Settings.shaBloodThrillIncomingDamagePct = Bounded<uint8>("Cultivation.Rogue.Sha.BloodThrill.IncomingDamagePct", 8, 0, 100);
    Settings.shaBloodThrillEnergyRegenPct = Bounded<uint8>("Cultivation.Rogue.Sha.BloodThrill.EnergyRegenPct", 20, 0, 200);
    Settings.shaBloodThrillInternalCooldownMs = Bounded<uint32>("Cultivation.Rogue.Sha.BloodThrill.InternalCooldownMs", 20000, 0, 300000);

    LOG_INFO("module", "mod-cultivation: config loaded (enabled={}, minLevel={})", Settings.enable, Settings.minLevel);
}
}
