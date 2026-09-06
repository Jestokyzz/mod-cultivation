#include "Cultivation.h"

namespace Cultivation::Rogue
{
void AddRoguePathPlayerScripts();
void AddRoguePathCommonSpellScripts();
void AddRoguePathAssassinationScripts();
void AddRoguePathCombatScripts();
void AddRoguePathSubtletyScripts();
void AddRoguePathSevenScripts();
void AddRogueMentorScripts();
}

namespace Cultivation
{
void AddRogueSubsystemScripts()
{
    Rogue::AddRoguePathPlayerScripts();
    Rogue::AddRogueMentorScripts();
    Rogue::AddRoguePathCommonSpellScripts();
    Rogue::AddRoguePathAssassinationScripts();
    Rogue::AddRoguePathSubtletyScripts();
    Rogue::AddRoguePathSevenScripts();
    // Blade Flurry copies the final post-specialization direct damage, so its
    // modifier must run after the Assassination/Subtlety damage modifiers.
    Rogue::AddRoguePathCombatScripts();
}
}
