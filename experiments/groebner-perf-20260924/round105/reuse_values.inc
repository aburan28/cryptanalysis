// Transfer only a distinct operand whose last use is this XOR node. The
// operand's term count survives until ordinary logical reclamation; its words
// belong to the result immediately. Output references are included in uses.
DenseValue dense_add_reuse(DenseValue &left, DenseValue &right, bool take_left, bool take_right)
{
    if (!take_left && !take_right) return dense_add(left, right);
    // Preserve the same conservative budget charges as the allocating arm,
    // including initialization work that a transferred buffer no longer needs.
    charge(left.size() + right.size());
    dense_charge(3 * dense.words_per_value);
    DenseValue value;
    DenseValue &donor = take_left ? left : right;
    const DenseValue &other = take_left ? right : left;
    value.words.swap(donor.words);
    ++dense.created_values;
    ++reuse.transfers;
    if (take_left)
        ++reuse.left_transfers;
    else
        ++reuse.right_transfers;
    for (size_t i = 0; i < value.words.size(); ++i) {
        value.words[i] ^= other.words[i];
        value.terms += __builtin_popcountll(value.words[i]);
    }
    return value;
}
