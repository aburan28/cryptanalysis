// Cancel nonlinear columns, retaining exact original-equation witnesses.
#include "abi.h"
#include <array>
#include <mutex>
#include <stdexcept>
#include <vector>

namespace
{
struct Limit {
};
struct Context {
    uint32_t variables, equations, limbs;
    std::array<uint32_t, 1024> index{};
    std::vector<uint32_t> monomials;
    std::mutex mutex;
    Context(uint32_t y, uint32_t e) : variables(y), equations(e), limbs((e + 63) / 64)
    {
        index.fill(UINT32_MAX);
        monomials.push_back(0);
        for (uint32_t i = 0; i < y; ++i) monomials.push_back(1u << i);
        for (uint32_t i = 0; i < y; ++i)
            for (uint32_t j = i + 1; j < y; ++j) monomials.push_back((1u << i) | (1u << j));
        for (uint32_t i = 0; i < monomials.size(); ++i) index[monomials[i]] = i;
    }
};
struct Row {
    uint64_t polynomial = 0;
    std::array<uint64_t, 2> witness{};
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
int produce(Context &w, const uint32_t *masks, const uint64_t *coefficients, uint32_t terms,
            uint64_t budget, uint64_t *output, uint32_t capacity, uint32_t &count,
            PartialStats &stats)
{
    if (terms > 1000000 || (terms && (!masks || !coefficients)) || capacity > 128 ||
        (capacity && !output))
        return PARTIAL_INVALID;
    Charge charge{stats, budget};
    std::array<Row, 128> original{};
    std::array<Row, 56> high{};
    std::array<Row, 11> low{};
    stats.workspace_bytes = sizeof(original) + sizeof(high) + sizeof(low) + sizeof(w.index) +
                            w.monomials.capacity() * sizeof(uint32_t);
    for (uint32_t e = 0; e < w.equations; ++e)
        original[e].witness[e / 64] = UINT64_C(1) << (e % 64);
    for (uint32_t t = 0; t < terms; ++t) {
        charge();
        ++stats.input_terms;
        if (masks[t] >= (1u << w.variables)) return PARTIAL_INVALID;
        if (w.equations % 64 &&
            coefficients[size_t(t) * w.limbs + w.limbs - 1] >> (w.equations % 64))
            return PARTIAL_INVALID;
        bool nonzero = false;
        for (uint32_t l = 0; l < w.limbs; ++l)
            nonzero |= coefficients[size_t(t) * w.limbs + l] != 0;
        if (!nonzero) continue;
        const uint32_t column = w.index[masks[t]];
        if (column == UINT32_MAX) return PARTIAL_NONLINEAR;
        for (uint32_t l = 0; l < w.limbs; ++l) {
            uint64_t bits = coefficients[size_t(t) * w.limbs + l];
            while (bits) {
                charge();
                const uint32_t e = 64 * l + uint32_t(__builtin_ctzll(bits));
                original[e].polynomial ^= UINT64_C(1) << column;
                ++stats.input_word_xors;
                bits &= bits - 1;
            }
        }
    }
    const uint64_t affine = (UINT64_C(1) << (w.variables + 1)) - 1;
    auto add = [&](Row &a, const Row &b) {
        charge();
        a.polynomial ^= b.polynomial;
        a.witness[0] ^= b.witness[0];
        a.witness[1] ^= b.witness[1];
        ++stats.elimination_row_xors;
    };
    bool contradiction = false;
    for (uint32_t e = 0; e < w.equations; ++e) {
        charge();
        Row row = original[e];
        while (row.polynomial & ~affine) {
            const uint32_t pivot = 63u - uint32_t(__builtin_clzll(row.polynomial & ~affine));
            if (!high[pivot].polynomial) {
                high[pivot] = row;
                break;
            }
            add(row, high[pivot]);
        }
        if (row.polynomial & ~affine) continue;
        while (row.polynomial) {
            const uint32_t pivot = 63u - uint32_t(__builtin_clzll(row.polynomial));
            if (!low[pivot].polynomial) {
                low[pivot] = row;
                break;
            }
            add(row, low[pivot]);
        }
        if (low[0].polynomial) {
            contradiction = true;
            break;
        }
    }
    std::array<std::array<uint64_t, 2>, 11> witnesses{};
    stats.workspace_bytes += sizeof(witnesses);
    uint32_t rows = 0;
    if (contradiction) {
        witnesses[rows++] = low[0].witness;
        stats.inconsistent = 1;
    } else {
        for (uint32_t pivot = 1; pivot <= w.variables; ++pivot)
            if (low[pivot].polynomial) witnesses[rows++] = low[pivot].witness;
        stats.rank = rows; // Diagnostic only; not included in the certificate.
    }
    stats.witness_rows = rows;
    if (rows > capacity) return PARTIAL_CAPACITY;
    for (uint32_t row = 0; row < rows; ++row)
        for (uint32_t l = 0; l < w.limbs; ++l) charge();
    for (uint32_t row = 0; row < rows; ++row)
        for (uint32_t l = 0; l < w.limbs; ++l)
            output[size_t(row) * w.limbs + l] = witnesses[row][l];
    count = rows;
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
extern "C" int partial_produce(void *context, const uint32_t *masks, const uint64_t *coefficients,
                               uint32_t terms, uint64_t budget, uint64_t *witnesses,
                               uint32_t capacity, uint32_t *count, PartialStats *stats)
{
    if (count) *count = 0;
    if (stats) *stats = {};
    if (!count || !stats || !context) return PARTIAL_INVALID;
    auto &w = *static_cast<Context *>(context);
    try {
        std::lock_guard<std::mutex> lock(w.mutex);
        return produce(w, masks, coefficients, terms, budget, witnesses, capacity, *count, *stats);
    } catch (const Limit &) {
        return PARTIAL_BUDGET;
    } catch (...) {
        return PARTIAL_INTERNAL;
    }
}
