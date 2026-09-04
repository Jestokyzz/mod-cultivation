#include "../src/RoguePathBalanceMath.h"
#include <cassert>
#include <iostream>
using namespace Cultivation::Rogue::BalanceMath;
int main()
{
    assert(EnergyCost(60, -10 - 15 - 40, 10) == 10);
    assert(EnergyCost(36, -10, 5) == 26);
    assert(EnergyCost(36, 15, 5) == 51);
    assert(DirectDamage(1000, 20 + 30 + 10 + 12, 60) == 1600);
    assert(DirectDamage(1000, 15 + 20 + 10 + 12, 40) == 1400);
    assert(DirectDamage(1000, 25, 60) == 1250);
    assert(!StrongerOpener(25, 20) && !StrongerOpener(25, 25));
    assert(StrongerOpener(25, 40));
    assert(PoisonBonus(20, 20, 20) == 40);
    assert(PoisonBonus(15, 15, 20) == 35);
    assert(PoisonBonus(0, 20, 0) == 20);
    assert(FallDamage(1000, 70) == 300);
    assert(FallDamage(1000, 100) == 0);
    assert(!DangerousFall(0, 10000, 10));
    assert(!DangerousFall(999, 10000, 10));
    assert(DangerousFall(1000, 10000, 10));
    assert(GhostDodge(30, 0) == 30 && GhostDodge(30, 50) == 0);
    assert(GhostDodge(30, 15) == 15);
    std::cout << "PASS: 18 shared runtime balance assertions\n";
}
