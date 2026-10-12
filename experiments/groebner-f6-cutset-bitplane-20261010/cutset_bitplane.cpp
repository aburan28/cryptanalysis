// Exact target-bitplane queries over grouped, cutset-conditioned S3 layouts.
#include "../groebner-f6-grouped-factor-20261009/grouped_separator.cpp"

struct CutsetBitplaneResult {
    MessageResult message;
    uint64_t setup_static_assignments, setup_template_evaluations, plane_words;
    uint64_t query_xor_words, query_and_words, query_ns;
};

namespace {
struct CutsetBitplaneLayout {
    std::unique_ptr<MessageLayout> source;
    uint32_t target_bits, equations, states, words, boundary_bits;
    uint64_t template_evaluations;
    std::vector<uint64_t> static_allowed, planes;
    std::vector<uint64_t> template_offsets, template_monomials;
};

uint64_t expand_cutset_scope(uint32_t local, uint64_t scope) {
    uint64_t global = 0;
    uint32_t position = 0;
    for (uint64_t todo = scope; todo; todo &= todo - 1, ++position)
        if ((local >> position) & 1)
            global |= todo & (~todo + 1);
    return global;
}

void fill_cutset_setup(const CutsetBitplaneLayout& layout,
                       CutsetBitplaneResult& out) {
    const auto& source = *layout.source;
    out.message.result = source.setup;
    out.message.setup_factor_states = source.setup.factor_states;
    out.message.setup_elimination_states = source.setup.elimination_states;
    out.message.residual_factor_words = factor_words(source.residual);
    out.message.cached_witness_words = source.setup.witness_words;
    out.setup_static_assignments = layout.states;
    out.setup_template_evaluations = layout.template_evaluations;
    out.plane_words = layout.planes.size();
}

bool target_rows_zero(const CutsetBitplaneLayout& layout,
                      uint64_t assignment, uint32_t target_x) {
    const auto& offsets = layout.template_offsets;
    const auto& monomials = layout.template_monomials;
    for (uint32_t row = 0; row < layout.equations; ++row) {
        uint32_t parity = 0;
        for (uint64_t term = offsets[row]; term < offsets[row + 1]; ++term)
            parity ^= (assignment & monomials[term]) == monomials[term];
        for (uint32_t bit = 0; bit < layout.target_bits; ++bit) {
            if (!((target_x >> bit) & 1)) continue;
            uint32_t basis = 0;
            const uint64_t at = uint64_t(bit + 1) * layout.equations + row;
            for (uint64_t term = offsets[at]; term < offsets[at + 1]; ++term)
                basis ^= (assignment & monomials[term]) == monomials[term];
            uint32_t zero = 0;
            for (uint64_t term = offsets[row]; term < offsets[row + 1]; ++term)
                zero ^= (assignment & monomials[term]) == monomials[term];
            parity ^= basis ^ zero;
        }
        if (parity) return false;
    }
    return true;
}
}

extern "C" void* cutset_bitplane_create(
        uint32_t nvars, uint64_t static_equations, uint64_t static_terms,
        const uint64_t* static_offsets, const uint64_t* static_monomials,
        uint64_t prefix_equations, uint32_t group_rows, uint64_t boundary_mask,
        uint32_t max_bag, uint64_t max_states, uint32_t target_bits,
        uint32_t equations, uint64_t template_terms,
        const uint64_t* template_offsets, const uint64_t* template_monomials,
        CutsetBitplaneResult* out) {
    if (!out) return nullptr;
    *out = {};
    out->message.result.status = INVALID;
    const uint32_t boundary_bits = bits(boundary_mask);
    if (!target_bits || target_bits > 31 || target_bits != equations ||
        boundary_bits > 16 || !template_offsets ||
        (template_terms && !template_monomials) || template_terms > 1000000)
        return nullptr;
    const uint64_t template_equations = uint64_t(target_bits + 1) * equations;
    if (template_offsets[0] ||
        template_offsets[template_equations] != template_terms) return nullptr;
    for (uint64_t row = 0; row < template_equations; ++row)
        if (template_offsets[row] > template_offsets[row + 1] ||
            template_offsets[row + 1] > template_terms) return nullptr;
    for (uint64_t term = 0; term < template_terms; ++term)
        if (template_monomials[term] & ~boundary_mask) return nullptr;
    const uint32_t states = uint32_t(1) << boundary_bits;
    const uint32_t words = uint32_t(words_for(states));
    const uint64_t evaluations = template_equations * states;
    const uint64_t plane_words = template_equations * words;
    if (evaluations > max_states || plane_words > (UINT64_C(1) << 22)) {
        out->message.result.status = STATE_CAP;
        return nullptr;
    }
    try {
        MessageResult initial{};
        std::unique_ptr<MessageLayout> source(static_cast<MessageLayout*>(
            grouped_message_separator_create(nvars, static_equations,
                static_terms, static_offsets, static_monomials,
                prefix_equations, group_rows, boundary_mask,
                max_bag, max_states, &initial)));
        if (!source) {
            out->message = initial;
            return nullptr;
        }
        auto layout = std::make_unique<CutsetBitplaneLayout>();
        layout->source = std::move(source);
        layout->target_bits = target_bits;
        layout->equations = equations;
        layout->boundary_bits = boundary_bits;
        layout->states = states;
        layout->words = words;
        layout->template_evaluations = evaluations;
        layout->template_offsets.assign(template_offsets,
                                        template_offsets + template_equations + 1);
        if (template_terms)
            layout->template_monomials.assign(template_monomials,
                                               template_monomials + template_terms);
        layout->static_allowed.assign(words, 0);
        layout->planes.assign(plane_words, 0);
        for (uint32_t local = 0; local < states; ++local) {
            const uint64_t assignment = expand_cutset_scope(local, boundary_mask);
            bool feasible = !layout->source->static_unsat;
            if (feasible)
                for (const auto& factor : layout->source->residual)
                    if (!get(factor.allowed, local_index(assignment, factor.scope))) {
                        feasible = false;
                        break;
                    }
            if (feasible) set(layout->static_allowed, local);
            for (uint64_t row = 0; row < template_equations; ++row) {
                uint32_t parity = 0;
                for (uint64_t term = template_offsets[row];
                     term < template_offsets[row + 1]; ++term)
                    parity ^= ((assignment & template_monomials[term]) ==
                               template_monomials[term]);
                if (parity)
                    layout->planes[row * words + (local >> 6)] |=
                        UINT64_C(1) << (local & 63);
            }
        }
        for (uint32_t bit = 0; bit < target_bits; ++bit)
            for (uint32_t row = 0; row < equations; ++row)
                for (uint32_t word = 0; word < words; ++word) {
                    const uint64_t base = uint64_t(row) * words + word;
                    const uint64_t delta =
                        (uint64_t(bit + 1) * equations + row) * words + word;
                    layout->planes[delta] ^= layout->planes[base];
                }
        fill_cutset_setup(*layout, *out);
        out->message.result.status = SAT;
        return layout.release();
    } catch (const std::bad_alloc&) {
        out->message.result.status = INVALID;
        out->message.result.stage = 4;
        return nullptr;
    }
}

extern "C" int cutset_bitplane_run(const void* opaque, uint64_t target_x,
                                    uint64_t max_states,
                                    CutsetBitplaneResult* out) {
    if (!out) return int(INVALID);
    *out = {};
    out->message.result.status = INVALID;
    const auto* layout = static_cast<const CutsetBitplaneLayout*>(opaque);
    if (!layout || target_x >= (UINT64_C(1) << layout->target_bits) ||
        max_states > 200000000) return int(INVALID);
    fill_cutset_setup(*layout, *out);
    const auto& source = *layout->source;
    const uint64_t query_charge = uint64_t(layout->equations) * layout->states;
    if (source.setup.factor_states + source.setup.elimination_states > max_states ||
        query_charge > max_states - source.setup.factor_states -
                       source.setup.elimination_states) {
        out->message.result.status = STATE_CAP;
        out->message.result.stage = 2;
        return int(STATE_CAP);
    }
    out->message.result.factor_states += query_charge;
    out->message.result.width =
        std::max(out->message.result.width, uint64_t(layout->boundary_bits));
    const auto start = Clock::now();
    uint32_t selected[31] = {}, selected_count = 0;
    for (uint32_t bit = 0; bit < layout->target_bits; ++bit)
        if ((target_x >> bit) & 1) selected[selected_count++] = bit;
    for (uint32_t word = 0; word < layout->words; ++word) {
        uint64_t allowed = layout->static_allowed[word];
        if (!allowed) continue;
        for (uint32_t row = 0; row < layout->equations; ++row) {
            uint64_t value = layout->planes[uint64_t(row) * layout->words + word];
            for (uint32_t index = 0; index < selected_count; ++index) {
                const uint32_t bit = selected[index];
                value ^= layout->planes[
                    (uint64_t(bit + 1) * layout->equations + row) *
                    layout->words + word];
                ++out->query_xor_words;
            }
            allowed &= ~value;
            ++out->query_and_words;
            if (!allowed) break;
        }
        if (!allowed) continue;
        const uint32_t local = word * 64 + uint32_t(__builtin_ctzll(allowed));
        uint64_t assignment =
            expand_cutset_scope(local, source.boundary_mask);
        for (auto item = source.history.rbegin();
             item != source.history.rend(); ++item)
            if (get(item->witness_one, local_index(assignment, item->keep)))
                assignment |= UINT64_C(1) << item->variable;
        out->message.result.assignment = assignment;
        if (!solution_checks(assignment, source.source->offsets.size() - 1,
                             source.source->offsets.data(),
                             source.source->terms.data()) ||
            !target_rows_zero(*layout, assignment, uint32_t(target_x))) {
            out->message.result.status = INVALID;
            out->message.result.stage = 3;
            out->query_ns = elapsed(start);
            out->message.query_elimination_ns = out->query_ns;
            return int(INVALID);
        }
        out->message.result.status = SAT;
        out->message.result.stage = 3;
        out->query_ns = elapsed(start);
        out->message.query_elimination_ns = out->query_ns;
        return int(SAT);
    }
    out->message.result.status = UNSAT;
    out->message.result.stage = 2;
    out->query_ns = elapsed(start);
    out->message.query_elimination_ns = out->query_ns;
    return int(UNSAT);
}

extern "C" void cutset_bitplane_destroy(void* opaque) {
    delete static_cast<CutsetBitplaneLayout*>(opaque);
}
