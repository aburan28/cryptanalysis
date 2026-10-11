    // Symbolic closure has fixed this matrix's monomial support. Column zero
    // is its greatest monomial. No coefficients, pivots or proof nodes survive
    // this call. The sparse fallback bounds the additional column-map memory.
    std::vector<Row> column_matrix(std::vector<Row> rows,
                                   const std::set<Mask>& support,
                                   const std::set<Mask>& reducer_heads) {
        std::vector<Mask> columns(support.begin(), support.end());
        std::sort(columns.begin(), columns.end(),
                  [](Mask a, Mask b) { return less_monomial(b, a); });
        std::unordered_map<Mask, Mask> rank;
        rank.reserve(columns.size());
        for (size_t i = 0; i < columns.size(); ++i) rank.emplace(columns[i], i);
        ++column_stats.indexed_matrices;
        column_stats.columns += columns.size();
        column_stats.peak_columns = std::max<uint64_t>(column_stats.peak_columns, columns.size());
        for (auto& row : rows) {
            column_stats.converted_terms += row.terms.size();
            for (auto& term : row.terms) term = rank.at(term);
            std::sort(row.terms.begin(), row.terms.end());
        }
        std::vector<size_t> pivot_slot(columns.size(), SIZE_MAX);
        std::vector<Row> pivots;
        pivots.reserve(rows.size());
        for (auto& initial : rows) {
            Row row = std::move(initial);
            while (!row.terms.empty()) {
                charge(row.terms.size());
                const Mask column = row.terms.front();
                const size_t slot = pivot_slot[column];
                if (slot == SIZE_MAX) {
                    pivot_slot[column] = pivots.size();
                    pivots.push_back(std::move(row));
                    break;
                }
                // add() emits the same XOR witness and charges the same term
                // counts: a bijection of columns commutes with symmetric XOR.
                row = add(row, pivots[slot]);
            }
        }
        std::vector<Row> out;
        out.reserve(pivots.size());
        for (size_t column = columns.size(); column-- > 0;) {
            const size_t slot = pivot_slot[column];
            if (slot == SIZE_MAX) continue;
            charge();
            ++top_stats.output_pivots;
            if (reducer_heads.count(columns[column])) {
                ++top_stats.skipped_reducer_pivots;
                continue;
            }
            Row row = std::move(pivots[slot]);
            for (auto& term : row.terms) term = columns[term];
            std::sort(row.terms.begin(), row.terms.end());
            out.push_back(std::move(row));
        }
        return out;
    }
