// Conditional quadratic lifting. A low-degree residual is solved exactly;
// large lifted nullspaces use original-variable enumeration, never truncation.
#include "abi.h"
#include <array>
#include <chrono>
#include <mutex>
#include <string>
#include <stdexcept>
#include <vector>
#include <variant>
#include "../round27/interpolation.hpp"
#ifdef QUADRATIC_METAL
#    include "metal_backend.h"
#endif

namespace
{
// Input extents are validated before narrowing. Certificates keep uint64 limbs.
template <typename T> struct NarrowWord {
    T value = 0;
    NarrowWord() = default;
    NarrowWord(uint64_t lo, uint64_t) : value(static_cast<T>(lo)) {}
    NarrowWord &operator^=(const NarrowWord &b)
    {
        value ^= b.value;
        return *this;
    }
    bool nonzero() const { return value != 0; }
    int pivot() const { return 63 - __builtin_clzll(value); }
    unsigned parity(const NarrowWord &b) const { return __builtin_parityll(value & b.value); }
    void toggle(uint32_t bit) { value ^= T{1} << bit; }
    uint64_t low() const { return value; }
    uint64_t high() const { return 0; }
};
struct WideWord {
    uint64_t lo = 0, hi = 0;
    WideWord &operator^=(const WideWord &b)
    {
        lo ^= b.lo;
        hi ^= b.hi;
        return *this;
    }
    bool nonzero() const { return lo || hi; }
    int pivot() const { return hi ? 127 - __builtin_clzll(hi) : 63 - __builtin_clzll(lo); }
    unsigned parity(const WideWord &b) const
    {
        return __builtin_parityll(lo & b.lo) ^ __builtin_parityll(hi & b.hi);
    }
    void toggle(uint32_t bit)
    {
        if (bit < 64)
            lo ^= UINT64_C(1) << bit;
        else
            hi ^= UINT64_C(1) << (bit - 64);
    }
    uint64_t low() const { return lo; }
    uint64_t high() const { return hi; }
};
using Word32 = NarrowWord<uint32_t>;
using Word64 = NarrowWord<uint64_t>;
static_assert(sizeof(Word32) == 4 && sizeof(Word64) == 8 && sizeof(WideWord) == 16);
static uint32_t word_bytes(uint32_t equations)
{
    return equations <= 32 ? 4 : equations <= 64 ? 8 : 16;
}
struct Producer {
    uint32_t nx, ny, equations, limbs, features, branches;
    std::variant<std::vector<Word32>, std::vector<Word64>, std::vector<WideWord>> values;
    std::vector<uint32_t> monomials, feature_index;
    // Invariant Boolean product layout. Pivot flags are reset for every
    // branch; an active pivot always belongs to this fresh specialization.
    std::vector<uint32_t> cubic_index, product_index;
    std::vector<uint64_t> multiplier_pivots;
    std::variant<std::vector<Word32>, std::vector<Word64>, std::vector<WideWord>> multiplier_proofs;
    std::vector<unsigned char> multiplier_active;
    uint32_t cubic_columns = 0, row_words = 0, proof_words = 0;
    std::mutex mutex;
#ifdef QUADRATIC_METAL
    void *metal = nullptr;
    ~Producer()
    {
        if (metal) multiplier_metal_destroy(metal);
    }
#endif
    Producer(uint32_t x, uint32_t y, uint32_t e)
        : nx(x), ny(y), equations(e), limbs((e + 63) / 64), features(y + y * (y - 1) / 2),
          branches(1u << x), feature_index(1u << y, UINT32_MAX)
    {
        const size_t words = size_t(branches) * (features + 1);
        if (e <= 32)
            values = std::vector<Word32>(words);
        else if (e <= 64)
            values = std::vector<Word64>(words);
        else
            values = std::vector<WideWord>(words);
        monomials.push_back(0);
        feature_index[0] = 0;
        for (uint32_t j = 0; j < y; ++j) monomials.push_back(1u << j);
        for (uint32_t j = 0; j < y; ++j)
            for (uint32_t k = j + 1; k < y; ++k) monomials.push_back((1u << j) | (1u << k));
        for (uint32_t j = 1; j < monomials.size(); ++j) feature_index[monomials[j]] = j;
        cubic_index.resize(1u << y, UINT32_MAX);
        for (uint32_t m = 0; m < (1u << y); ++m)
            if (__builtin_popcount(m) <= 3) cubic_index[m] = cubic_columns++;
        row_words = (cubic_columns + 63) / 64;
        proof_words = (y + 1) * limbs;
        product_index.resize(size_t(y + 1) * monomials.size());
        for (uint32_t slot = 0; slot <= y; ++slot)
            for (uint32_t j = 0; j < monomials.size(); ++j)
                product_index[size_t(slot) * monomials.size() + j] =
                    cubic_index[monomials[j] | (slot ? (1u << (slot - 1)) : 0)];
        multiplier_active.resize(cubic_columns);
        multiplier_pivots.resize(size_t(cubic_columns) * row_words);
        const size_t proof_coefficients = size_t(cubic_columns) * (y + 1);
        if (e <= 32)
            multiplier_proofs = std::vector<Word32>(proof_coefficients);
        else if (e <= 64)
            multiplier_proofs = std::vector<Word64>(proof_coefficients);
        else
            multiplier_proofs = std::vector<WideWord>(proof_coefficients);
#ifdef QUADRATIC_METAL
        if (features <= 31 && equations <= 32)
            metal = multiplier_metal_create(branches, features, equations);
#endif
    }
};
struct Produced {
    BranchStats stats{};
    MultiplierStats multipliers{};
    std::vector<Mask> roots;
    std::vector<Polynomial> basis;
    // Prefix: one constant equation-combination witness per branch.
    // Sparse tail: ascending records [branch, u_0 limbs, u_1 limbs, ..., u_y limbs].
    // A branch with neither proof still requires complete residual enumeration.
    std::vector<uint64_t> contradictions;
};
static thread_local std::string error_text;
static thread_local uint32_t error_code;
static thread_local MultiplierStats failed_multiplier_stats{};
static void dimensions(uint32_t x, uint32_t y, uint32_t e)
{
    if (!x || x > 20 || !y || y > 10 || x + y > 30 || !e || e > 128)
        throw std::invalid_argument("dimensions: x 1..20, y 1..10, x+y<=30, equations 1..128");
    const uint64_t bytes = (UINT64_C(1) << x) * (1 + y + y * (y - 1) / 2) * word_bytes(e);
    if (bytes > TABLE_BYTES_LIMIT) throw std::length_error("specialization table exceeds 64 MiB");
}
static uint64_t mask_at(const void *masks, uint32_t width, uint32_t i)
{
    return width == 32 ? static_cast<const uint32_t *>(masks)[i]
                       : static_cast<const uint64_t *>(masks)[i];
}
template <typename Word>
static bool multiplier_identity(Producer &w, const Word *columns, uint32_t branch, Produced &out)
{
    auto &stats = out.multipliers;
    const auto started = std::chrono::steady_clock::now();
    ++stats.attempts;
    uint64_t branch_work = 0;
    auto finish = [&](bool proved, bool budget) {
        stats.certified_branches += proved;
        stats.failed_branches += !proved;
        stats.budget_skips += budget;
        stats.seconds +=
            std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
        return proved;
    };
    auto charge = [&]() {
        if (stats.rows + stats.row_xors >= MULTIPLIER_WORK_BUDGET ||
            branch_work >= MULTIPLIER_BRANCH_BUDGET)
            return false;
        ++branch_work;
        return true;
    };
    const uint64_t entry_words = 1 + w.proof_words;
    if (entry_words > MULTIPLIER_PROOF_WORDS_LIMIT - out.contradictions.size())
        return finish(false, true);
    std::fill(w.multiplier_active.begin(), w.multiplier_active.end(), 0);
    auto &proof_pivots = std::get<std::vector<Word>>(w.multiplier_proofs);
    const uint32_t stride = w.features + 1;
    for (uint32_t slot = 0; slot <= w.ny; ++slot) {
        const uint32_t *products = w.product_index.data() + size_t(slot) * stride;
        for (uint32_t equation = 0; equation < w.equations; ++equation) {
            if (!charge()) return finish(false, true);
            ++stats.rows;
            std::array<uint64_t, 3> row{};
            std::array<Word, 11> proof{};
            proof[slot].toggle(equation);
            for (uint32_t feature = 0; feature < stride; ++feature) {
                const uint64_t coefficient =
                    equation < 64 ? columns[feature].low() : columns[feature].high();
                if ((coefficient >> (equation % 64)) & 1)
                    row[products[feature] / 64] ^= UINT64_C(1) << (products[feature] % 64);
            }
            while (true) {
                int pivot = -1;
                for (uint32_t limb = w.row_words; limb; --limb)
                    if (row[limb - 1]) {
                        pivot = int(64 * (limb - 1) + 63 - __builtin_clzll(row[limb - 1]));
                        break;
                    }
                if (pivot < 0) break;
                if (pivot == 0) {
                    // A polynomial identity in the Boolean quotient, not an
                    // inference from a missing or inconsistent lifted root.
                    const size_t required = out.contradictions.size() + entry_words;
                    if (required > out.contradictions.capacity()) {
                        const size_t previous_capacity = out.contradictions.capacity();
                        const size_t capacity =
                            std::min<size_t>(MULTIPLIER_PROOF_WORDS_LIMIT,
                                             std::max(required, 2 * out.contradictions.capacity()));
                        out.contradictions.reserve(capacity);
                        out.stats.workspace_bytes +=
                            (out.contradictions.capacity() - previous_capacity) * 8;
                    }
                    out.contradictions.push_back(branch);
                    for (uint32_t j = 0; j <= w.ny; ++j) {
                        out.contradictions.push_back(proof[j].low());
                        if (w.limbs == 2) out.contradictions.push_back(proof[j].high());
                    }
                    return finish(true, false);
                }
                uint64_t *old = w.multiplier_pivots.data() + size_t(pivot) * w.row_words;
                Word *old_proof = proof_pivots.data() + size_t(pivot) * (w.ny + 1);
                if (!w.multiplier_active[pivot]) {
                    w.multiplier_active[pivot] = 1;
                    std::copy_n(row.data(), w.row_words, old);
                    std::copy_n(proof.data(), w.ny + 1, old_proof);
                    break;
                }
                if (!charge()) return finish(false, true);
                ++stats.row_xors;
                // Count logical uint64 certificate limbs, independent of the
                // narrower in-memory representation selected for this input.
                stats.word_xors += w.row_words + w.proof_words;
                for (uint32_t limb = 0; limb < w.row_words; ++limb) row[limb] ^= old[limb];
                for (uint32_t j = 0; j <= w.ny; ++j) proof[j] ^= old_proof[j];
            }
        }
    }
    return finish(false, false);
}
template <typename Word>
static void solve(Producer &w, std::vector<Word> &values, const void *masks, uint32_t width,
                  const uint64_t *coeff, uint32_t count, Produced &out)
{
    if ((width != 32 && width != 64) || count > TERM_LIMIT || (count && (!masks || !coeff)))
        throw std::invalid_argument("packed extents");
    out.roots.reserve(ROOT_LIMIT);
    out.contradictions.resize(size_t(w.branches) * w.limbs, 0);
    out.stats.features = w.features;
    out.multipliers.workspace_bytes =
        w.multiplier_pivots.size() * 8 +
        std::get<std::vector<Word>>(w.multiplier_proofs).size() * sizeof(Word) +
        w.multiplier_active.size() + (w.cubic_index.size() + w.product_index.size()) * 4;
    out.stats.workspace_bytes = values.size() * sizeof(Word) + out.contradictions.capacity() * 8 +
                                out.multipliers.workspace_bytes;
    auto started = std::chrono::steady_clock::now();
    const uint64_t low = (UINT64_C(1) << w.nx) - 1;
    const uint32_t stride = w.features + 1;
    // The support-to-feature layout is invariant. Coefficients and all
    // specialization values are rebuilt from this call's packed input.
    std::fill(values.begin(), values.end(), Word{});
    for (uint32_t t = 0; t < count; ++t) {
        const uint64_t mask = mask_at(masks, width, t);
        if (mask >> (w.nx + w.ny)) throw std::invalid_argument("mask outside ring");
        if (w.equations % 64 && coeff[size_t(t) * w.limbs + w.limbs - 1] >> (w.equations % 64))
            throw std::invalid_argument("coefficient outside equations");
        Word c{coeff[size_t(t) * w.limbs], w.limbs == 2 ? coeff[size_t(t) * 2 + 1] : 0};
        if (!c.nonzero()) continue;
        const uint32_t right = uint32_t(mask >> w.nx), feature = w.feature_index[right];
        if (feature == UINT32_MAX) throw std::domain_error("residual degree exceeds two");
        values[size_t(mask & low) * stride + feature] ^= c;
    }
    // Packed-equation subset transform evaluates each residual coefficient
    // on every fixed-block assignment. No target-independent answers exist.
    for (uint32_t bit = 1; bit < w.branches; bit <<= 1)
        for (uint32_t base = 0; base < w.branches; base += 2 * bit)
            for (uint32_t j = 0; j < bit; ++j) {
                Word *dst = values.data() + size_t(base + bit + j) * stride;
                const Word *src = values.data() + size_t(base + j) * stride;
                for (uint32_t feature = 0; feature < stride; ++feature)
                    dst[feature] ^= src[feature];
            }
    out.stats.transform_xors = uint64_t(w.nx) * (w.branches / 2) * stride;
    auto specialized = std::chrono::steady_clock::now();
    out.stats.specialization = std::chrono::duration<double>(specialized - started).count();
    const uint32_t *gpu_rows = nullptr;
#ifdef QUADRATIC_METAL
    if (w.metal) {
        gpu_rows = multiplier_metal_solve(w.metal, values.data(), values.size() * sizeof(Word),
                                          out.stats.gpu_device);
        out.stats.gpu_wall =
            std::chrono::duration<double>(std::chrono::steady_clock::now() - specialized).count();
        out.stats.gpu_used = 1;
        out.stats.workspace_bytes += multiplier_metal_bytes(w.metal);
    } else
        out.stats.gpu_shape_fallback = 1;
#endif
    auto add_root = [&](uint32_t x, uint32_t y) {
        if (out.roots.size() == ROOT_LIMIT) {
            out.stats.evaluation =
                std::chrono::duration<double>(std::chrono::steady_clock::now() - specialized)
                    .count();
            throw std::length_error("complete roots exceed 256; no partial basis");
        }
        out.roots.push_back(uint64_t(x) | (uint64_t(y) << w.nx));
        out.stats.roots = out.roots.size();
    };
    auto charged = [&]() {
        if (out.stats.lifted_candidates + out.stats.fallback_assignments >= ENUMERATION_BUDGET) {
            out.stats.evaluation =
                std::chrono::duration<double>(std::chrono::steady_clock::now() - specialized)
                    .count();
            throw std::length_error("exact enumeration budget exceeded; no partial basis");
        }
    };
    for (uint32_t x = 0; x < w.branches; ++x) {
        ++out.stats.branches;
        const Word *columns = values.data() + size_t(x) * stride;
        std::array<uint64_t, 55> kernel{};
        uint32_t nullity = 0;
        uint64_t particular = 0;
        bool consistent = true;
        if (gpu_rows) {
            const uint32_t *rows = gpu_rows + size_t(x) * 34;
            const uint32_t rank = rows[0] & 0x7fffffffu;
            if (rank > w.features) throw std::runtime_error("invalid Metal rank");
            nullity = w.features - rank;
            consistent = !(rows[0] & 0x80000000u);
            if (!consistent) out.contradictions[x] = rows[33];
            if (consistent) {
                const uint32_t feature_mask = (1u << w.features) - 1, rhs_bit = 1u << w.features;
                uint32_t pivot_mask = 0;
                std::array<uint32_t, 31> pivot_bits{};
                for (uint32_t row = 0; row < rank; ++row) {
                    const uint32_t features = rows[row + 1] & feature_mask;
                    if (!features) throw std::runtime_error("invalid Metal pivot row");
                    const uint32_t bit = 1u << __builtin_ctz(features);
                    pivot_mask |= bit;
                    pivot_bits[row] = bit;
                    if (rows[row + 1] & rhs_bit) particular |= bit;
                }
                uint32_t k = 0;
                for (uint32_t j = 0; j < w.features; ++j)
                    if (!(pivot_mask & (1u << j))) {
                        uint64_t value = UINT64_C(1) << j;
                        for (uint32_t row = 0; row < rank; ++row)
                            if (rows[row + 1] & (1u << j)) value |= pivot_bits[row];
                        kernel[k++] = value;
                    }
                if (k != nullity) throw std::runtime_error("invalid Metal nullspace");
            }
        } else {
            std::array<Word, 128> pivots{};
            std::array<uint64_t, 128> combinations{};
            for (uint32_t j = 0; j < w.features; ++j) {
                Word column = columns[j + 1];
                uint64_t combination = UINT64_C(1) << j;
                while (column.nonzero()) {
                    int p = column.pivot();
                    if (!pivots[p].nonzero()) {
                        pivots[p] = column;
                        combinations[p] = combination;
                        break;
                    }
                    column ^= pivots[p];
                    combination ^= combinations[p];
                }
                if (!column.nonzero()) kernel[nullity++] = combination;
            }
            Word rhs = columns[0];
            while (rhs.nonzero()) {
                int p = rhs.pivot();
                if (!pivots[p].nonzero()) break;
                rhs ^= pivots[p];
                particular ^= combinations[p];
            }
            consistent = !rhs.nonzero();
            if (!consistent) {
                // Build a dual functional orthogonal to every column pivot.
                // Its value on the unreduced RHS pivot is one. This is only
                // proof generation; a separate library checks the identity.
                const uint32_t p = uint32_t(rhs.pivot());
                Word u{};
                u.toggle(p);
                for (uint32_t row = 0; row < w.equations; ++row)
                    if (pivots[row].nonzero() && u.parity(pivots[row])) u.toggle(row);
                out.contradictions[size_t(x) * w.limbs] = u.low();
                if (w.limbs == 2) out.contradictions[size_t(x) * 2 + 1] = u.high();
            }
        }
        out.stats.max_nullity = std::max(out.stats.max_nullity, uint64_t(nullity));
        if (!consistent) continue;
        ++out.stats.consistent;
        if (nullity < w.ny) {
            const size_t roots_before = out.roots.size();
            uint64_t value = particular;
            for (uint32_t serial = 0; serial < (1u << nullity); ++serial) {
                charged();
                ++out.stats.lifted_candidates;
                if (serial) value ^= kernel[__builtin_ctz(serial)];
                const uint32_t y = uint32_t(value) & ((1u << w.ny) - 1);
                bool valid = true;
                for (uint32_t j = w.ny; j < w.features; ++j)
                    if (((value >> j) & 1u) !=
                        unsigned((y & w.monomials[j + 1]) == w.monomials[j + 1])) {
                        valid = false;
                        break;
                    }
                if (valid) add_root(x, y);
            }
            // A small lifted search is cheaper than another matrix. If it
            // finds no actual roots, seek a proof to spare the checker its
            // independent full residual enumeration.
            if (out.roots.size() == roots_before) multiplier_identity(w, columns, x, out);
        } else {
            if (multiplier_identity(w, columns, x, out)) {
                out.multipliers.avoided_assignments += UINT64_C(1) << w.ny;
                continue;
            }
            ++out.stats.fallback_branches;
            // Exact original-variable fallback. Gray-code updates use the
            // quadratic derivative, avoiding enumeration in lifted space.
            Word value = columns[0];
            uint32_t y = 0;
            for (uint32_t serial = 0; serial < (1u << w.ny); ++serial) {
                charged();
                ++out.stats.fallback_assignments;
                if (serial) {
                    const uint32_t changed = uint32_t(__builtin_ctz(serial));
                    value ^= columns[changed + 1];
                    for (uint32_t j = 0; j < w.ny; ++j)
                        if (j != changed && ((y >> j) & 1u))
                            value ^= columns[w.feature_index[(1u << j) | (1u << changed)]];
                    y ^= 1u << changed;
                }
                if (!value.nonzero()) add_root(x, y);
            }
        }
    }
    std::sort(out.roots.begin(), out.roots.end());
    out.stats.roots = out.roots.size();
    out.multipliers.proof_words = out.contradictions.size();
    out.multipliers.proof_capacity_words = out.contradictions.capacity();
    auto evaluated = std::chrono::steady_clock::now();
    out.stats.evaluation = std::chrono::duration<double>(evaluated - specialized).count();
    out.basis = interpolate(w.nx + w.ny, out.roots, out.stats);
    out.stats.interpolation =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - evaluated).count();
}
} // namespace
extern "C" uint32_t branch_coefficient_bits(const void *p)
{
    return p ? 8 * word_bytes(static_cast<const Producer *>(p)->equations) : 0;
}
extern "C" const char *branch_error() { return error_text.c_str(); }
extern "C" uint32_t branch_error_code() { return error_code; }
extern "C" uint64_t branch_stats_size() { return sizeof(BranchStats); }
extern "C" uint64_t branch_multiplier_stats_size() { return sizeof(MultiplierStats); }
extern "C" const MultiplierStats *branch_last_multiplier_stats()
{
    return &failed_multiplier_stats;
}
extern "C" const MultiplierStats *branch_multiplier_stats(const void *p)
{
    return p ? &static_cast<const Produced *>(p)->multipliers : nullptr;
}
extern "C" const char *branch_device(const void *p)
{
#ifdef QUADRATIC_METAL
    auto *w = static_cast<const Producer *>(p);
    if (w && w->metal) return multiplier_metal_device(w->metal);
    return "cpu: Metal shape fallback (features>31 or equations>32)";
#else
    (void)p;
    return "cpu";
#endif
}
extern "C" void *branch_create(uint32_t x, uint32_t y, uint32_t e)
{
    try {
        dimensions(x, y, e);
        return new Producer(x, y, e);
    } catch (const std::exception &e) {
        error_text = e.what();
        error_code = 6;
        return nullptr;
    }
}
extern "C" void branch_destroy(void *p) { delete static_cast<Producer *>(p); }
extern "C" void *branch_solve(void *p, const void *masks, uint32_t width, const uint64_t *c,
                              uint32_t count, BranchStats *stats)
{
    Produced result;
    try {
        if (!p || !stats) throw std::invalid_argument("null producer or result");
        *stats = {};
        auto &w = *static_cast<Producer *>(p);
        std::lock_guard<std::mutex> guard(w.mutex);
        std::visit([&](auto &values) { solve(w, values, masks, width, c, count, result); },
                   w.values);
        *stats = result.stats;
        return new Produced(std::move(result));
    } catch (const std::length_error &e) {
        error_text = e.what();
        error_code = 5;
    } catch (const std::domain_error &e) {
        error_text = e.what();
        error_code = 7;
    } catch (const std::invalid_argument &e) {
        error_text = e.what();
        error_code = 6;
    } catch (const std::exception &e) {
        error_text = e.what();
        error_code = 8;
    }
    if (stats) *stats = result.stats;
    failed_multiplier_stats = result.multipliers;
    failed_multiplier_stats.proof_words = result.contradictions.size();
    failed_multiplier_stats.proof_capacity_words = result.contradictions.capacity();
    return nullptr;
}
extern "C" uint32_t branch_rows(const void *p)
{
    return p ? uint32_t(static_cast<const Produced *>(p)->basis.size()) : 0;
}
extern "C" uint32_t branch_row_size(const void *p, uint32_t row)
{
    auto *r = static_cast<const Produced *>(p);
    return r && row < r->basis.size() ? uint32_t(r->basis[row].size()) : 0;
}
extern "C" const uint64_t *branch_row(const void *p, uint32_t row)
{
    auto *r = static_cast<const Produced *>(p);
    return r && row < r->basis.size() ? r->basis[row].data() : nullptr;
}
extern "C" const uint64_t *branch_roots(const void *p)
{
    return p ? static_cast<const Produced *>(p)->roots.data() : nullptr;
}
extern "C" uint64_t branch_proof_size(const void *p)
{
    return p ? static_cast<const Produced *>(p)->contradictions.size() : 0;
}
extern "C" const uint64_t *branch_proof(const void *p)
{
    return p ? static_cast<const Produced *>(p)->contradictions.data() : nullptr;
}
extern "C" void branch_result_destroy(void *p) { delete static_cast<Produced *>(p); }
