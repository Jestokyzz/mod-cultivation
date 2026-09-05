#include "Cultivation.h"
#include "RogueCommand.h"

#include "Chat.h"
#include "CommandScript.h"

#include <string_view>

using namespace Acore::ChatCommands;

namespace Cultivation
{
namespace
{
constexpr uint32 RBAC_PERMISSION_CULTIVATION = 1001;

bool RunRogue(ChatHandler* handler, std::string_view action)
{
    return Rogue::HandleCultivationCommand(handler, action);
}

bool HandleCelestial(ChatHandler* handler) { return RunRogue(handler, "celestial"); }
bool HandleNebozhitel(ChatHandler* handler) { return RunRogue(handler, "nebozhitel"); }
bool HandleNebozhitelRu(ChatHandler* handler) { return RunRogue(handler, "небожитель"); }
bool HandleSha(ChatHandler* handler) { return RunRogue(handler, "sha"); }
bool HandleShaRu(ChatHandler* handler) { return RunRogue(handler, "ша"); }
bool HandleStatus(ChatHandler* handler) { return RunRogue(handler, "status"); }
bool HandleSync(ChatHandler* handler) { return RunRogue(handler, "sync"); }
bool HandleReset(ChatHandler* handler) { return RunRogue(handler, "reset"); }
bool HandleTestCelestial(ChatHandler* handler) { return RunRogue(handler, "testcelestial"); }
bool HandleTestResources(ChatHandler* handler) { return RunRogue(handler, "testresources"); }
bool HandleTestShaSinister(ChatHandler* handler) { return RunRogue(handler, "testshasinister"); }
bool HandleTestSha41(ChatHandler* handler) { return RunRogue(handler, "testsha41"); }
bool HandleTestShadowstep(ChatHandler* handler) { return RunRogue(handler, "testshadowstep"); }

bool HandleUsage(ChatHandler* handler)
{
    handler->SendSysMessage("Usage: .cultivation rogue celestial|nebozhitel|небожитель|sha|ша|status|sync|reset");
    return true;
}

class CultivationCommandScript : public CommandScript
{
public:
    CultivationCommandScript() : CommandScript("CultivationCommandScript") { }

    ChatCommandTable GetCommands() const override
    {
        static ChatCommandTable rogueCommandTable =
        {
            { "celestial",      HandleCelestial,      RBAC_PERMISSION_CULTIVATION, Console::No },
            { "nebozhitel",     HandleNebozhitel,     RBAC_PERMISSION_CULTIVATION, Console::No },
            { "небожитель",     HandleNebozhitelRu,   RBAC_PERMISSION_CULTIVATION, Console::No },
            { "sha",            HandleSha,            RBAC_PERMISSION_CULTIVATION, Console::No },
            { "ша",             HandleShaRu,          RBAC_PERMISSION_CULTIVATION, Console::No },
            { "status",         HandleStatus,         RBAC_PERMISSION_CULTIVATION, Console::No },
            { "sync",           HandleSync,           RBAC_PERMISSION_CULTIVATION, Console::No },
            { "reset",          HandleReset,          RBAC_PERMISSION_CULTIVATION, Console::No },
            { "testcelestial",  HandleTestCelestial,  RBAC_PERMISSION_CULTIVATION, Console::No },
            { "testresources",  HandleTestResources,  RBAC_PERMISSION_CULTIVATION, Console::No },
            { "testshasinister",HandleTestShaSinister,RBAC_PERMISSION_CULTIVATION, Console::No },
            { "testsha41",      HandleTestSha41,      RBAC_PERMISSION_CULTIVATION, Console::No },
            { "testshadowstep", HandleTestShadowstep, RBAC_PERMISSION_CULTIVATION, Console::No },
            { "",               HandleUsage,          RBAC_PERMISSION_CULTIVATION, Console::No }
        };

        static ChatCommandTable cultivationCommandTable =
        {
            { "rogue", rogueCommandTable },
            { "",      HandleUsage, RBAC_PERMISSION_CULTIVATION, Console::No }
        };

        static ChatCommandTable commandTable =
        {
            { "cultivation", cultivationCommandTable }
        };
        return commandTable;
    }
};
}

void AddCommandScripts()
{
    new CultivationCommandScript();
}
}
