// Independent checker: derive every affine consequence from the original ANFs.
// Recompute rank; exhaust its entire solution space; evaluate original
// equations.
#include "abi.h"
#include <algorithm>
#include <array>
#include <mutex>
#include <vector>

namespace
{
struct Limit {
};
struct Context {
    uint32_t variables, equations, limbs;
    std::vector<uint32_t> monomials;
    std::array<uint32_t, 1024> index{};
    std::mutex mutex;
    Context(uint32_t y, uint32_t e) : variables(y), equations(e), limbs((e + 63) / 64)
    {
        index.fill(UINT32_MAX);
        // Numeric order deliberately differs from the producer's singles/pairs.
        for (uint32_t m = 0; m < (1u << y); ++m)
            if (__builtin_popcount(m) <= 2) {
                index[m] = uint32_t(monomials.size());
                monomials.push_back(m);
            }
    }
};
struct Charge {
    PartialStats &stats;
    uint64_t limit;
    void operator()()
    {
        if (stats.work >= limit) throw Limit{};
        ++stats.work;
    }
};
int check(Context &w, const uint32_t *masks, const uint64_t *input, uint32_t terms,
          const uint64_t *witnesses, uint32_t witness_count, uint64_t budget,
          uint32_t assignment_budget, uint32_t *output, uint32_t capacity, uint32_t &count,
          PartialStats &stats)
{
    if (terms > 1000000 || (terms && (!masks || !input)) || witness_count > 128 ||
        (witness_count && !witnesses) || (capacity && !output) || capacity > 1024)
        return PARTIAL_INVALID;
    Charge charge{stats, budget};
    std::array<std::array<uint64_t, 2>, 56> columns{};
    std::array<uint32_t, 128> affine{};
    std::array<uint32_t, 10> pivot_columns{};
    std::array<uint32_t, 1024> roots{};
    stats.workspace_bytes = sizeof(columns) + sizeof(affine) + sizeof(pivot_columns) +
                            sizeof(roots) + sizeof(w.index) +
                            w.monomials.capacity() * sizeof(uint32_t);
    for (uint32_t t = 0; t < terms; ++t) {
        charge();
        ++stats.input_terms;
        if (masks[t] >= (1u << w.variables)) return PARTIAL_INVALID;
        if (w.equations % 64 && input[size_t(t) * w.limbs + w.limbs - 1] >> (w.equations % 64))
            return PARTIAL_INVALID;
        bool nonzero = false;
        for (uint32_t l = 0; l < w.limbs; ++l) nonzero |= input[size_t(t) * w.limbs + l] != 0;
        if (!nonzero) continue;
        const uint32_t feature = w.index[masks[t]];
        if (feature == UINT32_MAX) return PARTIAL_NONLINEAR;
        for (uint32_t l = 0; l < w.limbs; ++l) {
            charge();
            columns[feature][l] ^= input[size_t(t) * w.limbs + l];
            ++stats.input_word_xors;
        }
    }
    stats.witness_rows = witness_count;
    for (uint32_t row = 0; row < witness_count; ++row) {
        charge();
        const uint64_t *u = witnesses + size_t(row) * w.limbs;
        if (w.equations % 64 && u[w.limbs - 1] >> (w.equations % 64)) return PARTIAL_INVALID;
        for (uint32_t feature = 0; feature < w.monomials.size(); ++feature) {
            unsigned parity = 0;
            for (uint32_t l = 0; l < w.limbs; ++l) {
                charge();
                parity ^= __builtin_parityll(u[l] & columns[feature][l]);
                ++stats.witness_parities;
            }
            if (!parity) continue;
            const uint32_t monomial = w.monomials[feature];
            if (monomial & (monomial - 1)) return PARTIAL_NONLINEAR;
            const uint32_t column = monomial ? 1u + uint32_t(__builtin_ctz(monomial)) : 0;
            affine[row] ^= 1u << column;
        }
    }
    // Independent ascending-variable Gauss-Jordan elimination. Never accept
    // a producer rank, pivot list, assignment list or consistency assertion.
    uint32_t rank = 0;
    for (uint32_t column = 1; column <= w.variables; ++column) {
        uint32_t selected = rank;
        for (; selected < witness_count; ++selected) {
            charge();
            if (affine[selected] & (1u << column)) break;
        }
        if (selected == witness_count) continue;
        std::swap(affine[rank], affine[selected]);
        for (uint32_t row = 0; row < witness_count; ++row) {
            charge();
            if (row != rank && (affine[row] & (1u << column))) {
                affine[row] ^= affine[rank];
                ++stats.affine_row_xors;
            }
        }
        pivot_columns[rank++] = column;
    }
    stats.rank = rank;
    for (uint32_t row = 0; row < witness_count; ++row) {
        charge();
        if (affine[row] == 1) {
            stats.inconsistent = 1;
            return PARTIAL_OK;
        }
    }
    std::array<uint32_t, 10> free_columns{};
    stats.workspace_bytes += sizeof(free_columns);
    uint32_t free_count = 0;
    for (uint32_t column = 1; column <= w.variables; ++column) {
        bool pivot = false;
        for (uint32_t row = 0; row < rank; ++row) pivot |= pivot_columns[row] == column;
        if (!pivot) free_columns[free_count++] = column;
    }
    const uint32_t candidates = 1u << free_count;
    if (candidates > assignment_budget) return PARTIAL_BUDGET;
    uint32_t found = 0;
    for (uint32_t bits = 0; bits < candidates; ++bits) {
        charge();
        ++stats.assignments;
        uint32_t assignment = 0;
        for (uint32_t i = 0; i < free_count; ++i)
            assignment |= ((bits >> i) & 1) << (free_columns[i] - 1);
        for (uint32_t row = 0; row < rank; ++row) {
            charge();
            const unsigned value =
                (affine[row] & 1) ^ __builtin_parity((affine[row] >> 1) & assignment);
            assignment |= value << (pivot_columns[row] - 1);
        }
        std::array<uint64_t, 2> value{};
        for (uint32_t feature = 0; feature < w.monomials.size(); ++feature) {
            charge();
            if ((assignment & w.monomials[feature]) != w.monomials[feature]) continue;
            for (uint32_t l = 0; l < w.limbs; ++l) {
                charge();
                value[l] ^= columns[feature][l];
                ++stats.equation_word_xors;
            }
        }
        if (!(value[0] | value[1])) roots[found++] = assignment;
    }
    if (found > capacity) return PARTIAL_CAPACITY;
    // Sort only the discovered roots. Scanning the full original Boolean
    // domain here would undo the benefit of a small affine solution space.
    std::sort(roots.begin(), roots.begin() + found, [&](uint32_t a, uint32_t b) {
        charge();
        return a < b;
    });
    for (uint32_t i = 1; i < found; ++i) {
        charge();
        if (roots[i - 1] >= roots[i]) return PARTIAL_INTERNAL;
    }
    for (uint32_t i = 0; i < found; ++i) charge();
    for (uint32_t i = 0; i < found; ++i) output[i] = roots[i];
    count = found;
    return PARTIAL_OK;
}
} // namespace

extern "C" uint64_t partial_stats_size() { return sizeof(PartialStats); }
extern "C" void *partial_create(uint32_t y, uint32_t e)
{
    if (!y || y > 10 || !e || e > 128) return nullptr;
    try {
        return new Context(y, e);
    } catch (...) {
        return nullptr;
    }
}
extern "C" void partial_destroy(void *context) { delete static_cast<Context *>(context); }
extern "C" int partial_check(void *context, const uint32_t *masks, const uint64_t *coefficients,
                             uint32_t terms, const uint64_t *witnesses, uint32_t witness_count,
                             uint64_t budget, uint32_t assignment_budget, uint32_t *roots,
                             uint32_t capacity, uint32_t *count, PartialStats *stats)
{
    if (count) *count = 0;
    if (stats) *stats = {};
    if (!count || !stats || !context) return PARTIAL_INVALID;
    auto &w = *static_cast<Context *>(context);
    try {
        std::lock_guard<std::mutex> lock(w.mutex);
        return check(w, masks, coefficients, terms, witnesses, witness_count, budget,
                     assignment_budget, roots, capacity, *count, *stats);
    } catch (const Limit &) {
        return PARTIAL_BUDGET;
    } catch (...) {
        return PARTIAL_INTERNAL;
    }
}
