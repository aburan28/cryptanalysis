// Cache exact static elimination and its witnesses across fresh S3 targets.
#include "../groebner-f6-prepared-20261009/prepared_separator.cpp"

struct MessageResult {
    PackedResult result;
    uint64_t setup_factor_states, setup_elimination_states;
    uint64_t residual_factor_words, cached_witness_words;
    uint64_t copy_ns, dynamic_factor_ns, query_elimination_ns;
};

namespace {
struct MessageLayout {
    std::unique_ptr<Layout> source;
    uint64_t boundary_mask;
    bool static_unsat;
    PackedResult setup;
    std::vector<Factor> residual;
    std::vector<History> history;
};

int eliminate_static(uint32_t nvars, uint32_t max_bag, uint64_t max_states,
                     uint64_t boundary, std::vector<Factor>& factors,
                     std::vector<History>& history, PackedResult& out) {
    const uint64_t ring = nvars == 64 ? std::numeric_limits<uint64_t>::max()
                                       : ((UINT64_C(1) << nvars) - 1);
    uint64_t remaining = ring & ~boundary;
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
    return int(SAT);
}
}

extern "C" void* message_separator_create(uint32_t nvars, uint64_t equations,
        uint64_t total_terms, const uint64_t* offsets, const uint64_t* terms,
        uint64_t boundary_mask, uint32_t max_bag, uint64_t max_states,
        MessageResult* out) {
    if (!out) return nullptr;
    *out = {};
    out->result.status = INVALID;
    const uint64_t ring = nvars == 64 ? std::numeric_limits<uint64_t>::max()
                                       : (nvars < 64 ? ((UINT64_C(1) << nvars) - 1) : 0);
    if (nvars > 64 || (boundary_mask & ~ring)) return nullptr;
    try {
        PreparedResult initial{};
        std::unique_ptr<Layout> source(static_cast<Layout*>(prepared_separator_create(
            nvars, equations, total_terms, offsets, terms, equations,
            max_bag, max_states, &initial)));
        if (!source) {
            out->result = initial.result;
            return nullptr;
        }
        auto layout = std::make_unique<MessageLayout>();
        layout->source = std::move(source);
        layout->boundary_mask = boundary_mask;
        layout->static_unsat = layout->source->always_unsat;
        layout->setup = initial.result;
        layout->residual = layout->source->static_factors;
        if (!layout->static_unsat) {
            const int code = eliminate_static(nvars, max_bag, max_states,
                                              boundary_mask, layout->residual,
                                              layout->history, layout->setup);
            if (code == int(UNSAT)) layout->static_unsat = true;
            else if (code != int(SAT)) {
                out->result = layout->setup;
                out->result.status = uint64_t(code);
                return nullptr;
            }
        }
        out->setup_factor_states = layout->setup.factor_states;
        out->setup_elimination_states = layout->setup.elimination_states;
        out->residual_factor_words = factor_words(layout->residual);
        out->cached_witness_words = layout->setup.witness_words;
        out->result.status = SAT;
        return layout.release();
    } catch (const std::bad_alloc&) {
        out->result.status = INVALID;
        out->result.stage = 4;
        return nullptr;
    }
}

extern "C" int message_separator_run(const void* opaque, uint64_t equations,
        uint64_t total_terms, const uint64_t* offsets, const uint64_t* terms,
        uint64_t max_states, MessageResult* out) {
    if (!out) return int(INVALID);
    *out = {};
    out->result.status = INVALID;
    const auto* layout = static_cast<const MessageLayout*>(opaque);
    if (!layout || equations > 4096 || total_terms > 1000000 ||
        max_states > 200000000 || !offsets || (total_terms && !terms) ||
        offsets[0] || offsets[equations] != total_terms) return int(INVALID);
    for (uint64_t i = 0; i < equations; ++i) {
        if (offsets[i] > offsets[i + 1] || offsets[i + 1] > total_terms)
            return int(INVALID);
        for (uint64_t j = offsets[i]; j < offsets[i + 1]; ++j)
            if (terms[j] & ~layout->boundary_mask) return int(INVALID);
    }
    try {
        const auto copied = Clock::now();
        std::vector<Factor> factors = layout->residual;
        out->copy_ns = elapsed(copied);
        out->result = layout->setup;
        out->result.status = INVALID;
        out->setup_factor_states = layout->setup.factor_states;
        out->setup_elimination_states = layout->setup.elimination_states;
        out->residual_factor_words = factor_words(layout->residual);
        out->cached_witness_words = layout->setup.witness_words;
        if (layout->static_unsat) {
            out->result.status = UNSAT;
            out->result.stage = 2;
            return int(UNSAT);
        }
        const auto dynamic_start = Clock::now();
        for (uint64_t i = 0; i < equations; ++i) {
            const int code = build_factor(layout->source->nvars, offsets[i],
                                          offsets[i + 1], terms,
                                          layout->source->max_bag, max_states,
                                          out->result, factors);
            if (code) {
                out->result.status = uint64_t(code);
                out->result.stage = 1;
                out->dynamic_factor_ns = elapsed(dynamic_start);
                return code;
            }
        }
        out->dynamic_factor_ns = elapsed(dynamic_start);
        out->result.peak_factor_words =
            std::max(out->result.peak_factor_words, factor_words(factors));
        const auto reduction_start = Clock::now();
        const int code = eliminate(layout->source->nvars, layout->source->max_bag,
                                   max_states, std::move(factors), out->result);
        out->query_elimination_ns = elapsed(reduction_start);
        out->result.status = uint64_t(code);
        if (code == int(SAT)) {
            uint64_t assignment = out->result.assignment;
            for (auto item = layout->history.rbegin(); item != layout->history.rend(); ++item)
                if (get(item->witness_one, local_index(assignment, item->keep)))
                    assignment |= UINT64_C(1) << item->variable;
            out->result.assignment = assignment;
            if (!solution_checks(assignment, layout->source->offsets.size() - 1,
                                 layout->source->offsets.data(),
                                 layout->source->terms.data()) ||
                !solution_checks(assignment, equations, offsets, terms)) {
                out->result.status = INVALID;
                return int(INVALID);
            }
        }
        return code;
    } catch (const std::bad_alloc&) {
        out->result.status = INVALID;
        out->result.stage = 4;
        return int(INVALID);
    }
}

extern "C" void message_separator_destroy(void* opaque) {
    delete static_cast<MessageLayout*>(opaque);
}
