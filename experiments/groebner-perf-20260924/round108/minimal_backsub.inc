// Selection depends only on the immutable leading pivot columns.
// Charge the complete flag initialization, including unused columns.
charge(l.columns.size());
std::vector<uint8_t> selected(l.columns.size(), 0);
Masks minimal;
for (size_t c = l.columns.size(); c-- > 0;) {
    if (slots[c] == UINT32_MAX) continue;
    bool redundant = false;
    for (auto lm : minimal) {
        charge();
        if ((lm & l.columns[c]) == lm) {
            redundant = true;
            break;
        }
    }
    if (redundant) continue;
    minimal.push_back(l.columns[c]);
    selected[c] = 1;
}
// Only retained rows need RREF tails. Clear later pivots left to right:
// an echelon reducer can introduce only still-later pivot columns.
// Later retained rows may already be reduced, which preserves this
// invariant. The resulting row is the unique RREF row at this pivot.
for (size_t i = pivot_columns.size(); i-- > 0;) {
    const size_t earlier = pivot_columns[i];
    if (!selected[earlier]) continue;
    auto &row = pivots[slots[earlier]];
    for (size_t j = i + 1; j < pivot_columns.size(); ++j) {
        charge();
        const size_t c = pivot_columns[j];
        if ((row.words[c >> 6] >> (c & 63)) & 1) xor_row(row, pivots[slots[c]], c >> 6, true);
    }
}
