// Q1461: exact fixed-midpoint S3 pair inversion through sparse XOR sums.
#pragma once

#include "../q1422_leaf_lift_gate/lift_gate.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <set>
#include <utility>
#include <vector>

namespace q1461 {

using q1420::Field;
using q1420::U128;

struct Leaf {
    U128 fixed = 0;
    U128 ones = 0;
};

inline int weight(U128 x) {
    return __builtin_popcountll(uint64_t(x)) +
           __builtin_popcountll(uint64_t(x >> 64));
}

inline bool fits(U128 x, const Leaf &leaf, int maximum_weight) {
    return x && weight(x) <= maximum_weight &&
           (x & leaf.fixed) == leaf.ones;
}

inline uint64_t sum_candidate_count(int free_union, int total_slack,
                                    uint64_t cap) {
    unsigned __int128 count = 0, choose = 1;
    for (int k = 0; k <= std::min(free_union, total_slack); ++k) {
        if (k) choose = choose * unsigned(free_union - k + 1) / unsigned(k);
        count += choose;
        if (count > cap) return cap + 1;
    }
    return uint64_t(count);
}

struct Result {
    bool skipped = false;
    uint64_t sum_candidate_bound = 0;
    uint64_t sums_visited = 0;
    uint64_t trace_rejections = 0;
    uint64_t fixed_bit_rejections = 0;
    uint64_t linear_solutions = 0;
    uint64_t sparse_rejections = 0;
    uint64_t lift_rejections = 0;
    uint64_t verified_pairs = 0;
    uint64_t basis_xors = 0;
    uint64_t elimination_xors = 0;
    std::set<std::pair<U128, U128>> pairs;
};

// L_s(a) = a^2 + s*a has a kernel of dimension one over F_2 when s != 0,
// and a zero-dimensional kernel when s == 0. Any restriction to free leaf
// coordinates therefore has at most one dependency.
struct BinaryImage {
    std::array<U128, 128> pivots{};
    std::array<U128, 128> witnesses{};
    U128 kernel = 0;
    uint64_t xors = 0;

    void insert(U128 value, U128 assignment) {
        while (value) {
            unsigned bit = q1420::bit_index(value);
            if (pivots[bit]) {
                value ^= pivots[bit];
                assignment ^= witnesses[bit];
                ++xors;
            } else {
                pivots[bit] = value;
                witnesses[bit] = assignment;
                return;
            }
        }
        q1420::require(!kernel, "S3 linearized map has two dependencies");
        kernel = assignment;
    }

    bool solve(U128 value, U128 &assignment) {
        assignment = 0;
        while (value) {
            unsigned bit = q1420::bit_index(value);
            if (!pivots[bit]) return false;
            value ^= pivots[bit];
            assignment ^= witnesses[bit];
            ++xors;
        }
        return true;
    }
};

struct SparseSumInverse {
    Field &field;
    int maximum_weight;
    std::array<std::array<U128, 128>, 128> products{};
    std::array<U128, 128> squares{};
    std::array<U128, 128> halftrace_square{};

    explicit SparseSumInverse(Field &f, int weight_limit)
        : field(f), maximum_weight(weight_limit) {
        q1420::require(field.one_onb == field.mask,
                        "normal-basis trace parity assumption failed");
        q1420::require(maximum_weight > 0 && maximum_weight < field.n,
                        "invalid sparse weight bound");
        for (int i = 0; i < field.n; ++i) {
            squares[i] = field.sqr(field.onb_to_poly[i]);
            halftrace_square[i] = field.half_trace(squares[i]);
            for (int j = 0; j < field.n; ++j)
                products[i][j] = field.mul(field.onb_to_poly[i],
                                           field.onb_to_poly[j]);
        }
    }

    U128 coefficient(int bit, U128 sum) const {
        U128 result = squares[bit];
        while (sum) {
            unsigned j = q1420::bit_index(sum);
            result ^= products[bit][j];
            sum &= sum - 1;
        }
        return result;
    }

    Result check(Leaf first, Leaf second, U128 midpoint,
                 uint64_t sum_cap) {
        Result result;
        U128 mask = field.mask;
        q1420::require((first.fixed | first.ones | second.fixed |
                        second.ones | midpoint) <= mask,
                        "partial pair overflows field");
        q1420::require(!(first.ones & ~first.fixed) &&
                        !(second.ones & ~second.fixed),
                        "fixed one outside fixed mask");
        int slack_a = maximum_weight - weight(first.ones);
        int slack_b = maximum_weight - weight(second.ones);
        if (slack_a < 0 || slack_b < 0) return result;
        U128 free_union = mask & ~(first.fixed & second.fixed);
        result.sum_candidate_bound = sum_candidate_count(
            weight(free_union), slack_a + slack_b, sum_cap);
        if (result.sum_candidate_bound > sum_cap) {
            result.skipped = true;
            return result;
        }
        // S3(a,b,0) = (ab)^2 + 1, so ab = 1. The sum-coordinate
        // Artin-Schreier substitution below requires a nonzero midpoint.
        if (!midpoint) {
            result.skipped = true;
            return result;
        }
        U128 m = field.to_poly(midpoint);
        U128 inv_m = field.inv(m);
        U128 inv_m_squared = field.sqr(inv_m);
        U128 p_constant = field.mul(
            m, field.half_trace(inv_m_squared));
        std::array<U128, 128> p_basis{};
        for (int bit = 0; bit < field.n; ++bit)
            p_basis[bit] = field.mul(m, halftrace_square[bit]);
        int inv_trace = weight(field.to_onb(inv_m_squared)) & 1;
        std::vector<int> free_bits;
        while (free_union) {
            unsigned bit = q1420::bit_index(free_union);
            free_bits.push_back(int(bit));
            free_union &= free_union - 1;
        }
        U128 base_sum = first.ones ^ second.ones;
        auto process = [&](U128 sum) {
            ++result.sums_visited;
            if (((weight(sum) & 1) ^ inv_trace) != 0) {
                ++result.trace_rejections;
                return;
            }
            U128 known_a = 0;
            std::vector<int> unknown;
            for (int bit = 0; bit < field.n; ++bit) {
                bool a_fixed = bool(first.fixed >> bit & 1);
                bool b_fixed = bool(second.fixed >> bit & 1);
                bool sum_bit = bool(sum >> bit & 1);
                bool av = bool(first.ones >> bit & 1);
                bool bv = bool(second.ones >> bit & 1);
                if (a_fixed && b_fixed && (av ^ bv) != sum_bit) {
                    ++result.fixed_bit_rejections;
                    return;
                }
                if (a_fixed && av) known_a |= U128(1) << bit;
                else if (!a_fixed && b_fixed && (bv ^ sum_bit))
                    known_a |= U128(1) << bit;
                else if (!a_fixed && !b_fixed) unknown.push_back(bit);
            }
            if (weight(known_a) > maximum_weight) {
                ++result.sparse_rejections;
                return;
            }
            U128 p = p_constant;
            U128 remaining = sum;
            while (remaining) {
                unsigned bit = q1420::bit_index(remaining);
                p ^= p_basis[bit];
                ++result.basis_xors;
                remaining &= remaining - 1;
            }
            BinaryImage image;
            U128 constant = 0;
            remaining = known_a;
            while (remaining) {
                unsigned bit = q1420::bit_index(remaining);
                constant ^= coefficient(int(bit), sum);
                result.basis_xors += weight(sum) + 1;
                remaining &= remaining - 1;
            }
            for (size_t i = 0; i < unknown.size(); ++i) {
                image.insert(coefficient(unknown[i], sum), U128(1) << i);
                result.basis_xors += weight(sum);
            }
            for (U128 target : {p, p ^ m}) {
                U128 assignment = 0;
                if (!image.solve(target ^ constant, assignment)) continue;
                ++result.linear_solutions;
                for (int variant = 0; variant < (image.kernel ? 2 : 1);
                     ++variant) {
                    U128 chosen = assignment ^ (variant ? image.kernel : 0);
                    U128 a = known_a;
                    while (chosen) {
                        unsigned bit = q1420::bit_index(chosen);
                        a |= U128(1) << unknown[bit];
                        chosen &= chosen - 1;
                    }
                    U128 b = a ^ sum;
                    if (!fits(a, first, maximum_weight) ||
                        !fits(b, second, maximum_weight)) {
                        ++result.sparse_rejections;
                        continue;
                    }
                    if (!q1422::curve_lifts(field, a) ||
                        !q1422::curve_lifts(field, b)) {
                        ++result.lift_rejections;
                        continue;
                    }
                    q1420::require(field.evaluate_s3(
                        field.to_poly(a), field.to_poly(b), m) == 0,
                        "recovered pair fails S3");
                    if (result.pairs.insert({a, b}).second)
                        ++result.verified_pairs;
                }
            }
            result.elimination_xors += image.xors;
        };
        auto visit = [&](auto &&self, int start, int left,
                         U128 toggles) -> void {
            if (!left) {
                process(base_sum ^ toggles);
                return;
            }
            for (int i = start; i <= int(free_bits.size()) - left; ++i)
                self(self, i + 1, left - 1,
                     toggles | (U128(1) << free_bits[i]));
        };
        for (int size = 0;
             size <= std::min(int(free_bits.size()), slack_a + slack_b);
             ++size)
            visit(visit, 0, size, 0);
        q1420::require(result.sums_visited == result.sum_candidate_bound,
                        "sparse-sum candidate count mismatch");
        return result;
    }
};

}  // namespace q1461
