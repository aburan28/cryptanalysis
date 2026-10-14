// Exact bounded-width Boolean elimination with packed factor truth tables.
#include <algorithm>
#include <cstdint>
#include <limits>
#include <new>
#include <utility>
#include <vector>

struct PackedResult {
    uint64_t status, assignment, width, bag_variables, stage;
    uint64_t factor_states, elimination_states, transform_xors;
    uint64_t membership_tests, eliminated, peak_factor_words, witness_words;
};

namespace {
enum Status : uint64_t { SAT = 1, UNSAT = 2, WIDTH_CAP = 3, STATE_CAP = 4, INVALID = 5 };
struct Factor {
    uint64_t scope;
    std::vector<uint64_t> allowed;
};
struct History {
    uint32_t variable;
    uint64_t keep;
    std::vector<uint64_t> witness_one;
};
inline uint32_t bits(uint64_t mask) { return uint32_t(__builtin_popcountll(mask)); }
inline bool get(const std::vector<uint64_t>& words, uint32_t index) {
    return ((words[index >> 6] >> (index & 63)) & 1) != 0;
}
inline void set(std::vector<uint64_t>& words, uint32_t index) {
    words[index >> 6] |= UINT64_C(1) << (index & 63);
}
inline uint32_t local_index(uint64_t global, uint64_t scope) {
    uint32_t result = 0, position = 0;
    while (scope) {
        const uint64_t bit = scope & (~scope + 1);
        if (global & bit) result |= uint32_t(1) << position;
        scope ^= bit;
        ++position;
    }
    return result;
}
inline uint64_t words_for(uint64_t states) { return (states + 63) >> 6; }
uint64_t factor_words(const std::vector<Factor>& factors) {
    uint64_t count = 0;
    for (const auto& factor : factors) count += factor.allowed.size();
    return count;
}
bool solution_checks(uint64_t assignment, uint64_t equations,
                     const uint64_t* offsets, const uint64_t* terms) {
    for (uint64_t equation = 0; equation < equations; ++equation) {
        uint32_t parity = 0;
        for (uint64_t j = offsets[equation]; j < offsets[equation + 1]; ++j)
            parity ^= (assignment & terms[j]) == terms[j];
        if (parity) return false;
    }
    return true;
}
}

extern "C" int packed_separator_solve(uint32_t nvars, uint64_t equations,
        uint64_t total_terms, const uint64_t* offsets, const uint64_t* terms,
        uint32_t max_bag, uint64_t max_states, PackedResult* out) {
    if (!out) return int(INVALID);
    *out = {};
    auto stop = [&](Status status, uint64_t stage = 0) {
        out->status = status;
        out->stage = stage;
        return int(status);
    };
    if (nvars > 64 || max_bag > 24 || equations > 4096 ||
        total_terms > 1000000 || max_states > 200000000 || !offsets ||
        (total_terms && !terms) || offsets[0] != 0 ||
        offsets[equations] != total_terms) return stop(INVALID);
    const uint64_t ring = nvars == 64 ? std::numeric_limits<uint64_t>::max()
                                       : ((UINT64_C(1) << nvars) - 1);
    try {
        std::vector<Factor> factors;
        factors.reserve(equations);
        for (uint64_t equation = 0; equation < equations; ++equation) {
            const uint64_t begin = offsets[equation], end = offsets[equation + 1];
            if (begin > end || end > total_terms) return stop(INVALID);
            std::vector<uint64_t> sorted;
            sorted.reserve(end - begin);
            for (uint64_t j = begin; j < end; ++j) {
                if (terms[j] & ~ring) return stop(INVALID);
                sorted.push_back(terms[j]);
            }
            std::sort(sorted.begin(), sorted.end());
            std::vector<uint64_t> canonical;
            for (size_t i = 0; i < sorted.size();) {
                size_t j = i + 1;
                while (j < sorted.size() && sorted[j] == sorted[i]) ++j;
                if ((j - i) & 1) canonical.push_back(sorted[i]);
                i = j;
            }
            uint64_t scope = 0;
            for (uint64_t term : canonical) scope |= term;
            const uint32_t width = bits(scope);
            out->width = std::max(out->width, uint64_t(width));
            if (width > max_bag) {
                out->bag_variables = scope;
                return stop(WIDTH_CAP, 1);
            }
            const uint64_t states = UINT64_C(1) << width;
            if (states > max_states - out->factor_states - out->elimination_states)
                return stop(STATE_CAP, 1);
            out->factor_states += states;
            std::vector<uint8_t> value(states, 0);
            for (uint64_t term : canonical) value[local_index(term, scope)] ^= 1;
            for (uint32_t bit = 0; bit < width; ++bit) {
                const uint64_t stride = UINT64_C(1) << bit;
                for (uint64_t block = 0; block < states; block += 2 * stride)
                    for (uint64_t j = 0; j < stride; ++j)
                        value[block + stride + j] ^= value[block + j];
                out->transform_xors += states / 2;
            }
            Factor factor{scope, std::vector<uint64_t>(words_for(states), 0)};
            for (uint32_t local = 0; local < states; ++local)
                if (!value[local]) set(factor.allowed, local);
            factors.push_back(std::move(factor));
            out->peak_factor_words = std::max(out->peak_factor_words, factor_words(factors));
            if (std::all_of(factors.back().allowed.begin(), factors.back().allowed.end(),
                            [](uint64_t word) { return word == 0; })) return stop(UNSAT, 1);
        }
        uint64_t remaining = ring;
        std::vector<History> history;
        history.reserve(nvars);
        while (remaining) {
            uint32_t chosen = 0, best = 65;
            for (uint64_t todo = remaining; todo; todo &= todo - 1) {
                const uint32_t x = uint32_t(__builtin_ctzll(todo));
                const uint64_t xmask = UINT64_C(1) << x;
                uint64_t bag = xmask;
                for (const auto& factor : factors)
                    if (factor.scope & xmask) bag |= factor.scope;
                const uint32_t score = bits(bag);
                if (score < best || (score == best && x < chosen)) {
                    chosen = x;
                    best = score;
                }
            }
            const uint64_t xmask = UINT64_C(1) << chosen;
            std::vector<Factor> bucket, others;
            bucket.reserve(factors.size());
            others.reserve(factors.size());
            uint64_t bag = xmask;
            for (auto& factor : factors) {
                if (factor.scope & xmask) {
                    bag |= factor.scope;
                    bucket.push_back(std::move(factor));
                } else others.push_back(std::move(factor));
            }
            factors = std::move(others);
            const uint32_t width = bits(bag);
            out->width = std::max(out->width, uint64_t(width));
            if (width > max_bag) {
                out->bag_variables = bag;
                return stop(WIDTH_CAP, 2);
            }
            const uint64_t states = UINT64_C(1) << width;
            if (states > max_states - out->factor_states - out->elimination_states)
                return stop(STATE_CAP, 2);
            out->elimination_states += states;
            const uint64_t keep = bag ^ xmask;
            const uint32_t keep_states = uint32_t(UINT64_C(1) << (width - 1));
            std::vector<uint64_t> allowed(words_for(keep_states), 0);
            std::vector<uint64_t> witness_one(words_for(keep_states), 0);
            uint32_t bag_position[64] = {};
            uint32_t position = 0;
            for (uint64_t todo = bag; todo; todo &= todo - 1) {
                const uint32_t variable = uint32_t(__builtin_ctzll(todo));
                bag_position[variable] = position++;
            }
            const uint32_t xposition = bag_position[chosen];
            std::vector<std::vector<std::pair<uint32_t, uint32_t>>> updates(width);
            for (uint32_t f = 0; f < bucket.size(); ++f) {
                uint32_t local_bit = 0;
                for (uint64_t todo = bucket[f].scope; todo; todo &= todo - 1) {
                    const uint32_t variable = uint32_t(__builtin_ctzll(todo));
                    updates[bag_position[variable]].push_back({f, uint32_t(1) << local_bit});
                    ++local_bit;
                }
            }
            std::vector<uint32_t> index(bucket.size(), 0);
            for (uint32_t step = 0; step < states; ++step) {
                if (step) {
                    const uint32_t changed = uint32_t(__builtin_ctz(step));
                    for (const auto& update : updates[changed]) index[update.first] ^= update.second;
                }
                bool feasible = true;
                for (uint32_t f = 0; f < bucket.size(); ++f) {
                    ++out->membership_tests;
                    if (!get(bucket[f].allowed, index[f])) {
                        feasible = false;
                        break;
                    }
                }
                if (!feasible) continue;
                const uint32_t gray = step ^ (step >> 1);
                const uint32_t lower = (uint32_t(1) << xposition) - 1;
                const uint32_t projected = (gray & lower) |
                                           ((gray >> (xposition + 1)) << xposition);
                if (!get(allowed, projected)) {
                    set(allowed, projected);
                    if ((gray >> xposition) & 1) set(witness_one, projected);
                }
            }
            history.push_back({chosen, keep, std::move(witness_one)});
            out->witness_words += history.back().witness_one.size();
            ++out->eliminated;
            remaining ^= xmask;
            if (std::all_of(allowed.begin(), allowed.end(),
                            [](uint64_t word) { return word == 0; })) return stop(UNSAT, 2);
            factors.push_back({keep, std::move(allowed)});
            out->peak_factor_words = std::max(out->peak_factor_words, factor_words(factors));
        }
        for (const auto& factor : factors)
            if (!get(factor.allowed, 0)) return stop(UNSAT, 2);
        uint64_t assignment = 0;
        for (auto item = history.rbegin(); item != history.rend(); ++item)
            if (get(item->witness_one, local_index(assignment, item->keep)))
                assignment |= UINT64_C(1) << item->variable;
        if (!solution_checks(assignment, equations, offsets, terms)) return stop(INVALID, 3);
        out->assignment = assignment;
        return stop(SAT, 3);
    } catch (const std::bad_alloc&) {
        return stop(INVALID, 4);
    }
}
