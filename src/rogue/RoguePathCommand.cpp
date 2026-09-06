#include "CultivationRogue.h"
#include "RogueCommand.h"
#include "RoguePathMechanics.h"

#include "Chat.h"
#include "Player.h"
#include "WorldSession.h"
#include "Creature.h"
#include "ScriptMgr.h"
#include "ScriptedGossip.h"
#include "generated/RoguePathGeneratedSpells.h"

#include <string>
#include <string_view>

namespace Cultivation::Rogue
{
namespace
{
bool IsRussian(ChatHandler* handler)
{
    return handler && handler->GetSession() && handler->GetSession()->GetSessionDbLocaleIndex() == LOCALE_ruRU;
}

void Send(ChatHandler* handler, char const* russian, char const* english)
{
    handler->SendSysMessage(IsRussian(handler) ? russian : english);
}

std::string Trimmed(std::string_view value)
{
    std::size_t first = value.find_first_not_of(" \t\r\n");
    if (first == std::string_view::npos)
        return {};
    std::size_t last = value.find_last_not_of(" \t\r\n");
    return std::string(value.substr(first, last - first + 1));
}

bool CheckChangeAllowed(ChatHandler* handler, Player* player, RoguePath requested, bool byCommand = true)
{
    Config const& config = GetConfig();
    if (!config.enable || !IsDataValid())
    {
        Send(handler, "Модуль путей разбойника отключён или не прошёл проверку данных.",
            "Cultivation / Rogue is disabled or failed data validation.");
        return false;
    }
    if (byCommand && !config.allowPlayerCommand)
    {
        Send(handler, "Выбор пути командой отключён.", "Path selection by command is disabled.");
        return false;
    }
    if (!player->IsClass(CLASS_ROGUE, CLASS_CONTEXT_ABILITY))
    {
        Send(handler, "Эта команда доступна только разбойникам.", "This command is available only to rogues.");
        return false;
    }
    if (player->GetLevel() < config.minLevel)
    {
        handler->PSendSysMessage(IsRussian(handler) ? "Для выбора пути требуется {}-й уровень." :
            "Selecting a path requires level {}.", config.minLevel);
        return false;
    }
    if (!player->IsAlive())
    {
        Send(handler, "Нельзя менять путь, пока персонаж мёртв.", "You cannot change paths while dead.");
        return false;
    }
    if (!config.allowInCombat && player->IsInCombat())
    {
        Send(handler, "Нельзя менять путь во время боя.", "You cannot change paths during combat.");
        return false;
    }
    if (!config.allowInArena && player->InArena())
    {
        Send(handler, "Нельзя менять путь на арене.", "You cannot change paths in an arena.");
        return false;
    }
    if (!config.allowInBattleground && player->InBattleground())
    {
        Send(handler, "Нельзя менять путь на поле боя.", "You cannot change paths in a battleground.");
        return false;
    }
    if (player->IsBeingTeleported())
    {
        Send(handler, "Нельзя менять путь во время телепортации.", "You cannot change paths while teleporting.");
        return false;
    }
    if (player->IsInFlight() || player->HasUnitMovementFlag(MOVEMENTFLAG_FALLING | MOVEMENTFLAG_FALLING_FAR))
    {
        Send(handler, "Нельзя менять или сбрасывать путь во время падения или полёта на такси.",
            "You cannot change or reset your path while falling or on a taxi.");
        return false;
    }
    RoguePath current = sCultivationRogueSpellService.GetPath(player);
    if (!config.allowSwitching && current != RoguePath::None && requested != current)
    {
        Send(handler, "Смена уже выбранного пути отключена.", "Switching an existing path is disabled.");
        return false;
    }
    return true;
}
}

bool HandleCultivationCommand(ChatHandler* handler, std::string_view arguments)
{
        Player* player = handler->GetSession() ? handler->GetSession()->GetPlayer() : nullptr;
        if (!player)
            return false;

        std::string command = Trimmed(arguments);
        if (command == "testshadowstep")
            return Mechanics::RunShadowstepRegression(player, handler);
        if (command == "testcelestial")
            return Mechanics::RunCelestialRegression(player, handler);
        if (command == "testresources")
            return Mechanics::RunCelestialResourceRegression(player, handler);
        if (command == "testshasinister")
            return Mechanics::RunShaSinisterRegression(player, handler);
        if (command == "testsha41")
            return Mechanics::RunShaCandidate41Regression(player, handler);
        if (command == "status")
        {
            RoguePath path = sCultivationRogueSpellService.GetPath(player);
            if (IsRussian(handler))
                handler->PSendSysMessage("Текущий путь: {}. Активных навыков: {}. Пассивок: {}. Версия синхронизации: {}.",
                    PathNameRu(path), sCultivationRogueSpellService.CountActiveVariants(player),
                    sCultivationRogueSpellService.CountPassiveVariants(player), Generated::SynchronizationSchemaVersion);
            else
                handler->PSendSysMessage("Current path: {}. Active variants: {}. Passive variants: {}. Sync schema: {}.",
                    PathNameEn(path), sCultivationRogueSpellService.CountActiveVariants(player),
                    sCultivationRogueSpellService.CountPassiveVariants(player), Generated::SynchronizationSchemaVersion);
            return true;
        }
        if (command == "sync")
        {
            if (!player->IsClass(CLASS_ROGUE, CLASS_CONTEXT_ABILITY))
            {
                Send(handler, "Эта команда доступна только разбойникам.", "This command is available only to rogues.");
                return true;
            }
            if (!sCultivationRogueSpellService.SyncPlayerSpells(player))
                Send(handler, "Синхронизация не выполнена: проверьте конфигурацию и клиентские данные.",
                    "Synchronization failed: check configuration and client data.");
            else
                Send(handler, "Синхронизация навыков завершена.", "Spell synchronization completed.");
            return true;
        }

        RoguePath requested = RoguePath::None;
        if (command == "celestial" || command == "nebozhitel" || command == "небожитель")
            requested = RoguePath::Celestial;
        else if (command == "sha" || command == "ша")
            requested = RoguePath::Sha;
        else if (command != "reset")
        {
            Send(handler, "Использование: .cultivation rogue celestial|nebozhitel|небожитель|sha|ша|status|sync|reset",
                "Usage: .cultivation rogue celestial|nebozhitel|sha|status|sync|reset");
            return true;
        }

        if (!CheckChangeAllowed(handler, player, requested))
            return true;
        if (!sCultivationRogueSpellService.SetPath(player, requested))
        {
            Send(handler, "Не удалось применить путь. Изменения стандартных навыков не выполнены.",
                "The path could not be applied. Standard spells were left unchanged.");
            return true;
        }

        if (requested == RoguePath::Celestial)
            Send(handler, "Вы выбрали путь Небожителя. Стандартные навыки разбойника заменены версиями пути Небожителя.",
                "You selected the Celestial path. Standard rogue abilities were replaced with Celestial variants.");
        else if (requested == RoguePath::Sha)
            Send(handler, "Вы выбрали путь Ша. Стандартные навыки разбойника заменены версиями пути Ша.",
                "You selected the Sha path. Standard rogue abilities were replaced with Sha variants.");
        else
            Send(handler, "Путь сброшен. Стандартные навыки разбойника восстановлены.",
                "The path was reset. Standard rogue abilities were restored.");
        return true;
}

class CultivationRogueMentor final : public CreatureScript
{
public:
    CultivationRogueMentor() : CreatureScript("npc_cultivation_rogue_mentor") { }

    static RoguePath PathFor(Creature const* creature)
    {
        if (creature->GetEntry() == 900703) return RoguePath::Sha;
        if (creature->GetEntry() == 900704) return RoguePath::Celestial;
        return RoguePath::None;
    }

    bool OnGossipHello(Player* player, Creature* creature) override
    {
        auto path = PathFor(creature);
        if (path == RoguePath::None) return false;
        ClearGossipMenuFor(player);
        AddGossipItemFor(player, GOSSIP_ICON_CHAT,
            path == RoguePath::Sha ? "Изучить: Ша" : "Изучить: Небожители",
            GOSSIP_SENDER_MAIN, GOSSIP_ACTION_INFO_DEF + static_cast<uint32>(path));
        SendGossipMenuFor(player, DEFAULT_GOSSIP_MESSAGE, creature->GetGUID());
        return true;
    }

    bool OnGossipSelect(Player* player, Creature* creature, uint32 sender, uint32 action) override
    {
        auto path = PathFor(creature);
        if (path == RoguePath::None || sender != GOSSIP_SENDER_MAIN ||
            action != GOSSIP_ACTION_INFO_DEF + static_cast<uint32>(path) ||
            player->PlayerTalkClass->GetGossipMenu().GetSenderGUID() != creature->GetGUID() ||
            !player->IsWithinDistInMap(creature, INTERACTION_DISTANCE))
            return false;
        ClearGossipMenuFor(player);
        CloseGossipMenuFor(player);
        ChatHandler handler(player->GetSession());
        if (!CheckChangeAllowed(&handler, player, path, false)) return true;
        if (!sCultivationRogueSpellService.SetPath(player, path))
        {
            Send(&handler, "Не удалось принять культивацию.", "Could not accept cultivation.");
            return true;
        }
        Send(&handler, "Культивация изучена.", "Cultivation learned.");
        return true;
    }
};

void AddRogueMentorScripts() { new CultivationRogueMentor(); }
}
