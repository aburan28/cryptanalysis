#include "transform.h"
#include <stdexcept>

namespace
{
template <typename Word>
int run(Word *words, uint64_t length, uint32_t k, uint32_t method, uint32_t require_guard,
        uint64_t *stats)
{
    if (!words || !stats || k > 10 || method > 7 || require_guard > 1) return 1;
    const uint32_t n = 1u << k;
    if (length != uint64_t(n) * n) return 1;
    bool symmetric = true;
    uint64_t comparisons = 0;
    if (require_guard && method >= 2)
        for (uint32_t i = 0; i < n && symmetric; ++i)
            for (uint32_t j = 0; j < i; ++j) {
                ++comparisons;
                if (words[size_t(i) * n + j] != words[size_t(j) * n + i]) {
                    symmetric = false;
                    break;
                }
            }
    const uint32_t selected = symmetric ? method : 0;
    boolean_transform::Counts counts;
    switch (selected) {
    case 0: boolean_transform::accepted_full(words, n, counts); break;
    case 1: boolean_transform::full(words, n, n, counts); break;
    case 2: boolean_transform::triangular(words, n, counts, n); break;
    case 3: boolean_transform::triangular(words, n, counts, 16); break;
    case 4: boolean_transform::recursive(words, n, n, counts); break;
    case 5: boolean_transform::recursive(words, n, n, counts, 8); break;
    case 6: boolean_transform::recursive(words, n, n, counts, 16); break;
    case 7: boolean_transform::recursive(words, n, n, counts, 32); break;
    default: return 1;
    }
    stats[0] = counts.xors;
    stats[1] = counts.copies;
    stats[2] = comparisons;
    stats[3] = selected;
    return 0;
}
} // namespace

extern "C" int transform32(uint32_t *a, uint64_t length, uint32_t k, uint32_t method,
                           uint32_t require_guard, uint64_t *stats)
{
    return run(a, length, k, method, require_guard, stats);
}
extern "C" int transform64(uint64_t *a, uint64_t length, uint32_t k, uint32_t method,
                           uint32_t require_guard, uint64_t *stats)
{
    return run(a, length, k, method, require_guard, stats);
}
