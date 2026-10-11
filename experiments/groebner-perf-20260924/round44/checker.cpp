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
thread_local PartialCheckStats partial_stats{};
struct PartialTimer {
    std::chrono::steady_clock::time_point start = std::chrono::steady_clock::now();
    ~PartialTimer()
    {
        partial_stats.seconds +=
            std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
    }
};
struct AffineSpace {
    std::array<uint32_t, 11> rows{};
    std::array<uint32_t, 10> pivots{}, free_columns{};
    uint32_t rank = 0, free_count = 0;
    bool inconsistent = false;
};
static void partial_charge()
{
    if (partial_stats.work >= PARTIAL_CHECK_WORK_BUDGET)
        throw std::length_error("partial affine checker work budget");
    ++partial_stats.work;
}

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
                 uint32_t row_count, MultiplierCheckStats &stats)
{
    validate(w, masks, width, c, count);
    const uint64_t prefix_words = uint64_t(w.branches) * w.limbs;
    const uint64_t entry_words = 1 + uint64_t(w.y + 1) * w.limbs;
    if (!proof || proof_words < prefix_words || proof_words > MULTIPLIER_PROOF_WORDS_LIMIT ||
        (proof_words - prefix_words) % entry_words ||
        (proof_words - prefix_words) / entry_words > w.branches || root_count > ROOT_LIMIT ||
        term_count > TERM_LIMIT || row_count > 4096 || (root_count && !roots) ||
        (term_count && !terms) || !offsets || offsets[0] || offsets[row_count] != term_count)
        return 6;
    for (uint32_t x = 0; x < w.branches; ++x)
        if (w.equations % 64 && proof[size_t(x) * w.limbs + w.limbs - 1] >> (w.equations % 64))
            return 6;
    uint64_t previous_branch = 0;
    for (uint64_t offset = prefix_words; offset < proof_words; offset += entry_words) {
        const uint64_t branch = proof[offset] & ~PARTIAL_AFFINE_RECORD;
        if (branch >= w.branches || (offset != prefix_words && branch <= previous_branch)) return 6;
        previous_branch = branch;
        // Redundant overlapping records are rejected to keep accounting exact.
        for (uint32_t limb = 0; limb < w.limbs; ++limb)
            if (proof[branch * w.limbs + limb]) return 6;
        for (uint32_t slot = 0; slot <= w.y; ++slot)
            if (w.equations % 64 &&
                proof[offset + 1 + size_t(slot) * w.limbs + w.limbs - 1] >> (w.equations % 64))
                return 6;
    }
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
    auto affine_space = [&](uint32_t branch, const uint64_t *witnesses) {
        AffineSpace space;
        partial_stats.stack_bytes = sizeof(space);
        ++partial_stats.records;
        const uint32_t row_count = w.y + 1;
        for (uint32_t row = 0; row < row_count; ++row) {
            partial_charge();
            const uint64_t *u = witnesses + size_t(row) * w.limbs;
            if (!(u[0] | (w.limbs == 2 ? u[1] : 0))) continue;
            ++partial_stats.checked_rows;
            for (uint32_t feature = 0; feature < w.monomials.size(); ++feature) {
                unsigned parity = 0;
                for (uint32_t limb = 0; limb < w.limbs; ++limb) {
                    partial_charge();
                    parity ^= __builtin_parityll(u[limb] & table(feature, limb)[branch]);
                    ++partial_stats.witness_parities;
                }
                if (!parity) continue;
                const uint32_t monomial = w.monomials[feature];
                if (monomial & (monomial - 1))
                    throw std::domain_error("partial consequence is nonlinear");
                const uint32_t column = monomial ? 1u + uint32_t(__builtin_ctz(monomial)) : 0;
                space.rows[row] ^= 1u << column;
            }
        }
        // Recompute rank and pivots from original-equation consequences;
        // no producer elimination state is accepted.
        for (uint32_t column = 1; column <= w.y; ++column) {
            uint32_t selected = space.rank;
            for (; selected < row_count; ++selected) {
                partial_charge();
                if (space.rows[selected] & (1u << column)) break;
            }
            if (selected == row_count) continue;
            std::swap(space.rows[selected], space.rows[space.rank]);
            for (uint32_t row = 0; row < row_count; ++row) {
                partial_charge();
                if (row != space.rank && (space.rows[row] & (1u << column))) {
                    space.rows[row] ^= space.rows[space.rank];
                    ++partial_stats.row_xors;
                }
            }
            space.pivots[space.rank++] = column - 1;
        }
        partial_stats.rank_sum += space.rank;
        for (uint32_t row = 0; row < row_count; ++row) {
            partial_charge();
            if (space.rows[row] == 1) {
                space.inconsistent = true;
                ++partial_stats.inconsistent;
                return space;
            }
        }
        for (uint32_t column = 0; column < w.y; ++column) {
            bool pivot = false;
            for (uint32_t row = 0; row < space.rank; ++row) pivot |= space.pivots[row] == column;
            if (!pivot) space.free_columns[space.free_count++] = column;
        }
        return space;
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
    // Independently multiply the reconstructed original equations in the
    // Boolean quotient. Numeric monomial masks and a dense parity array do
    // not share the producer's cubic-column layout or elimination state.
    for (uint64_t offset = prefix_words; offset < proof_words; offset += entry_words) {
        if (proof[offset] & PARTIAL_AFFINE_RECORD) continue;
        const uint32_t branch = uint32_t(proof[offset]);
        std::array<unsigned char, 1024> identity{};
        for (uint32_t slot = 0; slot <= w.y; ++slot) {
            const uint32_t multiplier = slot ? 1u << (slot - 1) : 0;
            const uint64_t *u = proof + offset + 1 + size_t(slot) * w.limbs;
            for (uint32_t feature = 0; feature < w.monomials.size(); ++feature) {
                unsigned parity = 0;
                for (uint32_t limb = 0; limb < w.limbs; ++limb) {
                    parity ^= __builtin_parityll(u[limb] & table(feature, limb)[branch]);
                    ++stats.multiplier_parities;
                }
                identity[w.monomials[feature] | multiplier] ^= parity;
            }
        }
        if (identity[0] != 1) return 9;
        for (uint32_t monomial = 1; monomial < (1u << w.y); ++monomial)
            if (identity[monomial]) return 9;
        ++stats.extended_contradictions;
        stats.multiplier_words += entry_words - 1;
    }
    auto multiplied = std::chrono::steady_clock::now();
    stats.multiplier_check = std::chrono::duration<double>(multiplied - contradicted).count();
    uint64_t extension = prefix_words;
    // A zero witness provides no information. Enumerate the COMPLETE original
    // y-space for that branch, in numeric order and without lifted solutions.
    for (uint32_t x = 0; x < w.branches; ++x) {
        ++stats.branches;
        const uint64_t record = extension;
        const bool extended =
            extension < proof_words && (proof[extension] & ~PARTIAL_AFFINE_RECORD) == x;
        const bool partial = extended && (proof[extension] & PARTIAL_AFFINE_RECORD);
        if (extended) extension += entry_words;
        if ((extended && !partial) || proof[size_t(x) * w.limbs] ||
            (w.limbs == 2 && proof[size_t(x) * 2 + 1])) {
            ++stats.contradictions;
            continue;
        }
        if (partial) {
            PartialTimer timing;
            const auto space = affine_space(x, proof + record + 1);
            if (space.inconsistent) {
                ++stats.contradictions;
                continue;
            }
            ++stats.enumerated_branches;
            for (uint32_t bits = 0; bits < (1u << space.free_count); ++bits) {
                if (stats.assignments == BRANCH_CHECK_ENUMERATION_BUDGET) return 5;
                partial_charge();
                ++stats.assignments;
                ++partial_stats.assignments;
                uint32_t assignment = 0;
                for (uint32_t i = 0; i < space.free_count; ++i)
                    assignment |= ((bits >> i) & 1u) << space.free_columns[i];
                for (uint32_t row = 0; row < space.rank; ++row) {
                    partial_charge();
                    const unsigned bit = (space.rows[row] & 1u) ^
                                         __builtin_parity((space.rows[row] >> 1) & assignment);
                    assignment |= bit << space.pivots[row];
                }
                std::array<uint64_t, 2> value{};
                for (uint32_t feature = 0; feature < w.monomials.size(); ++feature) {
                    partial_charge();
                    if ((assignment & w.monomials[feature]) == w.monomials[feature])
                        for (uint32_t limb = 0; limb < w.limbs; ++limb) {
                            partial_charge();
                            value[limb] ^= table(feature, limb)[x];
                        }
                }
                if (!(value[0] | value[1])) {
                    if (stats.roots == ROOT_LIMIT) return 5;
                    ++stats.roots;
                }
            }
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
    stats.enumeration = std::chrono::duration<double>(enumerated - multiplied).count();
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
extern "C" uint64_t check_stats_size() { return sizeof(MultiplierCheckStats); }
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
                            MultiplierCheckStats *stats)
{
    partial_stats = {};
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
    } catch (const std::domain_error &) {
        return 9;
    } catch (...) {
        return 8;
    }
}
extern "C" uint64_t check_partial_stats_size() { return sizeof(PartialCheckStats); }
extern "C" const PartialCheckStats *check_last_partial_stats() { return &partial_stats; }
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
