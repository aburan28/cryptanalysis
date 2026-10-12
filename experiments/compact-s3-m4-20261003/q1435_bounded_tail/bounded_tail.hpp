// Q1435: exact S3 completion for one or two remaining weight units per leaf.
#pragma once

#include "../q1432_coefficient_cache/cached_span.hpp"

#include <cstdint>
#include <vector>

namespace q1435 {

using q1420::U128;

inline uint32_t option_count(int free_count, int slack) {
    q1420::require(free_count >= 0 && (slack == 1 || slack == 2),
                    "bad bounded-tail domain");
    uint32_t count = 1 + uint32_t(free_count);
    if (slack == 2)
        count += uint32_t(free_count * (free_count - 1) / 2);
    return count;
}

inline uint32_t candidate_count(int free_a, int slack_a,
                                 int free_b, int slack_b) {
    return option_count(free_a, slack_a) *
           option_count(free_b, slack_b);
}

struct TailResult {
    uint32_t candidates = 0;
    uint32_t solutions = 0;
    uint64_t expansion_xor_ops = 0;
    U128 unique_a = 0;
    U128 unique_b = 0;
};

struct Option {
    U128 extra_onb = 0;
    U128 linear = 0;
    int bits[2] = {-1, -1};
    int count = 0;
};

inline std::vector<Option> make_options(
        const std::vector<int> &free_bits,
        const std::vector<U128> &linear_coefficients,
        int slack, uint64_t &xor_ops) {
    std::vector<Option> out;
    out.reserve(option_count(int(free_bits.size()), slack));
    out.push_back({});
    for (size_t i = 0; i < free_bits.size(); ++i)
        out.push_back({U128(1) << free_bits[i], linear_coefficients[i],
                       {free_bits[i], -1}, 1});
    if (slack == 2)
        for (size_t i = 0; i < free_bits.size(); ++i)
            for (size_t j = i + 1; j < free_bits.size(); ++j) {
                out.push_back({(U128(1) << free_bits[i]) |
                               (U128(1) << free_bits[j]),
                               linear_coefficients[i] ^
                               linear_coefficients[j],
                               {free_bits[i], free_bits[j]}, 2});
                ++xor_ops;
            }
    return out;
}

// For each allowed completion, the bilinear expansion has exactly the
// same value as S3. The caller guards any clause by every fixed leaf bit
// and the complete intermediate; it may reject only zero-solution domains
// or force a unique completion. The domain cap is checked before field work.
inline TailResult check(q1432::CachedSpan &cache, U128 mid_onb,
                        U128 a_fixed_onb, U128 a_ones_onb,
                        U128 b_fixed_onb, U128 b_ones_onb,
                        int weight_bound, uint32_t max_candidates) {
    auto &field = cache.field;
    q1420::require(((mid_onb | a_fixed_onb | a_ones_onb |
                     b_fixed_onb | b_ones_onb) & ~field.mask) == 0,
                    "bounded tail field element overflow");
    q1420::require((a_ones_onb & ~a_fixed_onb) == 0 &&
                    (b_ones_onb & ~b_fixed_onb) == 0,
                    "bounded tail one outside fixed mask");
    auto popcount = [](U128 x) {
        return __builtin_popcountll(uint64_t(x)) +
               __builtin_popcountll(uint64_t(x >> 64));
    };
    const int slack_a = weight_bound - popcount(a_ones_onb);
    const int slack_b = weight_bound - popcount(b_ones_onb);
    const int free_a_count = field.n - popcount(a_fixed_onb);
    const int free_b_count = field.n - popcount(b_fixed_onb);
    const uint32_t count = candidate_count(
        free_a_count, slack_a, free_b_count, slack_b);
    q1420::require(count <= max_candidates,
                    "bounded tail exceeds candidate cap");

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

    std::vector<int> free_a, free_b;
    std::vector<U128> alpha, beta;
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
    result.candidates = count;
    auto a_options = make_options(free_a, alpha, slack_a,
                                  result.expansion_xor_ops);
    auto b_options = make_options(free_b, beta, slack_b,
                                  result.expansion_xor_ops);
    q1420::require(a_options.size() * b_options.size() == count,
                    "bounded tail domain count mismatch");
    for (const auto &ao : a_options)
        for (const auto &bo : b_options) {
            U128 value = constant ^ ao.linear ^ bo.linear;
            result.expansion_xor_ops += 2;
            for (int i = 0; i < ao.count; ++i)
                for (int j = 0; j < bo.count; ++j) {
                    value ^= gamma[cache.index(ao.bits[i], bo.bits[j])];
                    ++result.expansion_xor_ops;
                }
            if (value) continue;
            ++result.solutions;
            if (result.solutions == 1) {
                result.unique_a = a_ones_onb | ao.extra_onb;
                result.unique_b = b_ones_onb | bo.extra_onb;
            }
        }
    return result;
}

}  // namespace q1435
