// Build one exact truth table for several Boolean coordinates of one S3 link.
// The included implementation supplies the unchanged elimination and query ABI.
#include "../groebner-f6-message-20261009/message_separator.cpp"

namespace {
int build_group_factor(uint32_t nvars, uint64_t first, uint32_t group_rows,
                       const uint64_t* offsets, const uint64_t* terms,
                       uint32_t max_bag, uint64_t max_states,
                       PackedResult& out, std::vector<Factor>& factors) {
    const uint64_t ring = nvars == 64 ? std::numeric_limits<uint64_t>::max()
                                       : ((UINT64_C(1) << nvars) - 1);
    std::vector<std::vector<uint64_t>> rows(group_rows);
    uint64_t scope = 0;
    for (uint32_t i = 0; i < group_rows; ++i) {
        const uint64_t begin = offsets[first + i], end = offsets[first + i + 1];
        if (begin > end) return int(INVALID);
        std::vector<uint64_t> sorted;
        sorted.reserve(end - begin);
        for (uint64_t j = begin; j < end; ++j) {
            if (terms[j] & ~ring) return int(INVALID);
            sorted.push_back(terms[j]);
        }
        std::sort(sorted.begin(), sorted.end());
        for (size_t j = 0; j < sorted.size();) {
            size_t next = j + 1;
            while (next < sorted.size() && sorted[next] == sorted[j]) ++next;
            if ((next - j) & 1) {
                rows[i].push_back(sorted[j]);
                scope |= sorted[j];
            }
            j = next;
        }
    }
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

    // The low group_rows bits carry all coordinate polynomials through one
    // exact Boolean Möbius transform over the union of their variable scopes.
    std::vector<uint16_t> values(states, 0);
    for (uint32_t i = 0; i < group_rows; ++i)
        for (uint64_t term : rows[i])
            values[local_index(term, scope)] ^=
                uint16_t(uint32_t(1) << i);
    for (uint32_t bit = 0; bit < width; ++bit) {
        const uint64_t stride = UINT64_C(1) << bit;
        for (uint64_t block = 0; block < states; block += 2 * stride)
            for (uint64_t j = 0; j < stride; ++j)
                values[block + stride + j] ^= values[block + j];
        out.transform_xors += states / 2;
    }
    Factor factor{scope, std::vector<uint64_t>(words_for(states), 0)};
    for (uint32_t local = 0; local < states; ++local)
        if (values[local] == 0) set(factor.allowed, local);
    factors.push_back(std::move(factor));
    out.peak_factor_words = std::max(out.peak_factor_words,
                                     factor_words(factors));
    if (std::all_of(factors.back().allowed.begin(), factors.back().allowed.end(),
                    [](uint64_t word) { return word == 0; })) return int(UNSAT);
    return 0;
}
}

extern "C" void* grouped_message_separator_create(
        uint32_t nvars, uint64_t equations, uint64_t total_terms,
        const uint64_t* offsets, const uint64_t* terms,
        uint64_t prefix_equations, uint32_t group_rows,
        uint64_t boundary_mask, uint32_t max_bag, uint64_t max_states,
        MessageResult* out) {
    if (!out) return nullptr;
    *out = {};
    out->result.status = INVALID;
    const uint64_t ring = nvars == 64 ? std::numeric_limits<uint64_t>::max()
                                       : (nvars < 64 ? ((UINT64_C(1) << nvars) - 1) : 0);
    if (nvars > 64 || max_bag > 24 || max_states > 200000000 ||
        equations > 4096 || total_terms > 1000000 ||
        !offsets || (total_terms && !terms) || offsets[0] ||
        offsets[equations] != total_terms || (boundary_mask & ~ring) ||
        group_rows == 0 || group_rows > 16 ||
        prefix_equations > equations || prefix_equations % group_rows)
        return nullptr;
    for (uint64_t i = 0; i < equations; ++i)
        if (offsets[i] > offsets[i + 1] || offsets[i + 1] > total_terms)
            return nullptr;
    try {
        auto source = std::make_unique<Layout>(Layout{nvars, max_bag, equations,
            0, 0, 0, false, {}, {}, {}});
        source->offsets.assign(offsets, offsets + equations + 1);
        if (total_terms) source->terms.assign(terms, terms + total_terms);
        source->static_factors.reserve(prefix_equations / group_rows +
                                       equations - prefix_equations);
        for (uint64_t first = 0; first < prefix_equations; first += group_rows) {
            const int code = build_group_factor(nvars, first, group_rows,
                offsets, terms, max_bag, max_states, out->result,
                source->static_factors);
            if (code == int(UNSAT)) {
                source->always_unsat = true;
                break;
            }
            if (code) {
                out->result.status = uint64_t(code);
                out->result.stage = 1;
                return nullptr;
            }
        }
        if (!source->always_unsat)
            for (uint64_t i = prefix_equations; i < equations; ++i) {
                const int code = build_factor(nvars, offsets[i],
                    offsets[i + 1], terms, max_bag, max_states,
                    out->result, source->static_factors);
                if (code == int(UNSAT)) {
                    source->always_unsat = true;
                    break;
                }
                if (code) {
                    out->result.status = uint64_t(code);
                    out->result.stage = 1;
                    return nullptr;
                }
            }
        source->static_factor_states = out->result.factor_states;
        source->static_transform_xors = out->result.transform_xors;
        source->static_peak_words = out->result.peak_factor_words;
        auto layout = std::make_unique<MessageLayout>();
        layout->source = std::move(source);
        layout->boundary_mask = boundary_mask;
        layout->static_unsat = layout->source->always_unsat;
        layout->setup = out->result;
        layout->residual = layout->source->static_factors;
        if (!layout->static_unsat) {
            const int code = eliminate_static(nvars, max_bag, max_states,
                boundary_mask, layout->residual, layout->history,
                layout->setup);
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
