// Q1436: exact affine second-leaf feasibility for a fixed S3 intermediate.
#pragma once

#include "../q1435_bounded_tail/bounded_tail.hpp"

#include <array>
#include <cstdint>
#include <vector>

namespace q1436 {

using q1420::U128;

inline int popcount(U128 x) {
    return __builtin_popcountll(uint64_t(x)) +
           __builtin_popcountll(uint64_t(x >> 64));
}

inline int high_bit(U128 x) {
    q1420::require(x != 0, "zero has no pivot bit");
    uint64_t hi = uint64_t(x >> 64);
    return hi ? 127 - __builtin_clzll(hi) :
                63 - __builtin_clzll(uint64_t(x));
}

struct Result {
    bool feasible = false;
    bool unique = false;
    U128 unique_a = 0, unique_b = 0;
    uint32_t a_options = 0, b_free = 0;
    uint32_t inconsistent_options = 0, overweight_options = 0;
    uint32_t rank_deficient_options = 0, exact_solutions = 0;
    uint64_t coefficient_columns = 0, xor_ops = 0;
};

// S3(a,b,m) is affine over F2 in b when a and m are fixed. Enumerate all
// allowed a completions, solve the exact affine system on b's free normal-
// basis coordinates, and enforce b's weight bound if the solution is unique.
// A consistent rank-deficient b system is conservatively left feasible.
// Therefore !feasible excludes no solution of S3=0 with either weight bound.
inline Result check(q1432::CachedSpan &cache, U128 mid_onb,
                    U128 a_fixed_onb, U128 a_ones_onb,
                    U128 b_fixed_onb, U128 b_ones_onb,
                    int weight_bound, uint32_t max_columns) {
    auto &field = cache.field;
    q1420::require(((mid_onb | a_fixed_onb | a_ones_onb |
                     b_fixed_onb | b_ones_onb) & ~field.mask) == 0,
                    "affine pair field element overflow");
    q1420::require((a_ones_onb & ~a_fixed_onb) == 0 &&
                    (b_ones_onb & ~b_fixed_onb) == 0,
                    "affine pair one outside fixed mask");
    const int slack_a = weight_bound - popcount(a_ones_onb);
    const int slack_b = weight_bound - popcount(b_ones_onb);
    q1420::require(slack_a >= 0 && slack_a <= 2 && slack_b >= 0,
                    "affine pair unsupported slack");
    std::vector<int> free_a, free_b;
    for (int i = 0; i < field.n; ++i) {
        if (!(a_fixed_onb >> i & 1)) free_a.push_back(i);
        if (!(b_fixed_onb >> i & 1)) free_b.push_back(i);
    }
    const uint32_t option_count = q1435::option_count(
        int(free_a.size()), slack_a == 0 ? 1 : slack_a);
    // The zero-slack case has only its fixed completion.
    const uint32_t actual_options = slack_a ? option_count : 1;
    q1420::require(uint64_t(actual_options) * free_b.size() <= max_columns,
                    "affine pair exceeds column cap");

    cache.ensure_pairs();
    U128 m = field.to_poly(mid_onb);
    U128 a = field.to_poly(a_ones_onb);
    U128 b = field.to_poly(b_ones_onb);
    U128 m2 = field.sqr(m);
    std::vector<U128> local_gamma;
    const auto &gamma = cache.gamma_for(mid_onb, m, local_gamma);
    q1432::LinearRow local_a, local_b;
    auto &row_a = cache.linear_row_for(
        mid_onb, b_ones_onb, b, m, m2, local_a);
    auto &row_b = cache.linear_row_for(
        mid_onb, a_ones_onb, a, m, m2, local_b);
    const U128 constant = field.evaluate_s3(a, b, m);
    std::vector<U128> alpha, beta;
    for (int i : free_a) alpha.push_back(cache.coefficient(row_a, i));
    for (int j : free_b) beta.push_back(cache.coefficient(row_b, j));

    Result result;
    result.a_options = actual_options;
    result.b_free = uint32_t(free_b.size());
    auto options = slack_a ?
        q1435::make_options(free_a, alpha, slack_a, result.xor_ops) :
        std::vector<q1435::Option>(1);
    q1420::require(options.size() == actual_options,
                    "affine pair option count mismatch");
    bool unknown = false;
    for (const auto &ao : options) {
        std::array<U128, 128> pivots{}, reps{};
        int rank = 0;
        for (size_t offset = 0; offset < free_b.size(); ++offset) {
            int j = free_b[offset];
            U128 column = beta[offset];
            for (int k = 0; k < ao.count; ++k) {
                column ^= gamma[cache.index(ao.bits[k], j)];
                ++result.xor_ops;
            }
            ++result.coefficient_columns;
            U128 representation = U128(1) << j;
            while (column) {
                int pivot = high_bit(column);
                if (!pivots[pivot]) {
                    pivots[pivot] = column;
                    reps[pivot] = representation;
                    ++rank;
                    break;
                }
                column ^= pivots[pivot];
                representation ^= reps[pivot];
                result.xor_ops += 2;
            }
        }
        U128 residual = constant ^ ao.linear;
        ++result.xor_ops;
        U128 b_extra = 0;
        bool consistent = true;
        while (residual) {
            int pivot = high_bit(residual);
            if (!pivots[pivot]) {
                consistent = false;
                break;
            }
            residual ^= pivots[pivot];
            b_extra ^= reps[pivot];
            result.xor_ops += 2;
        }
        if (!consistent) {
            ++result.inconsistent_options;
            continue;
        }
        if (rank != int(free_b.size())) {
            ++result.rank_deficient_options;
            unknown = true;
            continue;
        }
        if (popcount(b_extra) > slack_b) {
            ++result.overweight_options;
            continue;
        }
        ++result.exact_solutions;
        if (result.exact_solutions == 1) {
            result.unique_a = a_ones_onb | ao.extra_onb;
            result.unique_b = b_ones_onb | b_extra;
        }
    }
    result.feasible = unknown || result.exact_solutions > 0;
    result.unique = !unknown && result.exact_solutions == 1;
    return result;
}

}  // namespace q1436
