#ifndef MOD_CULTIVATION_ROGUE_COMMAND_H
#define MOD_CULTIVATION_ROGUE_COMMAND_H

#include <string_view>

class ChatHandler;

namespace Cultivation::Rogue
{
bool HandleCultivationCommand(ChatHandler* handler, std::string_view arguments);
}

#endif
