// Q1434: enumerate every weight-one completion of both partial S3 leaves.
#pragma once

#include "../q1432_coefficient_cache/cached_span.hpp"

#include <vector>

namespace q1434 {

using q1420::U128;

struct TailResult {
    uint32_t candidates = 0;
    uint32_t solutions = 0;
    U128 unique_a = 0;
    U128 unique_b = 0;
};

// Both fixed-one masks have exactly one weight unit available. The parent
// weight clauses therefore allow either no extra bit or one free bit on each
// leaf. The bilinear expansion is exact for each such pair of choices.
inline TailResult check(q1432::CachedSpan &cache, U128 mid_onb,
                        U128 a_fixed_onb, U128 a_ones_onb,
                        U128 b_fixed_onb, U128 b_ones_onb,
                        int weight_bound) {
    auto &field = cache.field;
    q1420::require(((mid_onb | a_fixed_onb | a_ones_onb |
                     b_fixed_onb | b_ones_onb) & ~field.mask) == 0,
                    "exact tail field element overflow");
    q1420::require((a_ones_onb & ~a_fixed_onb) == 0 &&
                    (b_ones_onb & ~b_fixed_onb) == 0,
                    "exact tail one outside fixed mask");
    auto popcount = [](U128 x) {
        return __builtin_popcountll(uint64_t(x)) +
               __builtin_popcountll(uint64_t(x >> 64));
    };
    q1420::require(weight_bound - popcount(a_ones_onb) == 1 &&
                    weight_bound - popcount(b_ones_onb) == 1,
                    "exact tail requires one free weight unit per leaf");
    cache.ensure_pairs();
    U128 m = field.to_poly(mid_onb);
    U128 a = field.to_poly(a_ones_onb);
    U128 b = field.to_poly(b_ones_onb);
    U128 m2 = field.sqr(m);
    std::vector<U128> local_gamma;
    const auto &gamma = cache.gamma_for(mid_onb, m, local_gamma);
    q1432::LinearRow local_for_a, local_for_b;
    auto &row_for_a = cache.linear_row_for(
        mid_onb, b_ones_onb, b, m, m2, local_for_a);
    auto &row_for_b = cache.linear_row_for(
        mid_onb, a_ones_onb, a, m, m2, local_for_b);
    U128 constant = field.evaluate_s3(a, b, m);

    std::vector<int> free_a{-1}, free_b{-1};
    std::vector<U128> alpha{0}, beta{0};
    for (int i = 0; i < field.n; ++i) {
        if (!(a_fixed_onb >> i & 1)) {
            free_a.push_back(i);
            alpha.push_back(cache.coefficient(row_for_a, i));
        }
        if (!(b_fixed_onb >> i & 1)) {
            free_b.push_back(i);
            beta.push_back(cache.coefficient(row_for_b, i));
        }
    }
    TailResult result;
    result.candidates = uint32_t(free_a.size() * free_b.size());
    for (size_t ia = 0; ia < free_a.size(); ++ia)
        for (size_t ib = 0; ib < free_b.size(); ++ib) {
            U128 value = constant ^ alpha[ia] ^ beta[ib];
            if (ia && ib)
                value ^= gamma[cache.index(free_a[ia], free_b[ib])];
            if (value) continue;
            ++result.solutions;
            if (result.solutions == 1) {
                result.unique_a = a_ones_onb |
                    (ia ? U128(1) << free_a[ia] : 0);
                result.unique_b = b_ones_onb |
                    (ib ? U128(1) << free_b[ib] : 0);
            }
        }
    return result;
}

}  // namespace q1434
