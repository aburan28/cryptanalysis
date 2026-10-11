#pragma once

#include <cstdint>
#include <initializer_list>

#if defined(__aarch64__) && defined(__ARM_FEATURE_CRYPTO)
#include <arm_neon.h>
#endif

// Fe and xo are declared by the frozen native inverse before this header.
static inline Fe mul131_fast(Fe a, Fe b) {
#if defined(__aarch64__) && defined(__ARM_FEATURE_CRYPTO)
    const uint64_t av[3] = {a.lo, a.mid, a.hi};
    const uint64_t bv[3] = {b.lo, b.mid, b.hi};
    uint64_t product[5] = {};
    for (int i = 0; i < 3; ++i) {
        for (int j = 0; j < 3; ++j) {
            const poly128_t wide = vmull_p64(static_cast<poly64_t>(av[i]),
                                              static_cast<poly64_t>(bv[j]));
            const uint64x2_t words = vreinterpretq_u64_p128(wide);
            product[i+j] ^= vgetq_lane_u64(words, 0);
            product[i+j+1] ^= vgetq_lane_u64(words, 1);
        }
    }
    // t^131 = t^13+t^2+t+1. The product has degree at most 260,
    // so one 129-bit fold followed by one at-most-12-bit fold suffices.
    uint64_t low[3] = {product[0], product[1], product[2] & 7};
    const uint64_t high[3] = {
        (product[2] >> 3) | (product[3] << 61),
        (product[3] >> 3) | (product[4] << 61),
        product[4] >> 3,
    };
    for (int shift : {0, 1, 2, 13}) {
        for (int i = 0; i < 3; ++i) {
            low[i] ^= high[i] << shift;
            if (shift && i < 2) low[i+1] ^= high[i] >> (64-shift);
        }
    }
    const uint64_t high2 = low[2] >> 3;
    low[2] &= 7;
    low[0] ^= high2 ^ (high2 << 1) ^ (high2 << 2) ^ (high2 << 13);
    return {low[0], low[1], low[2]};
#else
    Fe result{};
    for (int i = 0; i < 131; ++i) {
        const bool selected = i < 64 ? ((a.lo >> i) & 1)
                             : i < 128 ? ((a.mid >> (i-64)) & 1)
                                       : ((a.hi >> (i-128)) & 1);
        if (selected) result = xo(result, b);
        const bool carry = (b.hi & 4) != 0;
        b = {(b.lo << 1) ^ (carry ? 0x2007ULL : 0ULL),
             (b.mid << 1) | (b.lo >> 63),
             ((b.hi << 1) | (b.mid >> 63)) & 7};
    }
    return result;
#endif
}
