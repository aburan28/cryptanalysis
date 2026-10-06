// Independent exact Boolean certificate. No solver headers or supplied roots.
// ANF terms scatter their 64-lane truth word to all supersets of their high
// variable mask. This is direct AND/XOR evaluation, not a subset transform.
#include <algorithm>
#include <array>
#include <cstdint>
#include <exception>
#include <stdexcept>
#include <vector>

struct Certificate {
    uint32_t code, roots, standard, solution_count;
    uint32_t solutions[256];
    uint64_t scatter_words, scalar_terms;
};
// ABI codes: 0 valid, 1 noncanonical, 2 lost root, 3 dimension mismatch,
// 4 nonminimal leading term, 5 nonstandard tail, 6 invalid input, 7 exception.
using Rows = std::vector<std::vector<uint32_t>>;
static Rows unpack(uint32_t n, const uint32_t* terms, uint32_t size,
                   const uint32_t* starts, uint32_t count, bool cancel) {
    if (!starts || (size && !terms) || starts[0] || starts[count] != size)
        throw std::invalid_argument("offsets");
    Rows rows(count);
    for (uint32_t i = 0; i < count; ++i) {
        if (starts[i] > starts[i+1] || starts[i+1] > size)
            throw std::invalid_argument("offsets");
        auto& row = rows[i];
        for (uint32_t j = starts[i]; j < starts[i+1]; ++j) {
            if (terms[j] >= (1u << n)) throw std::invalid_argument("mask");
            row.push_back(terms[j]);
        }
        std::sort(row.begin(), row.end());
        if (cancel) {
            size_t out = 0;
            for (size_t j = 0; j < row.size();) {
                size_t end = j+1;
                while (end < row.size() && row[end] == row[j]) ++end;
                if ((end-j)&1) row[out++] = row[j];
                j = end;
            }
            row.resize(out);
        }
    }
    return rows;
}
static bool parity(const std::vector<uint32_t>& row, uint32_t point) {
    bool value = false;
    for (uint32_t term : row) value ^= (term & point) == term;
    return value;
}
extern "C" int boolean_certificate(uint32_t n,
        const uint32_t* terms, uint32_t size, const uint32_t* offsets, uint32_t count,
        const uint32_t* basis_terms, uint32_t basis_size,
        const uint32_t* basis_offsets, uint32_t basis_count, Certificate* out) {
    if (!out) return 6;
    *out = {};
    try {
        if (n < 1 || n > 20) throw std::invalid_argument("variables");
        Rows equations = unpack(n, terms, size, offsets, count, true);
        Rows basis = unpack(n, basis_terms, basis_size, basis_offsets, basis_count, false);
        for (const auto& row : basis)
            if (row.empty() || std::adjacent_find(row.begin(), row.end()) != row.end())
                return out->code = 1;
        const uint32_t universe = 1u << n, blocks = (universe+63)/64;
        std::array<uint64_t, 64> low{};
        for (uint32_t m = 0; m < 64; ++m)
            for (uint32_t a = 0; a < 64; ++a)
                if ((a&m) == m) low[m] |= uint64_t(1) << a;
        std::vector<uint64_t> roots(blocks, ~uint64_t(0)), values(blocks), coefficients(blocks);
        if (n < 6) roots[0] = (uint64_t(1) << universe)-1;
        uint32_t alive = universe;
        // Small polynomials tend to eliminate assignments at lower cost.
        std::stable_sort(equations.begin(), equations.end(),
            [](const auto& a, const auto& b) { return a.size() < b.size(); });
        for (const auto& row : equations) {
            if (!alive) break;
            std::fill(coefficients.begin(), coefficients.end(), 0);
            for (uint32_t m : row) coefficients[m >> 6] ^= low[m & 63];
            uint64_t scatter_cost = 0;
            for (uint32_t h = 0; h < blocks; ++h)
                if (coefficients[h]) scatter_cost += blocks >> __builtin_popcount(h);
            // Switch only the evaluation method, never the set being checked.
            if (uint64_t(alive)*row.size() < scatter_cost) {
                out->scalar_terms += uint64_t(alive)*row.size();
                for (uint32_t b = 0; b < blocks; ++b) {
                    uint64_t bits = roots[b];
                    while (bits) {
                        uint32_t j = __builtin_ctzll(bits);
                        if (parity(row, 64*b+j)) { roots[b] ^= uint64_t(1)<<j; --alive; }
                        bits &= bits-1;
                    }
                }
            } else {
                std::fill(values.begin(), values.end(), 0);
                for (uint32_t h = 0; h < blocks; ++h) {
                    if (!coefficients[h]) continue;
                    uint32_t free = (blocks-1)^h, subset = free;
                    do {
                        values[h|subset] ^= coefficients[h];
                        if (!subset) break;
                        subset = (subset-1)&free;
                    } while (true);
                }
                out->scatter_words += scatter_cost;
                alive = 0;
                for (uint32_t b = 0; b < blocks; ++b) {
                    roots[b] &= ~values[b];
                    alive += __builtin_popcountll(roots[b]);
                }
            }
        }
        out->roots = alive;
        // Check output only on independently established input roots.
        for (const auto& row : basis)
            for (uint32_t b = 0; b < blocks; ++b) {
                uint64_t bits = roots[b];
                while (bits) {
                    if (parity(row, 64*b+__builtin_ctzll(bits))) return out->code = 2;
                    bits &= bits-1;
                }
            }
        std::vector<uint32_t> leading;
        std::vector<uint64_t> forbidden(blocks, 0);
        for (const auto& row : basis) {
            uint32_t lm = row[0];
            for (uint32_t m : row)
                if (__builtin_popcount(m) > __builtin_popcount(lm) ||
                    (__builtin_popcount(m) == __builtin_popcount(lm) && m < lm)) lm = m;
            leading.push_back(lm);
            uint32_t h = lm >> 6, free = (blocks-1)^h, subset = free;
            do {
                forbidden[h|subset] |= low[lm&63];
                if (!subset) break;
                subset = (subset-1)&free;
            } while (true);
        }
        uint32_t dimension = 0;
        for (uint32_t b = 0; b < blocks; ++b) {
            uint64_t standard = ~forbidden[b];
            if (n < 6) standard &= (uint64_t(1) << universe)-1;
            dimension += __builtin_popcountll(standard);
        }
        out->standard = dimension;
        if (dimension != alive) return out->code = 3;
        for (size_t i = 0; i < basis.size(); ++i) {
            for (size_t j = 0; j < basis.size(); ++j)
                if (i != j && (leading[i]&leading[j]) == leading[j]) return out->code = 4;
            for (uint32_t m : basis[i])
                if (m != leading[i] && ((forbidden[m>>6]>>(m&63))&1)) return out->code = 5;
        }
        if (alive <= 256)
            for (uint32_t b = 0; b < blocks; ++b) {
                uint64_t bits = roots[b];
                while (bits) {
                    out->solutions[out->solution_count++] = b*64+__builtin_ctzll(bits);
                    bits &= bits-1;
                }
            }
        return 0;
    } catch (const std::invalid_argument&) { return out->code = 6; }
      catch (const std::exception&) { return out->code = 7; }
}
