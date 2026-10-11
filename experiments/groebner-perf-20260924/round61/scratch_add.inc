// Scratch is local to one matrix. Coefficients and witnesses are never
// retained across matrices or queries. Charge and emit at the same points
// as add(); a failed emit leaves the input row unchanged.
void scratch_add(Row &row, const Row &pivot, Poly &scratch, size_t cap)
{
    const size_t total = row.terms.size() + pivot.terms.size();
    charge(total);
    ++scratch_stats.xors;
    if (total > cap) {
        ++scratch_stats.fresh_vectors;
        Poly out;
        out.reserve(total);
        std::set_symmetric_difference(row.terms.begin(), row.terms.end(), pivot.terms.begin(),
                                      pivot.terms.end(), std::back_inserter(out));
        const uint32_t proof = emit(2, row.proof, pivot.proof);
        row = {std::move(out), proof};
        return;
    }
    scratch.clear();
    if (scratch.capacity() < total) {
        ++scratch_stats.growths;
        scratch.reserve(total);
    } else {
        ++scratch_stats.reused;
    }
    scratch_stats.peak_capacity_words =
        std::max<uint64_t>(scratch_stats.peak_capacity_words, scratch.capacity());
    std::set_symmetric_difference(row.terms.begin(), row.terms.end(), pivot.terms.begin(),
                                  pivot.terms.end(), std::back_inserter(scratch));
    const uint32_t proof = emit(2, row.proof, pivot.proof);
    row.terms.swap(scratch);
    row.proof = proof;
    // An initial row can own a larger allocation than the scratch cap.
    // Drop that allocation after the swap instead of retaining it.
    if (scratch.capacity() > cap) Poly{}.swap(scratch);
}

void trim_pivot(Row &row, size_t last_xor_capacity)
{
    if (row.terms.capacity() <= last_xor_capacity) return;
    Poly compact;
    compact.reserve(last_xor_capacity);
    compact.insert(compact.end(), row.terms.begin(), row.terms.end());
    ++scratch_stats.trimmed_pivots;
    scratch_stats.trimmed_capacity_words += row.terms.capacity() - last_xor_capacity;
    row.terms.swap(compact);
}
