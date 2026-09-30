// Conditional quadratic lifting. A low-degree residual is solved exactly;
// large lifted nullspaces use original-variable enumeration, never truncation.
#include "abi.h"
#include <array>
#include <chrono>
#include <mutex>
#include <string>
#include <stdexcept>
#include <vector>
#include "../round27/interpolation.hpp"
#ifdef QUADRATIC_METAL
#    include "metal_backend.h"
#endif

struct Word {
    uint64_t lo = 0, hi = 0;
    Word &operator^=(const Word &b)
    {
        lo ^= b.lo;
        hi ^= b.hi;
        return *this;
    }
    bool nonzero() const { return lo || hi; }
    int pivot() const { return hi ? 127 - __builtin_clzll(hi) : 63 - __builtin_clzll(lo); }
};
struct Producer {
    uint32_t nx, ny, equations, limbs, features, branches;
    std::vector<Word> values;
    std::vector<uint32_t> monomials, feature_index;
    std::mutex mutex;
#ifdef QUADRATIC_METAL
    void *metal = nullptr;
    ~Producer()
    {
        if (metal) quadratic_metal_destroy(metal);
    }
#endif
    Producer(uint32_t x, uint32_t y, uint32_t e)
        : nx(x), ny(y), equations(e), limbs((e + 63) / 64), features(y + y * (y - 1) / 2),
          branches(1u << x), values(size_t(branches) * (features + 1)),
          feature_index(1u << y, UINT32_MAX)
    {
        monomials.push_back(0);
        feature_index[0] = 0;
        for (uint32_t j = 0; j < y; ++j) monomials.push_back(1u << j);
        for (uint32_t j = 0; j < y; ++j)
            for (uint32_t k = j + 1; k < y; ++k) monomials.push_back((1u << j) | (1u << k));
        for (uint32_t j = 1; j < monomials.size(); ++j) feature_index[monomials[j]] = j;
#ifdef QUADRATIC_METAL
        if (features <= 31 && equations <= 32)
            metal = quadratic_metal_create(branches, features, equations);
#endif
    }
};
struct Produced {
    BranchStats stats{};
    std::vector<Mask> roots;
    std::vector<Polynomial> basis;
    // Zero means unresolved: the independent checker must enumerate the entire
    // original residual space. Nonzero is an equation-combination witness of 1.
    std::vector<uint64_t> contradictions;
};
static thread_local std::string error_text;
static thread_local uint32_t error_code;
static void dimensions(uint32_t x, uint32_t y, uint32_t e)
{
    if (!x || x > 20 || !y || y > 10 || x + y > 30 || !e || e > 128)
        throw std::invalid_argument("dimensions: x 1..20, y 1..10, x+y<=30, equations 1..128");
    const uint64_t bytes = (UINT64_C(1) << x) * (1 + y + y * (y - 1) / 2) * sizeof(Word);
    if (bytes > TABLE_BYTES_LIMIT) throw std::length_error("specialization table exceeds 64 MiB");
}
static uint64_t mask_at(const void *masks, uint32_t width, uint32_t i)
{
    return width == 32 ? static_cast<const uint32_t *>(masks)[i]
                       : static_cast<const uint64_t *>(masks)[i];
}
static Produced solve(Producer &w, const void *masks, uint32_t width, const uint64_t *coeff,
                      uint32_t count)
{
    if ((width != 32 && width != 64) || count > TERM_LIMIT || (count && (!masks || !coeff)))
        throw std::invalid_argument("packed extents");
    Produced out;
    out.roots.reserve(ROOT_LIMIT);
    out.contradictions.resize(size_t(w.branches) * w.limbs, 0);
    out.stats.features = w.features;
    out.stats.workspace_bytes = w.values.size() * sizeof(Word) + out.contradictions.size() * 8;
    auto started = std::chrono::steady_clock::now();
    const uint64_t low = (UINT64_C(1) << w.nx) - 1;
    const uint32_t stride = w.features + 1;
    // The support-to-feature layout is invariant. Coefficients and all
    // specialization values are rebuilt from this call's packed input.
    std::fill(w.values.begin(), w.values.end(), Word{});
    for (uint32_t t = 0; t < count; ++t) {
        const uint64_t mask = mask_at(masks, width, t);
        if (mask >> (w.nx + w.ny)) throw std::invalid_argument("mask outside ring");
        Word c{coeff[size_t(t) * w.limbs], w.limbs == 2 ? coeff[size_t(t) * 2 + 1] : 0};
        if (w.equations % 64 && coeff[size_t(t) * w.limbs + w.limbs - 1] >> (w.equations % 64))
            throw std::invalid_argument("coefficient outside equations");
        if (!c.nonzero()) continue;
        const uint32_t right = uint32_t(mask >> w.nx), feature = w.feature_index[right];
        if (feature == UINT32_MAX) throw std::domain_error("residual degree exceeds two");
        w.values[size_t(mask & low) * stride + feature] ^= c;
    }
    // Packed-equation subset transform evaluates each residual coefficient
    // on every fixed-block assignment. No target-independent answers exist.
    for (uint32_t bit = 1; bit < w.branches; bit <<= 1)
        for (uint32_t base = 0; base < w.branches; base += 2 * bit)
            for (uint32_t j = 0; j < bit; ++j) {
                Word *dst = w.values.data() + size_t(base + bit + j) * stride;
                const Word *src = w.values.data() + size_t(base + j) * stride;
                for (uint32_t feature = 0; feature < stride; ++feature)
                    dst[feature] ^= src[feature];
            }
    out.stats.transform_xors = uint64_t(w.nx) * (w.branches / 2) * stride;
    auto specialized = std::chrono::steady_clock::now();
    out.stats.specialization = std::chrono::duration<double>(specialized - started).count();
    const uint32_t *gpu_rows = nullptr;
#ifdef QUADRATIC_METAL
    if (w.metal) {
        gpu_rows = quadratic_metal_solve(w.metal, w.values.data(), w.values.size() * sizeof(Word),
                                         out.stats.gpu_device);
        out.stats.gpu_wall =
            std::chrono::duration<double>(std::chrono::steady_clock::now() - specialized).count();
        out.stats.gpu_used = 1;
        out.stats.workspace_bytes += quadratic_metal_bytes(w.metal);
    } else
        out.stats.gpu_shape_fallback = 1;
#endif
    auto add_root = [&](uint32_t x, uint32_t y) {
        if (out.roots.size() == ROOT_LIMIT)
            throw std::length_error("complete roots exceed 256; no partial basis");
        out.roots.push_back(uint64_t(x) | (uint64_t(y) << w.nx));
    };
    auto charged = [&]() {
        if (out.stats.lifted_candidates + out.stats.fallback_assignments >= ENUMERATION_BUDGET)
            throw std::length_error("exact enumeration budget exceeded; no partial basis");
    };
    for (uint32_t x = 0; x < w.branches; ++x) {
        ++out.stats.branches;
        const Word *columns = w.values.data() + size_t(x) * stride;
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
                Word u{p < 64 ? UINT64_C(1) << p : 0, p >= 64 ? UINT64_C(1) << (p - 64) : 0};
                for (uint32_t row = 0; row < w.equations; ++row)
                    if (pivots[row].nonzero() && (__builtin_parityll(u.lo & pivots[row].lo) ^
                                                  __builtin_parityll(u.hi & pivots[row].hi))) {
                        if (row < 64)
                            u.lo ^= UINT64_C(1) << row;
                        else
                            u.hi ^= UINT64_C(1) << (row - 64);
                    }
                out.contradictions[size_t(x) * w.limbs] = u.lo;
                if (w.limbs == 2) out.contradictions[size_t(x) * 2 + 1] = u.hi;
            }
        }
        out.stats.max_nullity = std::max(out.stats.max_nullity, uint64_t(nullity));
        if (!consistent) continue;
        ++out.stats.consistent;
        if (nullity < w.ny) {
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
        } else {
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
    auto evaluated = std::chrono::steady_clock::now();
    out.stats.evaluation = std::chrono::duration<double>(evaluated - specialized).count();
    out.basis = interpolate(w.nx + w.ny, out.roots, out.stats);
    out.stats.interpolation =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - evaluated).count();
    return out;
}
extern "C" const char *branch_error() { return error_text.c_str(); }
extern "C" uint32_t branch_error_code() { return error_code; }
extern "C" uint64_t branch_stats_size() { return sizeof(BranchStats); }
extern "C" const char *branch_device(const void *p)
{
#ifdef QUADRATIC_METAL
    auto *w = static_cast<const Producer *>(p);
    if (w && w->metal) return quadratic_metal_device(w->metal);
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
    try {
        if (!p || !stats) throw std::invalid_argument("null producer or result");
        *stats = {};
        auto &w = *static_cast<Producer *>(p);
        std::lock_guard<std::mutex> guard(w.mutex);
        auto result = solve(w, masks, width, c, count);
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
