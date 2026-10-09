// Reuse immutable target-independent Boolean factors across fresh queries.
// Include the frozen baseline implementation for its factor and ABI contracts.
#include "../groebner-f6-packed-20261009/packed_separator.cpp"
#include <chrono>
#include <memory>

struct PreparedResult {
    PackedResult result;
    uint64_t reused_factor_states, reused_transform_xors, cached_factor_words;
    uint64_t copy_ns, dynamic_factor_ns, elimination_ns;
};

namespace {
using Clock = std::chrono::steady_clock;
uint64_t elapsed(Clock::time_point before) {
    return uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - before).count());
}
struct Layout {
    uint32_t nvars, max_bag;
    uint64_t insert_after, static_factor_states, static_transform_xors;
    uint64_t static_peak_words;
    bool always_unsat;
    std::vector<Factor> static_factors;
    std::vector<uint64_t> offsets, terms;
};
int build_factor(uint32_t nvars, uint64_t begin, uint64_t end,
                 const uint64_t* terms, uint32_t max_bag, uint64_t max_states,
                 PackedResult& out, std::vector<Factor>& factors) {
    if (begin > end) return int(INVALID);
    const uint64_t ring = nvars == 64 ? std::numeric_limits<uint64_t>::max()
                                       : ((UINT64_C(1) << nvars) - 1);
    std::vector<uint64_t> sorted;
    sorted.reserve(end - begin);
    for (uint64_t j = begin; j < end; ++j) {
        if (terms[j] & ~ring) return int(INVALID);
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
    out.width = std::max(out.width, uint64_t(width));
    if (width > max_bag) {
        out.bag_variables = scope;
        return int(WIDTH_CAP);
    }
    const uint64_t states = UINT64_C(1) << width;
    if (out.factor_states + out.elimination_states > max_states ||
        states > max_states - out.factor_states - out.elimination_states)
        return int(STATE_CAP);
    out.factor_states += states;
    std::vector<uint8_t> value(states, 0);
    for (uint64_t term : canonical) value[local_index(term, scope)] ^= 1;
    for (uint32_t bit = 0; bit < width; ++bit) {
        const uint64_t stride = UINT64_C(1) << bit;
        for (uint64_t block = 0; block < states; block += 2 * stride)
            for (uint64_t j = 0; j < stride; ++j)
                value[block + stride + j] ^= value[block + j];
        out.transform_xors += states / 2;
    }
    Factor factor{scope, std::vector<uint64_t>(words_for(states), 0)};
    for (uint32_t local = 0; local < states; ++local)
        if (!value[local]) set(factor.allowed, local);
    factors.push_back(std::move(factor));
    out.peak_factor_words = std::max(out.peak_factor_words, factor_words(factors));
    if (std::all_of(factors.back().allowed.begin(), factors.back().allowed.end(),
                    [](uint64_t word) { return word == 0; })) return int(UNSAT);
    return 0;
}
int eliminate(uint32_t nvars, uint32_t max_bag, uint64_t max_states,
              std::vector<Factor> factors, PackedResult& out) {
    const uint64_t ring = nvars == 64 ? std::numeric_limits<uint64_t>::max()
                                       : ((UINT64_C(1) << nvars) - 1);
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
        out.width = std::max(out.width, uint64_t(width));
        if (width > max_bag) {
            out.bag_variables = bag;
            out.stage = 2;
            return int(WIDTH_CAP);
        }
        const uint64_t states = UINT64_C(1) << width;
        if (out.factor_states + out.elimination_states > max_states ||
            states > max_states - out.factor_states - out.elimination_states) {
            out.stage = 2;
            return int(STATE_CAP);
        }
        out.elimination_states += states;
        const uint64_t keep = bag ^ xmask;
        const uint32_t keep_states = uint32_t(UINT64_C(1) << (width - 1));
        std::vector<uint64_t> allowed(words_for(keep_states), 0);
        std::vector<uint64_t> witness_one(words_for(keep_states), 0);
        uint32_t bag_position[64] = {};
        uint32_t position = 0;
        for (uint64_t todo = bag; todo; todo &= todo - 1)
            bag_position[uint32_t(__builtin_ctzll(todo))] = position++;
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
                ++out.membership_tests;
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
        out.witness_words += history.back().witness_one.size();
        ++out.eliminated;
        remaining ^= xmask;
        if (std::all_of(allowed.begin(), allowed.end(),
                        [](uint64_t word) { return word == 0; })) {
            out.stage = 2;
            return int(UNSAT);
        }
        factors.push_back({keep, std::move(allowed)});
        out.peak_factor_words = std::max(out.peak_factor_words, factor_words(factors));
    }
    for (const auto& factor : factors)
        if (!get(factor.allowed, 0)) {
            out.stage = 2;
            return int(UNSAT);
        }
    uint64_t assignment = 0;
    for (auto item = history.rbegin(); item != history.rend(); ++item)
        if (get(item->witness_one, local_index(assignment, item->keep)))
            assignment |= UINT64_C(1) << item->variable;
    out.assignment = assignment;
    out.stage = 3;
    return int(SAT);
}
bool checks_all(const Layout& layout, uint64_t dynamic_equations,
                const uint64_t* dynamic_offsets, const uint64_t* dynamic_terms,
                uint64_t assignment) {
    return solution_checks(assignment, layout.static_factors.size(),
                           layout.offsets.data(), layout.terms.data()) &&
           solution_checks(assignment, dynamic_equations, dynamic_offsets, dynamic_terms);
}
}

extern "C" void* prepared_separator_create(uint32_t nvars, uint64_t equations,
        uint64_t total_terms, const uint64_t* offsets, const uint64_t* terms,
        uint64_t insert_after, uint32_t max_bag, uint64_t max_states,
        PreparedResult* out) {
    if (!out) return nullptr;
    *out = {};
    out->result.status = INVALID;
    if (nvars > 64 || max_bag > 24 || equations > 4096 ||
        total_terms > 1000000 || max_states > 200000000 ||
        insert_after > equations || !offsets ||
        (total_terms && !terms) || offsets[0] || offsets[equations] != total_terms)
        return nullptr;
    try {
        auto layout = std::make_unique<Layout>(Layout{nvars, max_bag, insert_after,
                                                     0, 0, 0, false, {}, {}, {}});
        layout->offsets.assign(offsets, offsets + equations + 1);
        if (total_terms) layout->terms.assign(terms, terms + total_terms);
        layout->static_factors.reserve(equations);
        for (uint64_t i = 0; i < equations; ++i) {
            if (offsets[i] > offsets[i + 1] || offsets[i + 1] > total_terms) {
                out->result.status = INVALID;
                return nullptr;
            }
            const int code = build_factor(nvars, offsets[i], offsets[i + 1], terms,
                                          max_bag, max_states, out->result,
                                          layout->static_factors);
            if (code == int(UNSAT)) layout->always_unsat = true;
            else if (code != 0) {
                out->result.status = uint64_t(code);
                out->result.stage = 1;
                return nullptr;
            }
        }
        layout->static_factor_states = out->result.factor_states;
        layout->static_transform_xors = out->result.transform_xors;
        layout->static_peak_words = out->result.peak_factor_words;
        out->reused_factor_states = layout->static_factor_states;
        out->reused_transform_xors = layout->static_transform_xors;
        out->cached_factor_words = factor_words(layout->static_factors);
        out->result.status = SAT; // A ready layout, including an unsatisfiable static system.
        return layout.release();
    } catch (const std::bad_alloc&) {
        out->result.status = INVALID;
        out->result.stage = 4;
        return nullptr;
    }
}

extern "C" int prepared_separator_run(const void* opaque, uint64_t dynamic_equations,
        uint64_t dynamic_terms_count, const uint64_t* offsets, const uint64_t* terms,
        uint64_t max_states, PreparedResult* out) {
    if (!out) return int(INVALID);
    *out = {};
    out->result.status = INVALID;
    const auto* layout = static_cast<const Layout*>(opaque);
    if (!layout || dynamic_equations > 4096 || dynamic_terms_count > 1000000 ||
        max_states > 200000000 || !offsets ||
        (dynamic_terms_count && !terms) || offsets[0] ||
        offsets[dynamic_equations] != dynamic_terms_count)
        return int(INVALID);
    try {
        const auto copied = Clock::now();
        std::vector<Factor> factors;
        factors.reserve(layout->static_factors.size() + dynamic_equations);
        factors.insert(factors.end(), layout->static_factors.begin(),
                       layout->static_factors.begin() + layout->insert_after);
        out->copy_ns = elapsed(copied);
        out->result.factor_states = layout->static_factor_states;
        out->result.transform_xors = layout->static_transform_xors;
        out->result.peak_factor_words = layout->static_peak_words;
        out->reused_factor_states = layout->static_factor_states;
        out->reused_transform_xors = layout->static_transform_xors;
        out->cached_factor_words = factor_words(layout->static_factors);
        if (layout->always_unsat) {
            out->result.status = UNSAT;
            out->result.stage = 1;
            return int(UNSAT);
        }
        const auto dynamic_start = Clock::now();
        for (uint64_t i = 0; i < dynamic_equations; ++i) {
            if (offsets[i] > offsets[i + 1] || offsets[i + 1] > dynamic_terms_count)
                return int(INVALID);
            const int code = build_factor(layout->nvars, offsets[i], offsets[i + 1],
                                          terms, layout->max_bag, max_states,
                                          out->result, factors);
            if (code) {
                out->result.status = uint64_t(code);
                out->result.stage = 1;
                out->dynamic_factor_ns = elapsed(dynamic_start);
                return code;
            }
        }
        out->dynamic_factor_ns = elapsed(dynamic_start);
        const auto suffix_copy = Clock::now();
        factors.insert(factors.end(),
                       layout->static_factors.begin() + layout->insert_after,
                       layout->static_factors.end());
        out->copy_ns += elapsed(suffix_copy);
        const auto reduction_start = Clock::now();
        const int code = eliminate(layout->nvars, layout->max_bag, max_states,
                                   std::move(factors), out->result);
        out->elimination_ns = elapsed(reduction_start);
        out->result.status = uint64_t(code);
        if (code == int(SAT) && !checks_all(*layout, dynamic_equations, offsets,
                                            terms, out->result.assignment)) {
            out->result.status = INVALID;
            return int(INVALID);
        }
        return code;
    } catch (const std::bad_alloc&) {
        out->result.status = INVALID;
        out->result.stage = 4;
        return int(INVALID);
    }
}

extern "C" void prepared_separator_destroy(void* opaque) {
    delete static_cast<Layout*>(opaque);
}
