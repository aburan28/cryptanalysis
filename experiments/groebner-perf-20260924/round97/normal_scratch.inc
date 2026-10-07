// Inputs are descending grevlex, with the same comparator as ordered_add().
// Scratch belongs to one normal() invocation, including a chain probe. Emit
// the witness before replacing row so node exhaustion leaves its input intact.
void ordered_scratch_add(Row &row, const Row &other, Poly &scratch, size_t cap)
{
    const size_t total = row.terms.size() + other.terms.size();
    charge(total);
    normal_count(normal_scratch_stats.calls);
    normal_count(normal_scratch_stats.charged_terms, total);
    auto compare = [](Mask a, Mask b) { return less_monomial(b, a); };
    if (total > cap) {
        Poly out;
        out.reserve(total);
        normal_count(normal_scratch_stats.fresh_vectors);
        std::set_symmetric_difference(row.terms.begin(), row.terms.end(), other.terms.begin(),
                                      other.terms.end(), std::back_inserter(out), compare);
        const uint32_t proof = emit(2, row.proof, other.proof);
        row = {std::move(out), proof};
        normal_count(normal_scratch_stats.completed);
        return;
    }
    scratch.clear();
    if (scratch.capacity() < total) {
        scratch.reserve(total);
        normal_count(normal_scratch_stats.growths);
    } else
        normal_count(normal_scratch_stats.reused);
    normal_scratch_stats.peak_scratch_capacity =
        std::max<uint64_t>(normal_scratch_stats.peak_scratch_capacity, scratch.capacity());
    std::set_symmetric_difference(row.terms.begin(), row.terms.end(), other.terms.begin(),
                                  other.terms.end(), std::back_inserter(scratch), compare);
    const uint32_t proof = emit(2, row.proof, other.proof);
    row.terms.swap(scratch);
    row.proof = proof;
    normal_count(normal_scratch_stats.completed);
    normal_scratch_stats.peak_scratch_capacity =
        std::max<uint64_t>(normal_scratch_stats.peak_scratch_capacity, scratch.capacity());
    // The old input may own more storage than this scratch policy permits.
    if (scratch.capacity() > cap) {
        normal_count(normal_scratch_stats.oversized_releases);
        normal_count(normal_scratch_stats.released_capacity_words, scratch.capacity());
        Poly{}.swap(scratch);
    }
    normal_scratch_stats.peak_retained_scratch_capacity =
        std::max<uint64_t>(normal_scratch_stats.peak_retained_scratch_capacity, scratch.capacity());
}
