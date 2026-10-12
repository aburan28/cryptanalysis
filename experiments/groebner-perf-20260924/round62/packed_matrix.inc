struct BitRow {
    std::vector<uint64_t> words;
    size_t count;
    uint32_t proof;
};

// Rank zero denotes the greatest monomial. Numeric elimination follows
// exactly the sparse pivot order; each XOR emits the same proof node.
std::vector<Row> packed_column_matrix(std::vector<Row> rows, const std::vector<Mask> &columns,
                                      const std::set<Mask> &reducer_heads, size_t width)
{
    ++packed_stats.matrices;
    packed_stats.peak_width = std::max<uint64_t>(packed_stats.peak_width, width);
    std::vector<size_t> pivot_slot(columns.size(), SIZE_MAX);
    std::vector<BitRow> pivots;
    pivots.reserve(rows.size());
    for (auto &initial : rows) {
        if (initial.terms.empty()) continue;
        BitRow row{std::vector<uint64_t>(width, 0), initial.terms.size(), initial.proof};
        ++packed_stats.rows;
        packed_stats.input_terms += initial.terms.size();
        packed_stats.peak_payload_words =
            std::max<uint64_t>(packed_stats.peak_payload_words, (pivots.size() + 1) * width);
        for (Mask column : initial.terms) row.words[column >> 6] |= uint64_t(1) << (column & 63);
        Poly{}.swap(initial.terms);
        size_t first = 0;
        while (row.count) {
            charge(row.count);
            while (first < width && !row.words[first]) ++first;
            if (first == width) throw std::runtime_error("packed row cardinality mismatch");
            const size_t column = (first << 6) + __builtin_ctzll(row.words[first]);
            const size_t slot = pivot_slot[column];
            if (slot == SIZE_MAX) {
                pivot_slot[column] = pivots.size();
                pivots.push_back(std::move(row));
                break;
            }
            const BitRow &pivot = pivots[slot];
            charge(row.count + pivot.count);
            ++packed_stats.xors;
            packed_stats.word_xors += width - first;
            size_t count = 0;
            for (size_t word = first; word < width; ++word) {
                row.words[word] ^= pivot.words[word];
                count += __builtin_popcountll(row.words[word]);
            }
            // Earlier words are zero in both rows because their current
            // leading column is identical. Failed emission unwinds this
            // matrix and discards its numeric storage as in the sparse path.
            row.proof = emit(2, row.proof, pivot.proof);
            row.count = count;
        }
    }
    std::vector<Row> out;
    out.reserve(pivots.size());
    for (size_t column = columns.size(); column-- > 0;) {
        const size_t slot = pivot_slot[column];
        if (slot == SIZE_MAX) continue;
        charge();
        ++top_stats.output_pivots;
        BitRow &pivot = pivots[slot];
        if (reducer_heads.count(columns[column])) {
            ++top_stats.skipped_reducer_pivots;
            std::vector<uint64_t>{}.swap(pivot.words);
            continue;
        }
        Row row{{}, pivot.proof};
        row.terms.reserve(pivot.count);
        for (size_t word = column >> 6; word < width; ++word) {
            uint64_t bits = pivot.words[word];
            while (bits) {
                const size_t index = (word << 6) + __builtin_ctzll(bits);
                row.terms.push_back(columns[index]);
                bits &= bits - 1;
            }
        }
        packed_stats.output_terms += row.terms.size();
        std::vector<uint64_t>{}.swap(pivot.words);
        std::sort(row.terms.begin(), row.terms.end());
        out.push_back(std::move(row));
    }
    return out;
}
