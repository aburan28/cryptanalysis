#pragma once
#include <algorithm>
#include <cstdint>
#include <limits>
#include <vector>

struct MonomialOrderStats {
  uint64_t calls = 0, terms = 0, key_calls = 0, key_terms = 0;
  uint64_t comparison_calls = 0, comparison_terms = 0;
  uint64_t disabled_calls = 0, small_calls = 0, wide_calls = 0, overflow = 0;
};
static thread_local MonomialOrderStats monomial_order_stats{};
constexpr uint64_t order_mask57 = (uint64_t(1) << 57) - 1;

inline void order_count(uint64_t &value, uint64_t amount = 1) noexcept {
  if (amount > std::numeric_limits<uint64_t>::max() - value) {
    value = std::numeric_limits<uint64_t>::max();
    monomial_order_stats.overflow = 1;
  } else
    value += amount;
}

inline uint64_t monomial_key57(uint64_t mask) noexcept {
  return (uint64_t(64 - __builtin_popcountll(mask)) << 57) | mask;
}

// Only the temporary ordered_multiple row uses encoded words. Decode every
// word before parity cancellation, proof emission or any external exposure.
template <typename Compare>
void sort_ordered_terms(std::vector<uint64_t> &terms, Compare compare,
                        bool enabled, size_t minimum) {
  order_count(monomial_order_stats.calls);
  order_count(monomial_order_stats.terms, terms.size());
  bool keys = enabled && terms.size() >= minimum;
  if (!enabled)
    order_count(monomial_order_stats.disabled_calls);
  else if (!keys)
    order_count(monomial_order_stats.small_calls);
  else {
    uint64_t support = 0;
    for (uint64_t term : terms)
      support |= term;
    if (support & ~order_mask57) {
      keys = false;
      order_count(monomial_order_stats.wide_calls);
    }
  }
  if (keys) {
    order_count(monomial_order_stats.key_calls);
    order_count(monomial_order_stats.key_terms, terms.size());
    for (auto &term : terms)
      term = monomial_key57(term);
    std::sort(terms.begin(), terms.end());
    for (auto &term : terms)
      term &= order_mask57;
  } else {
    order_count(monomial_order_stats.comparison_calls);
    order_count(monomial_order_stats.comparison_terms, terms.size());
    std::sort(terms.begin(), terms.end(), compare);
  }
}
