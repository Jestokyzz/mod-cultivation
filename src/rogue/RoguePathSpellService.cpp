#include "CultivationRogue.h"
#include "RoguePathMechanics.h"

#include "CharacterDatabase.h"
#include "DBCStores.h"
#include "GameTime.h"
#include "Log.h"
#include "Player.h"
#include "ObjectMgr.h"
#include "ScriptMgr.h"
#include "SpellScriptLoader.h"
#include "SpellInfo.h"
#include "SpellMgr.h"
#include "Timer.h"
#include "WorldPacket.h"
#include "generated/RoguePathGeneratedSpells.h"

#include <algorithm>
#include <array>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace Cultivation::Rogue
{
namespace
{
constexpr uint16 SynchronizationSchemaVersion = Generated::SynchronizationSchemaVersion;

bool IsPersistentCooldown(uint32 id)
{
    return std::find(Generated::PersistentCooldownSpells.begin(), Generated::PersistentCooldownSpells.end(), id) !=
        Generated::PersistentCooldownSpells.end();
}

bool IsTalentAvailable(Player const* player, Generated::SpellVariantRow const& row)
{
    if (row.passive)
        return player->HasTalent(row.baseSpell, player->GetActiveSpec());
    SpellInfo const* info = sSpellMgr->GetSpellInfo(row.baseSpell);
    uint32 firstRank = sSpellMgr->GetFirstSpellInChain(row.baseSpell);
    return info && info->SpellLevel <= player->GetLevel() &&
        player->HasTalent(firstRank ? firstRank : row.baseSpell, player->GetActiveSpec());
}

bool IsRegularSpellAvailable(Player const* player, Generated::SpellVariantRow const& row)
{
    SpellInfo const* spellInfo = sSpellMgr->GetSpellInfo(row.baseSpell);
    return spellInfo && spellInfo->SpellLevel <= player->GetLevel() && player->IsSpellFitByClassAndRace(row.baseSpell);
}

bool IsAvailable(Player const* player, Generated::SpellVariantRow const& row)
{
    return row.talentGated ? IsTalentAvailable(player, row) : IsRegularSpellAvailable(player, row);
}

uint32 DestinationSpell(Generated::SpellVariantRow const& row, RoguePath path)
{
    switch (path)
    {
        case RoguePath::Celestial:
            return row.celestialSpell;
        case RoguePath::Sha:
            return row.shaSpell;
        default:
            return row.baseSpell;
    }
}

void TransferCooldown(Player* player, std::array<uint32, 3> const& sources, uint32 destination)
{
    SpellCooldowns& cooldowns = player->GetSpellCooldownMap();
    uint32 now = GameTime::GetGameTimeMS().count();
    bool found = false;
    SpellCooldown selected{};
    uint32 selectedRemaining = 0;

    for (uint32 source : sources)
    {
        auto itr = cooldowns.find(source);
        if (itr == cooldowns.end())
            continue;

        uint32 remaining = itr->second.end > now ? getMSTimeDiff(now, itr->second.end) : 0;
        if (!found || remaining > selectedRemaining)
        {
            selected = itr->second;
            selectedRemaining = remaining;
            found = true;
        }
    }

    if (!found)
        return;

    for (uint32 source : sources)
    {
        if (source == destination)
            continue;
        if (cooldowns.erase(source))
            player->SendClearCooldown(source, player);
    }

    selected.end = now + selectedRemaining;
    cooldowns[destination] = selected;
    if (selectedRemaining)
    {
        WorldPacket packet;
        player->BuildCooldownPacket(packet, SPELL_COOLDOWN_FLAG_NONE, destination, selectedRemaining);
        player->SendDirectMessage(&packet);
    }
}

struct CooldownTransfer
{
    std::array<uint32, 3> sources{};
    uint32 destination = 0;
    SpellCooldown selected{};
    uint32 remaining = 0;
};

bool CaptureCooldownTransfer(Player* player, std::array<uint32, 3> const& sources, uint32 destination,
    CooldownTransfer& result)
{
    SpellCooldowns const& cooldowns = player->GetSpellCooldownMap();
    uint32 now = GameTime::GetGameTimeMS().count();
    bool found = false;
    for (uint32 source : sources)
    {
        auto itr = cooldowns.find(source);
        if (itr == cooldowns.end())
            continue;
        uint32 remaining = itr->second.end > now ? getMSTimeDiff(now, itr->second.end) : 0;
        if (!found || remaining > result.remaining)
        {
            result.selected = itr->second;
            result.remaining = remaining;
            found = true;
        }
    }
    result.sources = sources;
    result.destination = destination;
    return found;
}

void RestoreCapturedCooldown(Player* player, CooldownTransfer const& transfer)
{
    SpellCooldowns& cooldowns = player->GetSpellCooldownMap();
    for (uint32 source : transfer.sources)
    {
        if (source == transfer.destination)
            continue;
        if (cooldowns.erase(source))
            player->SendClearCooldown(source, player);
    }
    SpellCooldown restored = transfer.selected;
    restored.end = GameTime::GetGameTimeMS().count() + transfer.remaining;
    cooldowns[transfer.destination] = restored;
    if (transfer.remaining)
    {
        WorldPacket packet;
        player->BuildCooldownPacket(packet, SPELL_COOLDOWN_FLAG_NONE, transfer.destination, transfer.remaining);
        player->SendDirectMessage(&packet);
    }
}

constexpr uint32 PreparationBaseSpell = 14185;
constexpr uint32 PreparationCelestialSpell = 86107;
constexpr uint32 PreparationShaSpell = 86307;

bool IsPreparationVariant(uint32 spellId)
{
    return spellId == PreparationBaseSpell || spellId == PreparationCelestialSpell || spellId == PreparationShaSpell;
}

void RememberSuppressedPreparationButton(Player* player, uint8 slot)
{
    CharacterDatabase.DirectExecute(
        "INSERT INTO `character_cultivation_rogue_suppressed_action` (`guid`,`spec`,`button`,`base_spell`) "
        "VALUES ({},{},{},{}) ON DUPLICATE KEY UPDATE `base_spell`=VALUES(`base_spell`), "
        "`updated_at`=CURRENT_TIMESTAMP",
        player->GetGUID().GetCounter(), player->GetActiveSpec(), slot, PreparationBaseSpell);
}

void ReplaceActionButtons(Player* player, std::unordered_map<uint32, uint32> const& replacements)
{
    bool changed = false;
    for (uint16 slot = 0; slot < MAX_ACTION_BUTTONS; ++slot)
    {
        ActionButton const* button = player->GetActionButton(uint8(slot));
        if (!button || button->GetType() != ACTION_BUTTON_SPELL)
            continue;

        auto itr = replacements.find(button->GetAction());
        if (itr == replacements.end())
            continue;

        if (itr->second)
            player->addActionButton(uint8(slot), itr->second, uint8(button->GetType()));
        else
        {
            // Celestial Preparation is deliberately passive and must not leave
            // a clickable action. Preserve its exact per-spec slot durably so
            // repeated path changes and relogs can restore the user's layout.
            if (IsPreparationVariant(button->GetAction()))
                RememberSuppressedPreparationButton(player, uint8(slot));
            player->removeActionButton(uint8(slot));
        }
        changed = true;
    }

    if (changed)
        player->SendActionButtons(1);
}

void RestoreSuppressedPreparationButtons(Player* player, uint32 destination)
{
    if (!player || !destination || !player->HasSpell(destination))
        return;

    QueryResult result = CharacterDatabase.Query(
        "SELECT `button` FROM `character_cultivation_rogue_suppressed_action` "
        "WHERE `guid`={} AND `spec`={} AND `base_spell`={} ORDER BY `button`",
        player->GetGUID().GetCounter(), player->GetActiveSpec(), PreparationBaseSpell);
    if (!result)
        return;

    bool changed = false;
    do
    {
        uint8 slot = result->Fetch()[0].Get<uint8>();
        ActionButton const* current = player->GetActionButton(slot);
        if (current)
        {
            // Never overwrite a button the player placed while Preparation was
            // passive. A matching button means restoration is already done.
            if (current->GetType() == ACTION_BUTTON_SPELL && current->GetAction() == destination)
                CharacterDatabase.DirectExecute(
                    "DELETE FROM `character_cultivation_rogue_suppressed_action` WHERE `guid`={} AND `spec`={} AND `button`={}",
                    player->GetGUID().GetCounter(), player->GetActiveSpec(), slot);
            continue;
        }
        if (!player->addActionButton(slot, destination, ACTION_BUTTON_SPELL))
            continue;
        CharacterDatabase.DirectExecute(
            "DELETE FROM `character_cultivation_rogue_suppressed_action` WHERE `guid`={} AND `spec`={} AND `button`={}",
            player->GetGUID().GetCounter(), player->GetActiveSpec(), slot);
        changed = true;
    } while (result->NextRow());

    if (changed)
        player->SendActionButtons(1);
}

void RemoveSpellFromActiveSpec(Player* player, uint32 spellId)
{
    // A path is character-wide. Skill-granted stock rank one can be TEMPORARY
    // with SPEC_MASK_ALL; removing only the active bit leaves a temporary entry
    // that _addSpell refuses to restore on reset. removeSpell does not remove
    // talent points from m_talents. Also clean entries left in inactive specs.
    player->removeSpell(spellId, SPEC_MASK_ALL, false);
}
}

SpellService& SpellService::Instance()
{
    static SpellService instance;
    return instance;
}

RoguePath SpellService::GetPath(Player const* player) const
{
    std::lock_guard<std::recursive_mutex> lock(_stateMutex);
    if (!player)
        return RoguePath::None;
    auto itr = _paths.find(player->GetGUID().GetCounter());
    return itr == _paths.end() ? RoguePath::None : itr->second;
}

RoguePath SpellService::LoadPath(Player* player)
{
    std::lock_guard<std::recursive_mutex> lock(_stateMutex);
    if (!player)
        return RoguePath::None;

    RoguePath path = RoguePath::None;
    if (QueryResult result = CharacterDatabase.Query(
        "SELECT `path`, `schema_version` FROM `character_cultivation_rogue` WHERE `guid` = {}", player->GetGUID().GetCounter()))
    {
        Field* fields = result->Fetch();
        uint8 rawPath = fields[0].Get<uint8>();
        uint16 schema = fields[1].Get<uint16>();
        if (rawPath <= uint8(RoguePath::Sha) && schema <= SynchronizationSchemaVersion)
            path = RoguePath(rawPath);
        else
        {
            LOG_ERROR("module", "mod-cultivation: invalid persisted state guid={} path={} schema={}",
                player->GetGUID().GetCounter(), rawPath, schema);
            SetDataValid(false); // Fail closed: never restore/remove spells from an unknown schema.
        }
    }

    if (!player->IsClass(CLASS_ROGUE, CLASS_CONTEXT_ABILITY))
        path = RoguePath::None;
    _paths[player->GetGUID().GetCounter()] = path;
    return path;
}

bool SpellService::SetPath(Player* player, RoguePath path)
{
    std::lock_guard<std::recursive_mutex> lock(_stateMutex);
    if (!player || uint8(path) > uint8(RoguePath::Sha) || !IsDataValid() || !GetConfig().enable ||
        !player->IsClass(CLASS_ROGUE, CLASS_CONTEXT_ABILITY) || player->IsInFlight() ||
        player->HasUnitMovementFlag(MOVEMENTFLAG_FALLING | MOVEMENTFLAG_FALLING_FAR))
        return false;

    RoguePath oldPath = GetPath(player);
    CharacterDatabase.DirectExecute(
        "INSERT INTO `character_cultivation_rogue` (`guid`, `path`, `schema_version`) VALUES ({}, {}, {}) "
        "ON DUPLICATE KEY UPDATE `path`=VALUES(`path`), `schema_version`=VALUES(`schema_version`), `updated_at`=CURRENT_TIMESTAMP",
        player->GetGUID().GetCounter(), uint8(path), SynchronizationSchemaVersion);
    QueryResult stored = CharacterDatabase.Query("SELECT `path`, `schema_version` FROM `character_cultivation_rogue` WHERE `guid` = {}",
        player->GetGUID().GetCounter());
    if (!stored || stored->Fetch()[0].Get<uint8>() != uint8(path) ||
        stored->Fetch()[1].Get<uint16>() != SynchronizationSchemaVersion)
    {
        LOG_ERROR("module", "mod-cultivation: persistence verification failed for guid={}; spellbook unchanged", player->GetGUID().GetCounter());
        return false;
    }
    _paths[player->GetGUID().GetCounter()] = path;
    if (oldPath != path)
    {
        Mechanics::CleanupSevenEffects(player);
        Mechanics::ResetRuntimeForPathChange(player);
    }
    return path == RoguePath::None ? RestoreStandardSpells(player) : SyncPlayerSpells(player);
}

void SpellService::ForgetPlayer(Player const* player)
{
    std::lock_guard<std::recursive_mutex> lock(_stateMutex);
    if (!player)
        return;
    uint32 guid = player->GetGUID().GetCounter();
    _paths.erase(guid);
    _syncDepth.erase(guid);
}

bool SpellService::IsSyncing(Player const* player) const
{
    std::lock_guard<std::recursive_mutex> lock(_stateMutex);
    if (!player)
        return false;
    auto itr = _syncDepth.find(player->GetGUID().GetCounter());
    return itr != _syncDepth.end() && itr->second != 0;
}

bool SpellService::SyncPlayerSpells(Player* player)
{
    std::lock_guard<std::recursive_mutex> lock(_stateMutex);
    if (!player || !GetConfig().enable || !IsDataValid() || !player->IsClass(CLASS_ROGUE, CLASS_CONTEXT_ABILITY))
        return false;

    Mechanics::RemoveRetiredCelestialAuras(player);
    RoguePath path = GetPath(player);
    if (path == RoguePath::None)
    {
        SyncVisibleTalentPassives(player);
        bool hasVariant = player->HasSpell(Generated::CelestialPathPassive) || player->HasSpell(Generated::ShaPathPassive);
        for (Generated::SpellVariantRow const& row : Generated::SpellVariants)
            hasVariant = hasVariant || player->HasSpell(row.celestialSpell) || player->HasSpell(row.shaSpell);
        return !hasVariant || RestoreStandardSpells(player);
    }

    uint32 guid = player->GetGUID().GetCounter();
    if (_syncDepth[guid]++)
    {
        --_syncDepth[guid];
        return true;
    }

    std::vector<CooldownTransfer> capturedCooldowns;
    for (Generated::SpellVariantRow const& row : Generated::SpellVariants)
    {
        if (!IsAvailable(player, row))
            continue;
        CooldownTransfer transfer;
        uint32 destination = DestinationSpell(row, IsGroupEnabled(row.logicalName) ? path : RoguePath::None);
        if (CaptureCooldownTransfer(player, { row.baseSpell, row.celestialSpell, row.shaSpell }, destination, transfer))
            capturedCooldowns.push_back(transfer);
    }

    std::unordered_map<uint32, uint32> actionReplacements;
    for (Generated::SpellVariantRow const& row : Generated::SpellVariants)
    {
        bool available = IsAvailable(player, row);
        uint32 destination = DestinationSpell(row, IsGroupEnabled(row.logicalName) ? path : RoguePath::None);
        if (available && !player->HasSpell(destination))
            player->learnSpell(destination, false, false);

        if (!row.passive)
        {
            for (uint32 source : { row.baseSpell, row.celestialSpell, row.shaSpell })
                actionReplacements[source] = available && !(path == RoguePath::Celestial && row.logicalName == "preparation") ? destination : 0;
            if (destination != row.baseSpell)
                RemoveSpellFromActiveSpec(player, row.baseSpell);
            if (destination != row.celestialSpell)
                RemoveSpellFromActiveSpec(player, row.celestialSpell);
            if (destination != row.shaSpell)
                RemoveSpellFromActiveSpec(player, row.shaSpell);
            if (!available)
                RemoveSpellFromActiveSpec(player, destination);
        }
        else
        {
            if (row.logicalName == "safe_fall" && destination != row.baseSpell)
                RemoveSpellFromActiveSpec(player, row.baseSpell);
            if (destination != row.celestialSpell)
                RemoveSpellFromActiveSpec(player, row.celestialSpell);
            if (destination != row.shaSpell)
                RemoveSpellFromActiveSpec(player, row.shaSpell);
            if (!available)
                RemoveSpellFromActiveSpec(player, destination);
            bool suppressOriginal = row.logicalName == "overkill" || row.logicalName == "combat_potency" ||
                row.logicalName == "cheat_death" ||
                (row.logicalName == "honor_among_thieves" && path == RoguePath::Sha);
            if (available && suppressOriginal && destination != row.baseSpell)
                player->RemoveAurasDueToSpell(row.baseSpell);
            else if (available && destination == row.baseSpell && !player->HasAura(row.baseSpell))
                player->CastSpell(player, row.baseSpell, true);
        }
    }

    uint32 pathPassive = path == RoguePath::Celestial ? Generated::CelestialPathPassive : Generated::ShaPathPassive;
    uint32 oppositePassive = path == RoguePath::Celestial ? Generated::ShaPathPassive : Generated::CelestialPathPassive;
    RemoveSpellFromActiveSpec(player, oppositePassive);
    if (!player->HasSpell(pathPassive))
        player->learnSpell(pathPassive, false, false);
    if (!player->HasAura(pathPassive))
        player->CastSpell(player, pathPassive, true);

    RemoveOppositePathAuras(player, path);
    SyncVisibleTalentPassives(player);
    Mechanics::SyncCelestialPreparationGlyph(player);
    for (CooldownTransfer const& transfer : capturedCooldowns)
        RestoreCapturedCooldown(player, transfer);
    ReplaceActionButtons(player, actionReplacements);
    if (path == RoguePath::Sha)
        RestoreSuppressedPreparationButtons(player, PreparationShaSpell);
    CharacterDatabase.Execute("UPDATE character_cultivation_rogue SET schema_version={} WHERE guid={} AND schema_version<{}",
        SynchronizationSchemaVersion, guid, SynchronizationSchemaVersion);
    --_syncDepth[guid];
    if (_syncDepth[guid] == 0)
        _syncDepth.erase(guid);
    return true;
}

void SpellService::SyncVisibleTalentPassives(Player* player)
{
    std::lock_guard<std::recursive_mutex> lock(_stateMutex);
    if (!player || !IsDataValid() || !player->IsClass(CLASS_ROGUE, CLASS_CONTEXT_ABILITY))
        return;
    uint32 guid = player->GetGUID().GetCounter();
    ++_syncDepth[guid]; // learn/remove callbacks must not recurse into full spell sync.
    RoguePath path = GetConfig().enable ? GetPath(player) : RoguePath::None;
    std::unordered_map<std::string_view, uint8> highest;
    for (auto const& row : Generated::DisplayPassives)
        if (row.path == uint8(path) && row.talentRequired && player->HasTalent(row.base, player->GetActiveSpec()))
            highest[row.logicalName] = std::max(highest[row.logicalName], row.rank);

    // Two phases: remove every obsolete display before granting the current one.
    // No action-bar, cooldown, standard talent or mechanic aura mutation here.
    std::unordered_set<uint32> wanted;
    for (auto const& row : Generated::DisplayPassives)
    {
        std::string_view group = row.logicalName == "stealth_mastery" ? "stealth" : row.logicalName;
        bool available = row.path == uint8(path) && IsGroupEnabled(group) &&
            sSpellMgr->GetSpellInfo(row.mechanic) &&
            (row.talentRequired ? (highest[row.logicalName] == row.rank &&
                player->HasTalent(row.base, player->GetActiveSpec()) && player->HasSpell(row.mechanic)) :
                player->HasSpell(path == RoguePath::Celestial ? Generated::CelestialPathPassive : Generated::ShaPathPassive));
        if (available)
            wanted.insert(row.spell);
        else if (player->HasSpell(row.spell))
            RemoveSpellFromActiveSpec(player, row.spell);
    }
    for (uint32 spell : wanted)
        if (!player->HasSpell(spell))
            player->learnSpell(spell, false, false);
    if (--_syncDepth[guid] == 0)
        _syncDepth.erase(guid);
}

bool SpellService::RestoreStandardSpells(Player* player)
{
    std::lock_guard<std::recursive_mutex> lock(_stateMutex);
    if (!player || !player->IsClass(CLASS_ROGUE, CLASS_CONTEXT_ABILITY))
        return false;

    uint32 guid = player->GetGUID().GetCounter();
    if (_syncDepth[guid]++)
    {
        --_syncDepth[guid];
        return true;
    }

    std::unordered_map<uint32, uint32> actionReplacements;
    for (Generated::SpellVariantRow const& row : Generated::SpellVariants)
    {
        bool available = IsAvailable(player, row);
        if ((!row.passive || row.logicalName == "safe_fall") && available && !player->HasSpell(row.baseSpell))
            player->learnSpell(row.baseSpell, false, false);

        if (!row.passive)
        {
            actionReplacements[row.celestialSpell] = available ? row.baseSpell : 0;
            actionReplacements[row.shaSpell] = available ? row.baseSpell : 0;
            TransferCooldown(player, { row.baseSpell, row.celestialSpell, row.shaSpell }, row.baseSpell);
        }
        RemoveSpellFromActiveSpec(player, row.celestialSpell);
        RemoveSpellFromActiveSpec(player, row.shaSpell);
        if (row.passive && available && player->HasSpell(row.baseSpell) && !player->HasAura(row.baseSpell))
            player->CastSpell(player, row.baseSpell, true);
    }

    RemoveSpellFromActiveSpec(player, Generated::CelestialPathPassive);
    RemoveSpellFromActiveSpec(player, Generated::ShaPathPassive);
    for (auto const& display : Generated::DisplayPassives)
        RemoveSpellFromActiveSpec(player, display.spell);
    player->RemoveAurasDueToSpell(63848);
    for (uint32 spellId : Generated::CelestialTechnicalSpells)
        if (!IsPersistentCooldown(spellId))
            player->RemoveAurasDueToSpell(spellId);
    for (uint32 spellId : Generated::ShaTechnicalSpells)
        if (!IsPersistentCooldown(spellId))
            player->RemoveAurasDueToSpell(spellId);
    ReplaceActionButtons(player, actionReplacements);
    RestoreSuppressedPreparationButtons(player, PreparationBaseSpell);
    --_syncDepth[guid];
    if (_syncDepth[guid] == 0)
        _syncDepth.erase(guid);
    return true;
}

bool SpellService::ValidateMappings(std::string& error) const
{
    std::lock_guard<std::recursive_mutex> lock(_stateMutex);
    _disabledGroups.clear();
    auto requireScript = [&error](uint32 spellId, std::string_view logical, char const* name)
    {
        std::vector<std::pair<SpellScriptLoader*, SpellScriptsContainer::iterator>> loaders;
        sScriptMgr->CreateSpellScriptLoaders(spellId, loaders);
        for (auto const& loader : loaders)
            if (loader.first->GetName() == name)
                return true;
        error = "missing registered/bound script " + std::string(name) + " for " + std::string(logical) +
            " Spell ID " + std::to_string(spellId);
        return false;
    };
    std::unordered_map<std::string_view, uint8> chainSizes;
    for (Generated::SpellVariantRow const& row : Generated::SpellVariants)
        ++chainSizes[row.logicalName];
    std::unordered_map<std::string_view, char const*> inherited = {
        {"vanish", "spell_rog_vanish"}, {"evasion", "spell_cultivation_rogue_evasion"},
        {"rupture", "spell_rog_rupture"}, {"killing_spree", "spell_rog_killing_spree"},
        {"tricks_of_the_trade", "spell_rog_tricks_of_the_trade"},
        {"cheat_death", "spell_rog_cheat_death"}, {"combat_potency", "spell_cultivation_rogue_combat_potency"}
    };
    std::unordered_set<uint32> seen;
    for (Generated::SpellVariantRow const& row : Generated::SpellVariants)
    {
        auto validateRow = [&]() -> bool
        {
        if (!sSpellMgr->GetSpellInfo(row.baseSpell))
        {
            error = "missing base Spell ID " + std::to_string(row.baseSpell) + " for " + std::string(row.logicalName);
            return false;
        }
        for (uint32 spellId : { row.celestialSpell, row.shaSpell })
        {
            if (!seen.insert(spellId).second)
            {
                error = "duplicate custom Spell ID " + std::to_string(spellId);
                return false;
            }
            if (!sSpellMgr->GetSpellInfo(spellId))
            {
                error = "missing custom Spell ID " + std::to_string(spellId) + " for " + std::string(row.logicalName);
                return false;
            }
            if (chainSizes[row.logicalName] > 1 && sSpellMgr->GetSpellInfo(spellId)->GetRank() != row.rank)
            {
                error = "invalid rank chain for " + std::string(row.logicalName) + " Spell ID " + std::to_string(spellId);
                return false;
            }
            if (!row.passive && !requireScript(spellId, row.logicalName, "spell_cultivation_rogue_active"))
                return false;
            auto script = inherited.find(row.logicalName);
            if (script != inherited.end() && !requireScript(spellId, row.logicalName, script->second))
                return false;
            if (row.logicalName == "shiv" && !requireScript(spellId, row.logicalName, "spell_cultivation_rogue_shiv"))
                return false;
            if (row.logicalName == "blind" && spellId == row.celestialSpell &&
                !requireScript(spellId, row.logicalName, "spell_cultivation_rogue_blind"))
                return false;
            if (row.logicalName == "honor_among_thieves" && spellId == row.shaSpell)
            {
                if (!requireScript(spellId, row.logicalName, "spell_cultivation_rogue_sha_honor"))
                    return false;
                SpellProcEntry const* proc = sSpellMgr->GetSpellProcEntry(spellId);
                if (!proc || !(proc->SpellPhaseMask & PROC_SPELL_PHASE_HIT) ||
                    !(proc->SpellTypeMask & PROC_SPELL_TYPE_DAMAGE) || !(proc->HitMask & PROC_EX_CRITICAL_HIT))
                {
                    error = "invalid hit-phase proc metadata for honor_among_thieves Spell ID " + std::to_string(spellId);
                    return false;
                }
            }
            SkillLineAbilityMapBounds bounds = sSpellMgr->GetSkillLineAbilityMapBounds(spellId);
            if (bounds.first == bounds.second)
            {
                error = "visible Spell ID absent from SkillLineAbility.dbc: " + std::to_string(spellId);
                return false;
            }
        }
        return true;
        };
        if (!validateRow())
        {
            _disabledGroups.insert(row.logicalName);
            LOG_ERROR("module", "mod-cultivation: replacement group {} disabled: {}. Stock spell retained/restored.", row.logicalName, error);
        }
    }
    for (auto const& row : Generated::DisplayPassives)
    {
        SpellInfo const* display = sSpellMgr->GetSpellInfo(row.spell);
        SpellInfo const* mechanic = sSpellMgr->GetSpellInfo(row.mechanic);
        SpellInfo const* iconSource = sSpellMgr->GetSpellInfo(row.iconSource);
        SkillLineAbilityMapBounds bounds = sSpellMgr->GetSkillLineAbilityMapBounds(row.spell);
        bool valid = seen.insert(row.spell).second && display && mechanic && iconSource &&
            display->IsPassive() && !(display->Attributes & SPELL_ATTR0_DO_NOT_DISPLAY) &&
            display->ManaCost == 0 && display->ManaCostPercentage == 0 && display->RecoveryTime == 0 &&
            display->CategoryRecoveryTime == 0 && display->StartRecoveryTime == 0 && display->ProcFlags == 0 &&
            display->SpellIconID == (row.iconId ? row.iconId : iconSource->SpellIconID) && display->ActiveIconID == iconSource->ActiveIconID &&
            bounds.first != bounds.second;
        if (display)
            for (auto const& effect : display->Effects)
                valid = valid && effect.Effect == 0;
        if (!valid)
        {
            std::string_view group = row.logicalName == "stealth_mastery" ? "stealth" : row.logicalName;
            _disabledGroups.insert(group);
            LOG_ERROR("module", "mod-cultivation: {} disabled: invalid display-only spell {} / mechanic {}", group, row.spell, row.mechanic);
        }
    }
    std::unordered_map<uint32, std::string_view> dependencies = {
        {Generated::CelestialCheapShotGuard, "cheap_shot"}, {Generated::ShaCheapShotMark, "cheap_shot"},
        {Generated::ShaOpenerArmor, "cheap_shot"}, {Generated::ShaBlindStrike, "blind"},
        {Generated::CelestialSafeFallSpeed, "safe_fall"}, {Generated::CelestialSafeFallKnockback, "safe_fall"},
        {Generated::ShaSafeFallDive, "safe_fall"}, {Generated::CelestialSafeFallIcd, "safe_fall"},
        {Generated::ShaSafeFallIcd, "safe_fall"}, {Generated::CelestialSapGuard, "sap"},
        {Generated::ShaSapIcd, "sap"}, {Generated::ShaSapStrike, "sap"},
        {Generated::CelestialGhostlyStrikeTracker, "ghostly_strike"}, {Generated::ShaGhostlyStrikeFury, "ghostly_strike"},
        {Generated::CelestialShivProtection, "shiv"}, {Generated::CelestialShivIcd, "shiv"},
        {Generated::ShaShivVulnerability, "shiv"}, {Generated::ShaShivRegenPenalty, "shiv"},
        {Generated::CelestialShivHit, "shiv"}, {Generated::ShaShivHit, "shiv"}, {Generated::ShaShivSecond, "shiv"},
        {Generated::ShaShadowstepPosition, "backstab"}, {Generated::ShaVanishEnergy, "vanish"}
    };
    auto requireTechnical = [&](uint32 spellId)
    {
        bool valid = sSpellMgr->GetSpellInfo(spellId) && seen.insert(spellId).second;
        if (valid && (spellId == Generated::CelestialShivHit || spellId == Generated::ShaShivHit || spellId == Generated::ShaShivSecond))
            valid = requireScript(spellId, "shiv", "spell_cultivation_rogue_shiv_component");
        if (valid && spellId == Generated::CelestialGhostlyStrikeTracker)
        {
            SpellProcEntry const* proc = sSpellMgr->GetSpellProcEntry(spellId);
            valid = requireScript(spellId, "ghostly_strike", "spell_cultivation_rogue_ghostly_dodge") && proc && (proc->HitMask & PROC_HIT_DODGE);
        }
        if (valid)
            return true;
        error = "invalid/missing technical spell or script/proc " + std::to_string(spellId);
        auto group = dependencies.find(spellId);
        if (group == dependencies.end())
            return false; // shared legacy technical dependency: fail globally, never remove stock spells
        _disabledGroups.insert(group->second);
        LOG_ERROR("module", "mod-cultivation: replacement group {} disabled: {}", group->second, error);
        return true;
    };
    for (uint32 spellId : Generated::CelestialTechnicalSpells)
        if (!requireTechnical(spellId))
        {
            error = "missing or duplicate Celestial technical Spell ID " + std::to_string(spellId);
            return false;
        }
    for (uint32 spellId : Generated::ShaTechnicalSpells)
        if (!requireTechnical(spellId))
        {
            error = "missing or duplicate Sha technical Spell ID " + std::to_string(spellId);
            return false;
        }
    return requireScript(Generated::CelestialFanOffhand, "fan_of_knives_offhand", "spell_cultivation_rogue_active") &&
        requireScript(Generated::ShaFanOffhand, "fan_of_knives_offhand", "spell_cultivation_rogue_active");
}

bool SpellService::IsGroupEnabled(std::string_view name) const
{
    std::lock_guard<std::recursive_mutex> lock(_stateMutex);
    return _disabledGroups.find(name) == _disabledGroups.end();
}

uint32 SpellService::DisabledGroupCount() const
{
    std::lock_guard<std::recursive_mutex> lock(_stateMutex);
    return uint32(_disabledGroups.size());
}

uint32 SpellService::GetBaseSpell(uint32 anyVariantSpell) const
{
    for (Generated::SpellVariantRow const& row : Generated::SpellVariants)
        if (anyVariantSpell == row.baseSpell || anyVariantSpell == row.celestialSpell || anyVariantSpell == row.shaSpell)
            return row.baseSpell;
    return anyVariantSpell;
}

uint32 SpellService::GetVariantSpell(uint32 baseSpell, RoguePath path) const
{
    for (Generated::SpellVariantRow const& row : Generated::SpellVariants)
        if (row.baseSpell == baseSpell)
            return DestinationSpell(row, path);
    return baseSpell;
}

bool SpellService::IsVariantSpell(uint32 spellId) const
{
    for (Generated::SpellVariantRow const& row : Generated::SpellVariants)
        if (spellId == row.celestialSpell || spellId == row.shaSpell)
            return true;
    return false;
}

uint32 SpellService::CountActiveVariants(Player const* player) const
{
    uint32 count = 0;
    for (Generated::SpellVariantRow const& row : Generated::SpellVariants)
        if (!row.passive && (player->HasSpell(row.celestialSpell) || player->HasSpell(row.shaSpell)))
            ++count;
    return count;
}

uint32 SpellService::CountPassiveVariants(Player const* player) const
{
    uint32 count = 0;
    for (Generated::SpellVariantRow const& row : Generated::SpellVariants)
        if (row.passive && (player->HasSpell(row.celestialSpell) || player->HasSpell(row.shaSpell)))
            ++count;
    return count;
}

void SpellService::RemoveOppositePathAuras(Player* player, RoguePath path) const
{
    if (!player)
        return;
    if (path == RoguePath::Celestial)
        for (uint32 spellId : Generated::ShaTechnicalSpells)
            if (!IsPersistentCooldown(spellId))
                player->RemoveAurasDueToSpell(spellId);
    if (path == RoguePath::Sha)
    {
        player->RemoveAurasDueToSpell(63848);
        for (uint32 spellId : Generated::CelestialTechnicalSpells)
            if (!IsPersistentCooldown(spellId))
                player->RemoveAurasDueToSpell(spellId);
    }
}

char const* PathNameRu(RoguePath path)
{
    switch (path)
    {
        case RoguePath::Celestial: return "Небожитель";
        case RoguePath::Sha: return "Ша";
        default: return "не выбран";
    }
}

char const* PathNameEn(RoguePath path)
{
    switch (path)
    {
        case RoguePath::Celestial: return "Celestial";
        case RoguePath::Sha: return "Sha";
        default: return "not selected";
    }
}
}
