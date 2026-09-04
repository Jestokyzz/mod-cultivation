#ifndef MOD_CULTIVATION_ROGUE_H
#define MOD_CULTIVATION_ROGUE_H

#include "Define.h"
#include "RoguePathSevenBalance.h"

#include <string>
#include <unordered_map>
#include <unordered_set>
#include <string_view>
#include <mutex>

class Player;

namespace Cultivation::Rogue
{
enum class RoguePath : uint8
{
    None = 0,
    Celestial = 1,
    Sha = 2
};

struct Config
{
#define RP_BALANCE_FIELD(name, key, value, low, high) int32 name = value;
    CULTIVATION_ROGUE_SEVEN_BALANCE(RP_BALANCE_FIELD)
#undef RP_BALANCE_FIELD
    bool enable = true;
    uint8 minLevel = 80;
    bool allowPlayerCommand = true;
    bool allowSwitching = true;
    bool allowInCombat = false;
    bool allowInBattleground = false;
    bool allowInArena = false;
    bool debugLog = false;

    uint8 shaKidneyPvEDamagePct = 15;
    uint8 shaShadowDancePvEDamagePct = 30;
    uint8 shaEnvenomDetonationPct = 40;
    uint32 shaVanishCooldownReductionMs = 45000;
    uint8 shaBladeFlurryHastePct = 50;
    uint8 shaKillingSpreeAttackCount = 7;
    uint8 celestialTricksDamagePct = 10;
    uint8 celestialTricksDurationSeconds = 10;
    uint8 shaTricksDamagePct = 25;
    uint8 shaTricksDurationSeconds = 4;
    uint8 shaBloodThrillDirectDamagePct = 8;
    uint8 shaBloodThrillIncomingDamagePct = 8;
    uint8 shaBloodThrillEnergyRegenPct = 20;
    uint32 shaBloodThrillInternalCooldownMs = 20000;
};

Config GetConfig();
void LoadConfig();
bool IsDataValid();
void SetDataValid(bool valid);

class SpellService
{
public:
    static SpellService& Instance();

    RoguePath GetPath(Player const* player) const;
    RoguePath LoadPath(Player* player);
    bool SetPath(Player* player, RoguePath path);
    void ForgetPlayer(Player const* player);

    bool SyncPlayerSpells(Player* player);
    void SyncVisibleTalentPassives(Player* player);
    bool RestoreStandardSpells(Player* player);
    bool ValidateMappings(std::string& error) const;
    bool IsGroupEnabled(std::string_view name) const;
    uint32 DisabledGroupCount() const;

    uint32 GetBaseSpell(uint32 anyVariantSpell) const;
    uint32 GetVariantSpell(uint32 baseSpell, RoguePath path) const;
    bool IsVariantSpell(uint32 spellId) const;
    bool IsSyncing(Player const* player) const;

    uint32 CountActiveVariants(Player const* player) const;
    uint32 CountPassiveVariants(Player const* player) const;
    void RemoveOppositePathAuras(Player* player, RoguePath path) const;

private:
    SpellService() = default;
    mutable std::recursive_mutex _stateMutex;
    std::unordered_map<uint32, RoguePath> _paths;
    std::unordered_map<uint32, uint32> _syncDepth;
    mutable std::unordered_set<std::string_view> _disabledGroups;
};

char const* PathNameRu(RoguePath path);
char const* PathNameEn(RoguePath path);
}

#define sCultivationRogueSpellService Cultivation::Rogue::SpellService::Instance()

#endif
