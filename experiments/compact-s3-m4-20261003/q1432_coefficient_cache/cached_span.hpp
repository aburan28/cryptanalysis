// Q1432: exact coefficient reuse for the sound Q1431 partial-S3 span test.
#pragma once

#include "../q1431_guarded_span/span_filter.hpp"

#include <array>
#include <cstdint>
#include <map>
#include <utility>
#include <vector>

namespace q1432 {

using q1420::U128;

struct LinearRow {
    U128 squared_plus_mid_squared = 0;
    U128 times_mid = 0;
    std::array<U128, 128> coefficients{};
    std::array<uint8_t, 128> ready{};
};

struct CachedSpan {
    q1420::Field &field;
    static constexpr size_t max_gamma_tables = 64;
    static constexpr size_t max_linear_rows = 16384;
    bool pair_tables_ready = false;
    std::vector<U128> pair_products, pair_squares;
    std::map<U128, std::vector<U128>> gamma_tables;
    std::map<std::pair<U128, U128>, LinearRow> linear_rows;
    uint64_t pair_build_mul_calls = 0, pair_build_sqr_calls = 0;
    uint64_t gamma_build_mul_calls = 0, gamma_table_builds = 0;
    uint64_t gamma_cache_hits = 0, gamma_cache_fallbacks = 0;
    uint64_t linear_row_hits = 0, linear_row_misses = 0;
    uint64_t linear_row_fallbacks = 0;
    uint64_t linear_coefficient_hits = 0, linear_coefficient_misses = 0;

    explicit CachedSpan(q1420::Field &f) : field(f) {}

    size_t index(int i, int j) const {
        return size_t(i) * size_t(field.n) + size_t(j);
    }

    void ensure_pairs() {
        if (pair_tables_ready) return;
        size_t cells = size_t(field.n) * size_t(field.n);
        pair_products.resize(cells);
        pair_squares.resize(cells);
        for (int i = 0; i < field.n; ++i)
            for (int j = i; j < field.n; ++j) {
                U128 product = field.mul(field.onb_to_poly[i],
                                         field.onb_to_poly[j]);
                U128 squared = field.sqr(product);
                pair_products[index(i, j)] = pair_products[index(j, i)] =
                    product;
                pair_squares[index(i, j)] = pair_squares[index(j, i)] =
                    squared;
                ++pair_build_mul_calls;
                ++pair_build_sqr_calls;
            }
        pair_tables_ready = true;
    }

    std::vector<U128> make_gamma(U128 m_poly) {
        ++gamma_table_builds;
        std::vector<U128> gamma(size_t(field.n) * size_t(field.n));
        for (int i = 0; i < field.n; ++i)
            for (int j = i; j < field.n; ++j) {
                U128 value = pair_squares[index(i, j)] ^
                             field.mul(pair_products[index(i, j)], m_poly);
                gamma[index(i, j)] = gamma[index(j, i)] = value;
                ++gamma_build_mul_calls;
            }
        return gamma;
    }

    const std::vector<U128> &gamma_for(U128 m_onb, U128 m_poly,
                                        std::vector<U128> &fallback) {
        auto found = gamma_tables.find(m_onb);
        if (found != gamma_tables.end()) {
            ++gamma_cache_hits;
            return found->second;
        }
        std::vector<U128> made = make_gamma(m_poly);
        if (gamma_tables.size() < max_gamma_tables)
            return gamma_tables.emplace(m_onb, std::move(made)).first->second;
        ++gamma_cache_fallbacks;
        fallback = std::move(made);
        return fallback;
    }

    LinearRow make_linear_row(U128 other_poly, U128 m_poly, U128 m2) {
        LinearRow row;
        row.squared_plus_mid_squared = field.sqr(other_poly) ^ m2;
        row.times_mid = field.mul(other_poly, m_poly);
        return row;
    }

    LinearRow &linear_row_for(U128 m_onb, U128 other_onb,
                              U128 other_poly, U128 m_poly, U128 m2,
                              LinearRow &fallback) {
        auto key = std::make_pair(m_onb, other_onb);
        auto found = linear_rows.find(key);
        if (found != linear_rows.end()) {
            ++linear_row_hits;
            return found->second;
        }
        ++linear_row_misses;
        LinearRow made = make_linear_row(other_poly, m_poly, m2);
        if (linear_rows.size() < max_linear_rows)
            return linear_rows.emplace(key, std::move(made)).first->second;
        ++linear_row_fallbacks;
        fallback = std::move(made);
        return fallback;
    }

    U128 coefficient(LinearRow &row, int coordinate) {
        if (row.ready[coordinate]) {
            ++linear_coefficient_hits;
            return row.coefficients[coordinate];
        }
        ++linear_coefficient_misses;
        U128 e = field.onb_to_poly[coordinate];
        U128 e2 = pair_products[index(coordinate, coordinate)];
        U128 value = field.mul(e2, row.squared_plus_mid_squared) ^
                     field.mul(e, row.times_mid);
        row.coefficients[coordinate] = value;
        row.ready[coordinate] = 1;
        return value;
    }

    size_t payload_bytes_lower_bound() const {
        size_t total = (pair_products.size() + pair_squares.size()) *
                       sizeof(U128);
        for (const auto &item : gamma_tables)
            total += item.second.size() * sizeof(U128);
        total += linear_rows.size() * sizeof(LinearRow);
        return total;
    }

    q1431::SpanResult check(U128 mid_onb, U128 a_fixed_onb,
                            U128 a_ones_onb, U128 b_fixed_onb,
                            U128 b_ones_onb) {
        q1420::require(((mid_onb | a_fixed_onb | a_ones_onb |
                         b_fixed_onb | b_ones_onb) & ~field.mask) == 0,
                        "cached span field element overflow");
        q1420::require((a_ones_onb & ~a_fixed_onb) == 0 &&
                        (b_ones_onb & ~b_fixed_onb) == 0,
                        "cached span one outside fixed mask");
        ensure_pairs();
        U128 m = field.to_poly(mid_onb);
        U128 a = field.to_poly(a_ones_onb);
        U128 b = field.to_poly(b_ones_onb);
        U128 m2 = field.sqr(m);
        std::vector<U128> local_gamma;
        const auto &gamma = gamma_for(mid_onb, m, local_gamma);
        LinearRow local_for_a, local_for_b;
        LinearRow &row_for_a = linear_row_for(
            mid_onb, b_ones_onb, b, m, m2, local_for_a);
        LinearRow &row_for_b = linear_row_for(
            mid_onb, a_ones_onb, a, m, m2, local_for_b);
        U128 constant = field.evaluate_s3(a, b, m);
        std::array<U128, 128> pivots{};
        q1431::SpanResult result;
        std::vector<int> free_a, free_b;
        for (int i = 0; i < field.n; ++i) {
            if (!(a_fixed_onb >> i & 1)) free_a.push_back(i);
            if (!(b_fixed_onb >> i & 1)) free_b.push_back(i);
        }
        for (int i : free_a) {
            result.rank += q1431::insert(
                pivots, coefficient(row_for_a, i));
            ++result.linear_columns;
        }
        for (int j : free_b) {
            result.rank += q1431::insert(
                pivots, coefficient(row_for_b, j));
            ++result.linear_columns;
        }
        if (result.rank < field.n)
            for (int i : free_a) {
                for (int j : free_b) {
                    result.rank += q1431::insert(
                        pivots, gamma[index(i, j)]);
                    ++result.bilinear_columns;
                    if (result.rank == field.n) break;
                }
                if (result.rank == field.n) break;
            }
        result.feasible = q1431::contains(pivots, constant);
        return result;
    }
};

}  // namespace q1432
