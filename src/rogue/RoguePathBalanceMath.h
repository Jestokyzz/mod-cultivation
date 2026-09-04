#ifndef CULTIVATION_ROGUE_BALANCE_MATH_H
#define CULTIVATION_ROGUE_BALANCE_MATH_H
#include <algorithm>
#include <cstdint>

namespace Cultivation::Rogue::BalanceMath
{
constexpr bool StrongerOpener(int current, int candidate) { return candidate > current; }
constexpr int EnergyCost(int nativeCost, int delta, int floor) { return std::max(floor, nativeCost + delta); }
constexpr std::int32_t DirectDamage(std::int32_t damage, int additiveBonus, int cap)
{
    return std::int32_t(std::int64_t(damage) * (100 + std::min(additiveBonus, cap)) / 100);
}
constexpr int PoisonBonus(int masterPoisoner, int shiv, int cloak)
{
    return std::max(masterPoisoner, shiv) + cloak;
}
constexpr std::uint32_t FallDamage(std::uint32_t raw, int reduction)
{
    return std::uint32_t(std::uint64_t(raw) * (100 - reduction) / 100);
}
constexpr bool DangerousFall(std::uint32_t raw, std::uint32_t maxHealth, int threshold)
{
    return raw && std::uint64_t(raw) * 100 >= std::uint64_t(maxHealth) * threshold;
}
constexpr int GhostDodge(int ghost, int evasion) { return std::max(0, ghost - evasion); }
}
#endif
