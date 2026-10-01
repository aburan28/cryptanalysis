// Independent certificate checker. Reconstruct feature-major coefficient
// tables from the original input; never read producer rows, pivots or tables.
#include "abi.h"
#include "transform.h"
#include <algorithm>
#include <array>
#include <chrono>
#include <mutex>
#include <stdexcept>
#include <variant>
#include <vector>

namespace
{
thread_local PartialCheckStats partial_stats{};
thread_local SymmetryCheckStats symmetry_stats{};
thread_local TransformCheckStats transform_stats{};
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
    // Optional target-independent storage. Failure preserves the complete path.
    std::vector<uint32_t> record_offsets;
    std::vector<unsigned char> reuse;
    bool symmetry_requested = true;
    uint32_t transform_mode = 0;
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
        if (!(x & 1u) && uint64_t(branches) * 5 <= SYMMETRY_CHECK_AUX_BYTES) {
            try {
                record_offsets.resize(branches);
                reuse.resize(branches);
            } catch (const std::bad_alloc &) {
                std::vector<uint32_t>().swap(record_offsets);
                std::vector<unsigned char>().swap(reuse);
            }
        }
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

// This guard checks original ANF coefficients before specialization, using
// only this checker's freshly decoded table. No producer symmetry assertion
// or producer data structure is consulted. Duplicate input monomials have
// already canceled by XOR in the independent scatter.
static bool symmetry_charge(uint64_t amount = 1)
{
    if (amount > SYMMETRY_CHECK_WORK_BUDGET - symmetry_stats.work) {
        symmetry_stats.budget_fallback = 1;
        return false;
    }
    symmetry_stats.work += amount;
    return true;
}
static uint32_t swapped(const Checker &w, uint32_t branch)
{
    const uint32_t half = w.x / 2, mask = (1u << half) - 1;
    return ((branch & mask) << half) | (branch >> half);
}
template <typename Coefficient>
static bool prepare_symmetry(Checker &w, const std::vector<Coefficient> &coefficients,
                             const void *masks, uint32_t width, const uint64_t *input_coefficients,
                             uint32_t count, const uint64_t *proof, uint64_t prefix_words,
                             uint64_t entry_words, uint64_t proof_words)
{
    symmetry_stats.requested = w.symmetry_requested;
    symmetry_stats.workspace_bytes =
        uint64_t(w.record_offsets.size()) * sizeof(uint32_t) + w.reuse.size();
    if (!w.symmetry_requested) return false;
    if (w.x & 1u) {
        symmetry_stats.shape_fallback = 1;
        return false;
    }
    if (w.record_offsets.size() != w.branches || w.reuse.size() != w.branches) {
        symmetry_stats.workspace_fallback = 1;
        return false;
    }
    const auto started = std::chrono::steady_clock::now();
    struct Timer {
        std::chrono::steady_clock::time_point start;
        ~Timer()
        {
            symmetry_stats.guard_seconds =
                std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
        }
    } timer{started};
    // A mismatch has a nonzero coefficient on at least one side. Every
    // nonzero aggregate coefficient has at least one nonzero original term,
    // so visiting the input support is sufficient, even with duplicates,
    // cancellations, unsorted terms, or an absent swapped monomial.
    for (uint32_t t = 0; t < count; ++t) {
        if (!symmetry_charge()) return false;
        ++symmetry_stats.guard_terms;
        bool nonzero = false;
        for (uint32_t limb = 0; limb < w.limbs; ++limb)
            nonzero |= input_coefficients[size_t(t) * w.limbs + limb] != 0;
        if (!nonzero) continue;
        const uint64_t mask = mask_at(masks, width, t);
        const uint32_t a = uint32_t(mask & (w.branches - 1)), b = swapped(w, a);
        if (a == b) continue;
        ++symmetry_stats.guard_pairs;
        const uint32_t feature = w.index[mask >> w.x];
        for (uint32_t limb = 0; limb < w.limbs; ++limb) {
            if (!symmetry_charge()) return false;
            ++symmetry_stats.guard_coefficients;
            const auto *values =
                coefficients.data() + (size_t(feature) * w.limbs + limb) * w.branches;
            if (values[a] != values[b]) {
                symmetry_stats.asymmetric_fallback = 1;
                return false;
            }
        }
    }
    if (!symmetry_charge(uint64_t(w.branches) * 2)) return false;
    std::fill(w.record_offsets.begin(), w.record_offsets.end(), UINT32_MAX);
    std::fill(w.reuse.begin(), w.reuse.end(), 0);
    for (uint64_t offset = prefix_words; offset < proof_words; offset += entry_words) {
        if (!symmetry_charge()) return false;
        // Proof word limit is far below UINT32_MAX. Shape/order/padding was
        // validated before this function, including absence of overlaps.
        w.record_offsets[proof[offset] & ~PARTIAL_AFFINE_RECORD] = uint32_t(offset);
    }
    auto kind = [&](uint32_t branch) {
        if (proof[size_t(branch) * w.limbs] || (w.limbs == 2 && proof[size_t(branch) * 2 + 1]))
            return 1;
        const auto offset = w.record_offsets[branch];
        if (offset == UINT32_MAX) return 0;
        return (proof[offset] & PARTIAL_AFFINE_RECORD) ? 3 : 2;
    };
    uint64_t representatives = 0;
    for (uint32_t a = 0; a < w.branches; ++a) {
        const uint32_t b = swapped(w, a);
        if (a >= b) continue;
        if (!symmetry_charge()) return false;
        ++symmetry_stats.proof_pairs;
        const int ka = kind(a), kb = kind(b);
        bool equal = ka == kb;
        if (equal && ka) {
            const uint64_t oa = ka == 1 ? uint64_t(a) * w.limbs : w.record_offsets[a] + 1u;
            const uint64_t ob = ka == 1 ? uint64_t(b) * w.limbs : w.record_offsets[b] + 1u;
            const uint64_t words = ka == 1 ? w.limbs : entry_words - 1;
            for (uint64_t j = 0; j < words; ++j) {
                if (!symmetry_charge()) return false;
                ++symmetry_stats.proof_words;
                if (proof[oa + j] != proof[ob + j]) {
                    equal = false;
                    break;
                }
            }
        }
        if (!equal) {
            ++symmetry_stats.proof_mismatches;
            continue; // Different or absent certificates are checked in full.
        }
        w.reuse[a] = 2;
        w.reuse[b] = 1;
        ++representatives;
    }
    // Transactional enable: any budget failure above makes all stale or
    // partially prepared flags inaccessible for this query.
    symmetry_stats.representatives = representatives;
    symmetry_stats.enabled = 1;
    return true;
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
    const bool use_symmetry = prepare_symmetry(w, coefficients, masks, width, c, count, proof,
                                               prefix_words, entry_words, proof_words);
    // The symmetry guard above uses freshly scattered ORIGINAL coefficients.
    // General axis separation needs no symmetry. Symmetric kernels require
    // the guard to finish successfully, including all of its soft budgets.
    const auto transform_started = std::chrono::steady_clock::now();
    transform_stats.requested_mode = w.transform_mode;
    uint32_t selected = w.transform_mode;
    if (selected && (w.x & 1u)) {
        selected = 0;
        transform_stats.shape_fallback = 1;
    } else if (selected >= 2 && !use_symmetry) {
        selected = 0;
        transform_stats.symmetry_fallback = 1;
    }
    transform_stats.selected_mode = selected;
    transform_stats.slices = w.monomials.size() * w.limbs;
    transform_stats.word_bits = 8 * sizeof(Coefficient);
    transform_stats.full_xors = transform_stats.slices * w.x * (w.branches / 2);
#ifdef CHECKER_TRANSFORM_AUDIT
    // Explicit test build only. Account for the additional coefficient table
    // and independently replay the accepted complete transform below.
    std::vector<Coefficient> reference;
    if (selected) {
        reference = coefficients;
        transform_stats.audit_bytes = reference.size() * sizeof(Coefficient);
    }
#endif
    boolean_transform::Counts counts;
    for (size_t slice = 0; slice < transform_stats.slices; ++slice) {
        Coefficient *values = coefficients.data() + slice * w.branches;
        if (!selected) {
            // Preserve the accepted loop shape, including odd fixed splits.
            for (uint32_t bit = w.branches / 2; bit; bit >>= 1)
                for (uint32_t base = 0; base < w.branches; base += 2 * bit)
                    for (uint32_t offset = 0; offset < bit; ++offset)
                        values[base + bit + offset] ^= values[base + offset];
        } else {
            const uint32_t n = 1u << (w.x / 2);
            if (selected == 1) {
                boolean_transform::full(values, n, n, counts);
            } else {
                const uint32_t tile = selected == 2   ? 8
                                      : selected == 3 ? 16
                                      : selected == 4 ? 32
                                                      : n;
                boolean_transform::recursive_tiled(values, n, n, counts, tile);
            }
        }
    }
    transform_stats.actual_xors = selected ? counts.xors : transform_stats.full_xors;
    transform_stats.mirror_words = counts.copies;
    stats.transform_xors = transform_stats.actual_xors;
#ifdef CHECKER_TRANSFORM_AUDIT
    if (selected) {
        for (size_t slice = 0; slice < transform_stats.slices; ++slice) {
            Coefficient *values = reference.data() + slice * w.branches;
            for (uint32_t bit = w.branches / 2; bit; bit >>= 1)
                for (uint32_t base = 0; base < w.branches; base += 2 * bit)
                    for (uint32_t offset = 0; offset < bit; ++offset)
                        values[base + bit + offset] ^= values[base + offset];
        }
        transform_stats.audit_xors = transform_stats.full_xors;
        for (size_t i = 0; i < reference.size(); ++i) {
            ++transform_stats.audit_words;
            if (reference[i] != coefficients[i]) return 8;
        }
    }
#endif
    transform_stats.seconds =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - transform_started).count();
    auto specialized = std::chrono::steady_clock::now();
    stats.specialization = std::chrono::duration<double>(specialized - started).count();
    // Check a polynomial identity, not a producer's rank/consistency assertion:
    // sum_e u[e]*F_e(y) = 1. Every nonconstant coefficient must be zero.
    for (uint32_t feature = 0; feature < w.monomials.size(); ++feature) {
        const Coefficient *low = table(feature, 0);
        const Coefficient *high = w.limbs == 2 ? table(feature, 1) : nullptr;
        unsigned bad = 0;
        for (uint32_t x = 0; x < w.branches; ++x) {
            if (use_symmetry && w.reuse[x] == 1) {
                symmetry_stats.avoided_constant_parities += w.limbs;
                continue;
            }
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
        if (use_symmetry && w.reuse[branch] == 1) {
            symmetry_stats.avoided_multiplier_parities +=
                uint64_t(w.y + 1) * w.monomials.size() * w.limbs;
            continue;
        }
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
        stats.extended_contradictions += use_symmetry && w.reuse[branch] == 2 ? 2 : 1;
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
        if (use_symmetry && w.reuse[x] == 1) {
            ++symmetry_stats.inferred_aliases;
            if (partial)
                ++symmetry_stats.partial_aliases;
            else if (extended)
                ++symmetry_stats.multiplier_aliases;
            else if (proof[size_t(x) * w.limbs] || (w.limbs == 2 && proof[size_t(x) * 2 + 1]))
                ++symmetry_stats.constant_aliases;
            else
                ++symmetry_stats.enumerated_aliases;
            continue;
        }
        const uint64_t weight = use_symmetry && w.reuse[x] == 2 ? 2 : 1;
        if ((extended && !partial) || proof[size_t(x) * w.limbs] ||
            (w.limbs == 2 && proof[size_t(x) * 2 + 1])) {
            stats.contradictions += weight;
            continue;
        }
        if (partial) {
            PartialTimer timing;
            const auto space = affine_space(x, proof + record + 1);
            symmetry_stats.derived_partial_rank += (weight - 1) * space.rank;
            symmetry_stats.derived_partial_inconsistent += (weight - 1) * space.inconsistent;
            if (space.inconsistent) {
                stats.contradictions += weight;
                continue;
            }
            stats.enumerated_branches += weight;
            for (uint32_t bits = 0; bits < (1u << space.free_count); ++bits) {
                if (stats.assignments == BRANCH_CHECK_ENUMERATION_BUDGET) return 5;
                partial_charge();
                ++stats.assignments;
                symmetry_stats.avoided_assignments += weight - 1;
                symmetry_stats.derived_partial_assignments += weight - 1;
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
                    if (weight > ROOT_LIMIT - stats.roots) return 5;
                    stats.roots += weight;
                }
            }
            continue;
        }
        stats.enumerated_branches += weight;
        for (uint32_t y = 0; y < (1u << w.y); ++y) {
            if (stats.assignments == BRANCH_CHECK_ENUMERATION_BUDGET) return 5;
            ++stats.assignments;
            symmetry_stats.avoided_assignments += weight - 1;
            std::array<uint64_t, 2> value{};
            for (uint32_t feature = 0; feature < w.monomials.size(); ++feature)
                if ((y & w.monomials[feature]) == w.monomials[feature])
                    for (uint32_t l = 0; l < w.limbs; ++l) value[l] ^= table(feature, l)[x];
            if (!(value[0] | value[1])) {
                if (weight > ROOT_LIMIT - stats.roots) return 5;
                stats.roots += weight;
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
    symmetry_stats = {};
    transform_stats = {};
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

extern "C" uint64_t check_symmetry_stats_size() { return sizeof(SymmetryCheckStats); }
extern "C" const SymmetryCheckStats *check_last_symmetry_stats() { return &symmetry_stats; }
extern "C" int check_symmetry_configure(void *p, uint32_t enabled)
{
    if (!p || enabled > 1) return -1;
    auto &w = *static_cast<Checker *>(p);
    std::lock_guard<std::mutex> guard(w.mutex);
    w.symmetry_requested = enabled;
    return 0;
}

extern "C" uint64_t check_transform_stats_size() { return sizeof(TransformCheckStats); }
extern "C" const TransformCheckStats *check_last_transform_stats() { return &transform_stats; }
extern "C" int check_transform_configure(void *p, uint32_t mode)
{
    if (!p || mode > 5) return -1;
    auto &w = *static_cast<Checker *>(p);
    std::lock_guard<std::mutex> guard(w.mutex);
    w.transform_mode = mode;
    return 0;
}
