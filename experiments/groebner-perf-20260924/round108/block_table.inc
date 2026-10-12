struct PivotTable {
    Masks words;
    std::array<uint32_t, 16> proofs{};
    std::array<uint8_t, 16> lookup{};
};
std::vector<PivotTable> tables;
std::vector<uint32_t> table_index;
std::vector<uint8_t> table_count;
uint64_t table_bytes_used = 0;
void table_pay(uint64_t amount = 1)
{
    charge(amount);
    block.work += amount;
}
void prepare_tables()
{
    if (!block.bits) return;
    table_pay();
    const size_t groups = (layout.columns.size() + 3) / 4;
    block.groups = groups;
    const uint64_t bytes = 5 * uint64_t(groups);
    if (bytes > max_table_bytes) {
        block.fallback_index_bytes = 1;
        return;
    }
    table_pay(2 * groups);
    table_index.assign(groups, UINT32_MAX);
    table_count.assign(groups, 0);
    table_bytes_used = bytes;
    block.index_bytes = block.peak_payload_bytes = bytes;
}
void note_pivot(size_t column)
{
    if (table_index.empty()) return;
    const size_t group = column / 4;
    if (table_count[group] == 255) return;
    table_pay();
    ++table_count[group];
    ++block.pivot_updates;
}
bool table_reduce(Row &row, size_t column, const std::vector<Row> &pivots,
                  const std::vector<uint32_t> &slots)
{
    if (table_index.empty()) return false;
    table_pay();
    ++block.lookups;
    const size_t group = column / 4, start = group * 4;
    if (table_count[group] == 255) {
        ++block.fallback_table_bytes;
        return false;
    }
    if (table_count[group] != 4 || start + 4 > slots.size()) {
        ++block.incomplete;
        return false;
    }
    const size_t first = start >> 6, width = row.words.size() - first;
    if (table_index[group] == UINT32_MAX) {
        table_pay();
        // Coefficient payload plus sixteen proof IDs and lookup bytes.
        // Vector headers, capacity slack and allocator metadata are separate.
        const uint64_t bytes = 15 * uint64_t(width) * 8 + 80;
        if (bytes > max_table_bytes - table_bytes_used) {
            table_count[group] = 255;
            ++block.fallback_table_bytes;
            return false;
        }
        table_pay(15 * width + 32);
        PivotTable table;
        table.words.assign(15 * width, 0);
        table_bytes_used += bytes;
        block.table_bytes += bytes;
        block.peak_payload_bytes = table_bytes_used;
        for (uint32_t combination = 1; combination < 16; ++combination) {
            table_pay();
            const uint32_t bit = __builtin_ctz(combination);
            const uint32_t previous = combination & (combination - 1);
            const auto &pivot = pivots[slots[start + bit]];
            const size_t destination = (combination - 1) * width;
            table_pay(width);
            if (!previous) {
                std::copy(pivot.words.begin() + first, pivot.words.end(),
                          table.words.begin() + destination);
                table.proofs[combination] = pivot.proof;
                block.copied_words += width;
            } else {
                const uint32_t proof = emit(2, table.proofs[previous], pivot.proof);
                for (size_t w = 0; w < width; ++w)
                    table.words[destination + w] =
                        table.words[(previous - 1) * width + w] ^ pivot.words[first + w];
                table.proofs[combination] = proof;
                block.table_word_xors += width;
                stats.word_xors += width;
            }
            table_pay();
            const uint32_t signature = (table.words[destination] >> (start & 63)) & 15;
            if (!signature || table.lookup[signature])
                throw std::runtime_error("noninvertible pivot table signature");
            table.lookup[signature] = uint8_t(combination);
            ++block.combinations;
        }
        table_index[group] = uint32_t(tables.size());
        tables.push_back(std::move(table));
        ++block.builds;
    }
    const auto &table = tables[table_index[group]];
    table_pay();
    const uint32_t signature = (row.words[first] >> (start & 63)) & 15;
    const uint32_t combination = table.lookup[signature];
    if (!combination) throw std::runtime_error("missing pivot table signature");
    table_pay(width);
    const uint32_t proof = emit(2, row.proof, table.proofs[combination]);
    for (size_t w = 0; w < width; ++w)
        row.words[first + w] ^= table.words[(combination - 1) * width + w];
    row.proof = proof;
    ++stats.forward_xors;
    stats.word_xors += width;
    ++block.applications;
    block.applied_word_xors += width;
    block.scalar_pivots_replaced += __builtin_popcount(combination);
    return true;
}
void release_tables()
{
    std::vector<PivotTable>().swap(tables);
    std::vector<uint32_t>().swap(table_index);
    std::vector<uint8_t>().swap(table_count);
    table_bytes_used = 0;
}
