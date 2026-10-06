// Independent certificate checker. Reconstruct feature-major coefficient
// tables from the original input; never read producer rows, pivots or tables.
#include "abi.h"
#include <algorithm>
#include <array>
#include <chrono>
#include <mutex>
#include <stdexcept>
#include <vector>
#include <variant>

namespace
{

struct Checker {
    uint32_t x, y, equations, limbs, branches;
    std::vector<uint32_t> monomials, index;
    std::variant<std::vector<uint32_t>, std::vector<uint64_t>> coefficients;
    std::mutex mutex;
    Checker(uint32_t a, uint32_t b, uint32_t e)
        : x(a), y(b), equations(e), limbs((e + 63) / 64), branches(1u << a),
          index(1u << b, UINT32_MAX)
    {
        // Numeric monomial order differs from the producer's singles/pairs.
        for (uint32_t m = 0; m < (1u << y); ++m)
            if (__builtin_popcount(m) <= 2) {
                index[m] = uint32_t(monomials.size());
                monomials.push_back(m);
            }
        uint64_t words = uint64_t(monomials.size()) * limbs * branches;
        if (words * (e <= 32 ? 4 : 8) > TABLE_BYTES_LIMIT)
            throw std::length_error("checker table exceeds 64 MiB");
        if (e <= 32)
            coefficients = std::vector<uint32_t>(words);
        else
            coefficients = std::vector<uint64_t>(words);
    }
};

static uint64_t mask_at(const void *masks, uint32_t width, uint32_t i)
{
    return width == 32 ? static_cast<const uint32_t *>(masks)[i]
                       : static_cast<const uint64_t *>(masks)[i];
}
static void validate(const Checker &w, const void *masks, uint32_t width, const uint64_t *c,
                     uint32_t count)
{
    if ((width != 32 && width != 64) || count > TERM_LIMIT || (count && (!masks || !c)))
        throw std::invalid_argument("packed extents");
    for (uint32_t t = 0; t < count; ++t) {
        if (mask_at(masks, width, t) >> (w.x + w.y))
            throw std::invalid_argument("mask outside ring");
        if (w.equations % 64 && c[size_t(t) * w.limbs + w.limbs - 1] >> (w.equations % 64))
            throw std::invalid_argument("coefficient outside equations");
    }
}

template <typename Coefficient>
static int check(Checker &w, std::vector<Coefficient> &coefficients, const void *masks,
                 uint32_t width, const uint64_t *c, uint32_t count, const uint64_t *proof,
                 uint64_t proof_words, const uint64_t *roots, uint32_t root_count,
                 const uint64_t *terms, uint32_t term_count, const uint32_t *offsets,
                 uint32_t row_count, CheckStats &stats)
{
    validate(w, masks, width, c, count);
    if (!proof || proof_words != uint64_t(w.branches) * w.limbs || root_count > ROOT_LIMIT ||
        term_count > TERM_LIMIT || row_count > 4096 || (root_count && !roots) ||
        (term_count && !terms) || !offsets || offsets[0] || offsets[row_count] != term_count)
        return 6;
    for (uint32_t x = 0; x < w.branches; ++x)
        if (w.equations % 64 && proof[size_t(x) * w.limbs + w.limbs - 1] >> (w.equations % 64))
            return 6;
    for (uint32_t i = 0; i < root_count; ++i)
        if (roots[i] >> (w.x + w.y) || (i && roots[i - 1] >= roots[i])) return 2;
    std::vector<uint64_t> leading;
    for (uint32_t i = 0; i < row_count; ++i) {
        if (offsets[i] >= offsets[i + 1] || offsets[i + 1] > term_count) return 1;
        uint64_t lm = terms[offsets[i]];
        for (uint32_t t = offsets[i]; t < offsets[i + 1]; ++t) {
            uint64_t m = terms[t];
            if (m >> (w.x + w.y) || (t > offsets[i] && terms[t - 1] >= m)) return 1;
            int degree = __builtin_popcountll(m), prior = __builtin_popcountll(lm);
            if (degree > prior || (degree == prior && m < lm)) lm = m;
        }
        leading.push_back(lm);
    }
    auto table = [&](uint32_t feature, uint32_t limb) {
        return coefficients.data() + (size_t(feature) * w.limbs + limb) * w.branches;
    };
    stats.workspace_bytes = coefficients.size() * sizeof(Coefficient);
    stats.proof_bytes = proof_words * 8;
    auto started = std::chrono::steady_clock::now();
    std::fill(coefficients.begin(), coefficients.end(), 0);
    const uint64_t left_mask = (UINT64_C(1) << w.x) - 1;
    for (uint32_t t = 0; t < count; ++t) {
        bool nonzero = false;
        for (uint32_t l = 0; l < w.limbs; ++l) nonzero |= c[size_t(t) * w.limbs + l] != 0;
        if (!nonzero) continue;
        const uint64_t mask = mask_at(masks, width, t);
        uint32_t feature = w.index[mask >> w.x];
        if (feature == UINT32_MAX) return 7;
        for (uint32_t l = 0; l < w.limbs; ++l)
            coefficients[(size_t(feature) * w.limbs + l) * w.branches + (mask & left_mask)] ^=
                c[size_t(t) * w.limbs + l];
    }
    // Independently decoded feature-major slices, descending transform bits.
    for (size_t slice = 0; slice < w.monomials.size() * w.limbs; ++slice) {
        Coefficient *values = coefficients.data() + slice * w.branches;
        for (uint32_t bit = w.branches / 2; bit; bit >>= 1)
            for (uint32_t base = 0; base < w.branches; base += 2 * bit)
                for (uint32_t offset = 0; offset < bit; ++offset)
                    values[base + bit + offset] ^= values[base + offset];
    }
    stats.transform_xors = uint64_t(w.monomials.size()) * w.limbs * w.x * (w.branches / 2);
    auto specialized = std::chrono::steady_clock::now();
    stats.specialization = std::chrono::duration<double>(specialized - started).count();
    // Check a polynomial identity, not a producer's rank/consistency assertion:
    // sum_e u[e]*F_e(y) = 1. Every nonconstant coefficient must be zero.
    for (uint32_t feature = 0; feature < w.monomials.size(); ++feature) {
        const Coefficient *low = table(feature, 0);
        const Coefficient *high = w.limbs == 2 ? table(feature, 1) : nullptr;
        unsigned bad = 0;
        for (uint32_t x = 0; x < w.branches; ++x) {
            const uint64_t a = proof[size_t(x) * w.limbs], b = high ? proof[size_t(x) * 2 + 1] : 0;
            const unsigned parity =
                __builtin_parityll(a & low[x]) ^ (high ? __builtin_parityll(b & high[x]) : 0);
            bad |= (parity ^ unsigned(feature == 0)) & unsigned((a | b) != 0);
        }
        if (bad) return 9;
    }
    auto contradicted = std::chrono::steady_clock::now();
    stats.contradiction_check = std::chrono::duration<double>(contradicted - specialized).count();
    // A zero witness provides no information. Enumerate the COMPLETE original
    // y-space for that branch, in numeric order and without lifted solutions.
    for (uint32_t x = 0; x < w.branches; ++x) {
        ++stats.branches;
        if (proof[size_t(x) * w.limbs] || (w.limbs == 2 && proof[size_t(x) * 2 + 1])) {
            ++stats.contradictions;
            continue;
        }
        ++stats.enumerated_branches;
        for (uint32_t y = 0; y < (1u << w.y); ++y) {
            if (stats.assignments == BRANCH_CHECK_ENUMERATION_BUDGET) return 5;
            ++stats.assignments;
            std::array<uint64_t, 2> value{};
            for (uint32_t feature = 0; feature < w.monomials.size(); ++feature)
                if ((y & w.monomials[feature]) == w.monomials[feature])
                    for (uint32_t l = 0; l < w.limbs; ++l) value[l] ^= table(feature, l)[x];
            if (!(value[0] | value[1])) {
                if (stats.roots == ROOT_LIMIT) return 5;
                ++stats.roots;
            }
        }
    }
    auto enumerated = std::chrono::steady_clock::now();
    stats.enumeration = std::chrono::duration<double>(enumerated - contradicted).count();
    if (stats.roots != root_count) return 3;
    // Exact total count plus distinct actual roots proves completeness.
    for (uint32_t i = 0; i < root_count; ++i) {
        std::array<uint64_t, 2> value{};
        for (uint32_t t = 0; t < count; ++t)
            if ((mask_at(masks, width, t) & roots[i]) == mask_at(masks, width, t))
                for (uint32_t l = 0; l < w.limbs; ++l) value[l] ^= c[size_t(t) * w.limbs + l];
        if (value[0] | value[1]) return 2;
        for (uint32_t row = 0; row < row_count; ++row) {
            bool parity = false;
            for (uint32_t t = offsets[row]; t < offsets[row + 1]; ++t)
                parity ^= (terms[t] & roots[i]) == terms[t];
            if (parity) return 4;
        }
    }
    auto allowed = [&](uint64_t monomial) {
        for (auto lm : leading) {
            if (++stats.work > BRANCH_BASIS_PROOF_BUDGET)
                throw std::length_error("basis proof budget");
            if ((monomial & lm) == lm) return false;
        }
        return true;
    };
    std::vector<uint64_t> staircase;
    if (allowed(0)) staircase.push_back(0);
    for (size_t cursor = 0; cursor < staircase.size(); ++cursor) {
        auto m = staircase[cursor];
        const uint32_t first = m ? 64u - uint32_t(__builtin_clzll(m)) : 0;
        for (uint32_t j = first; j < w.x + w.y; ++j) {
            auto child = m | (UINT64_C(1) << j);
            if (allowed(child)) {
                if (staircase.size() == ROOT_LIMIT) return 5;
                staircase.push_back(child);
            }
        }
    }
    stats.standard = staircase.size();
    if (stats.standard != stats.roots) return 4;
    for (uint32_t i = 0; i < row_count; ++i) {
        for (uint32_t j = 0; j < row_count; ++j)
            if (i != j && (leading[i] & leading[j]) == leading[j]) return 4;
        for (uint32_t t = offsets[i]; t < offsets[i + 1]; ++t)
            if (terms[t] != leading[i])
                for (auto lm : leading)
                    if ((terms[t] & lm) == lm) return 4;
    }
    stats.basis_check =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - enumerated).count();
    return 0;
}

} // namespace
extern "C" uint32_t check_coefficient_bits(const void *p)
{
    return p ? (static_cast<const Checker *>(p)->equations <= 32 ? 32 : 64) : 0;
}
extern "C" uint64_t check_stats_size() { return sizeof(CheckStats); }
extern "C" void *check_create(uint32_t x, uint32_t y, uint32_t e)
{
    if (!x || x > 20 || !y || y > 10 || x + y > 30 || !e || e > 128) return nullptr;
    try {
        return new Checker(x, y, e);
    } catch (...) {
        return nullptr;
    }
}
extern "C" void check_destroy(void *p) { delete static_cast<Checker *>(p); }
extern "C" int branch_check(void *p, const void *masks, uint32_t width, const uint64_t *c,
                            uint32_t count, const uint64_t *proof, uint64_t proof_words,
                            const uint64_t *roots, uint32_t root_count, const uint64_t *terms,
                            uint32_t term_count, const uint32_t *offsets, uint32_t row_count,
                            CheckStats *stats)
{
    if (!p || !stats) return 6;
    *stats = {};
    try {
        auto &w = *static_cast<Checker *>(p);
        std::lock_guard<std::mutex> guard(w.mutex);
        return std::visit(
            [&](auto &coefficients) {
                return check(w, coefficients, masks, width, c, count, proof, proof_words, roots,
                             root_count, terms, term_count, offsets, row_count, *stats);
            },
            w.coefficients);
    } catch (const std::length_error &) {
        return 5;
    } catch (const std::invalid_argument &) {
        return 6;
    } catch (...) {
        return 8;
    }
}
extern "C" int branch_evaluate(void *p, const void *masks, uint32_t width, const uint64_t *c,
                               uint32_t count, uint64_t assignment, uint64_t *output)
{
    if (!p || !output) return 6;
    try {
        auto &w = *static_cast<Checker *>(p);
        std::lock_guard<std::mutex> guard(w.mutex);
        validate(w, masks, width, c, count);
        if (assignment >> (w.x + w.y)) return 6;
        output[0] = output[1] = 0;
        for (uint32_t t = 0; t < count; ++t)
            if ((mask_at(masks, width, t) & assignment) == mask_at(masks, width, t))
                for (uint32_t l = 0; l < w.limbs; ++l) output[l] ^= c[size_t(t) * w.limbs + l];
        return 0;
    } catch (const std::invalid_argument &) {
        return 6;
    } catch (...) {
        return 8;
    }
}
