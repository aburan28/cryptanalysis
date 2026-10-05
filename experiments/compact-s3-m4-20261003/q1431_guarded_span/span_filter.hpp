// Q1431: sound necessary linear-span test for a partial S3 pair.
#pragma once

#include "../q1420_root_theory/root_field.hpp"

#include <array>
#include <vector>

namespace q1431 {

using q1420::U128;

struct SpanResult {
    bool feasible = true;
    int rank = 0;
    unsigned linear_columns = 0;
    unsigned bilinear_columns = 0;
};

inline unsigned highest_bit(U128 value) {
    q1420::require(value != 0, "highest bit of zero");
    uint64_t high = uint64_t(value >> 64);
    if (high) return 64 + 63 - unsigned(__builtin_clzll(high));
    return 63 - unsigned(__builtin_clzll(uint64_t(value)));
}

inline bool insert(std::array<U128, 128> &pivots, U128 value) {
    while (value) {
        unsigned bit = highest_bit(value);
        if (pivots[bit]) value ^= pivots[bit];
        else {
            pivots[bit] = value;
            return true;
        }
    }
    return false;
}

inline bool contains(const std::array<U128, 128> &pivots, U128 value) {
    while (value) {
        unsigned bit = highest_bit(value);
        if (!pivots[bit]) return false;
        value ^= pivots[bit];
    }
    return true;
}

inline SpanResult check(q1420::Field &field, U128 mid_onb,
                        U128 a_fixed_onb, U128 a_ones_onb,
                        U128 b_fixed_onb, U128 b_ones_onb) {
    q1420::require(((mid_onb | a_fixed_onb | a_ones_onb |
                     b_fixed_onb | b_ones_onb) & ~field.mask) == 0,
                    "partial-pair field element overflow");
    q1420::require((a_ones_onb & ~a_fixed_onb) == 0 &&
                    (b_ones_onb & ~b_fixed_onb) == 0,
                    "one outside fixed partial-pair mask");
    U128 m = field.to_poly(mid_onb);
    U128 a = field.to_poly(a_ones_onb);
    U128 b = field.to_poly(b_ones_onb);
    U128 constant = field.evaluate_s3(a, b, m);
    U128 m2 = field.sqr(m), a2 = field.sqr(a), b2 = field.sqr(b);
    U128 bm = field.mul(b, m), am = field.mul(a, m);
    std::vector<int> free_a, free_b;
    for (int i = 0; i < field.n; ++i) {
        if (!(a_fixed_onb >> i & 1)) free_a.push_back(i);
        if (!(b_fixed_onb >> i & 1)) free_b.push_back(i);
    }
    std::array<U128, 128> pivots{};
    SpanResult result;
    for (int i : free_a) {
        U128 e = field.onb_to_poly[i];
        U128 column = field.mul(field.sqr(e), b2 ^ m2) ^
                      field.mul(e, bm);
        result.rank += insert(pivots, column);
        ++result.linear_columns;
    }
    for (int j : free_b) {
        U128 e = field.onb_to_poly[j];
        U128 column = field.mul(field.sqr(e), a2 ^ m2) ^
                      field.mul(e, am);
        result.rank += insert(pivots, column);
        ++result.linear_columns;
    }
    if (result.rank < field.n)
        for (int i : free_a) {
            for (int j : free_b) {
                U128 product = field.mul(field.onb_to_poly[i],
                                         field.onb_to_poly[j]);
                U128 column = field.sqr(product) ^ field.mul(product, m);
                result.rank += insert(pivots, column);
                ++result.bilinear_columns;
                if (result.rank == field.n) break;
            }
            if (result.rank == field.n) break;
        }
    result.feasible = contains(pivots, constant);
    return result;
}

}  // namespace q1431
