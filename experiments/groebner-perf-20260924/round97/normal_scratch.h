#pragma once
#include <cstdint>
#include <limits>

struct NormalScratchStats {
    uint64_t calls = 0, completed = 0, charged_terms = 0;
    uint64_t fresh_vectors = 0, growths = 0, reused = 0;
    uint64_t oversized_releases = 0, released_capacity_words = 0;
    uint64_t peak_scratch_capacity = 0, peak_retained_scratch_capacity = 0;
    uint64_t overflow = 0;
};
static thread_local NormalScratchStats normal_scratch_stats{};

inline void normal_count(uint64_t &destination, uint64_t amount = 1) noexcept
{
    if (amount > std::numeric_limits<uint64_t>::max() - destination) {
        destination = std::numeric_limits<uint64_t>::max();
        normal_scratch_stats.overflow = 1;
    } else
        destination += amount;
}
