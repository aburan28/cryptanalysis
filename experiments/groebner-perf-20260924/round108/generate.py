"""Four-column combination tables with original-input derivation witnesses."""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE.parent
spec = importlib.util.spec_from_file_location('generator107_for108', P/'round107/generate.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
source, sparse_source, dense_source, reuse_source, normal_source, minimal_source, parity_source = (
    previous.source, previous.sparse_source, previous.dense_source,
    previous.reuse_source, previous.normal_source, previous.minimal_source, previous.parity_source)


def block_source():
    text = parity_source()

    def change(old, new):
        nonlocal text
        assert text.count(old) == 1, old[:100]
        text = text.replace(old, new)

    change('#include <algorithm>', '#include <algorithm>\n#include <array>')
    change('struct ParityStats {', '''struct BlockStats {
    uint64_t bits, groups, fallback_index_bytes, index_bytes, table_bytes, peak_payload_bytes;
    uint64_t pivot_updates, lookups, incomplete, fallback_table_bytes, builds, combinations;
    uint64_t copied_words, table_word_xors, applications, applied_word_xors;
    uint64_t scalar_pivots_replaced, work;
};
struct ParityStats {''')
    change('    uint64_t max_parity_bytes;', '''    uint64_t max_parity_bytes;
    BlockStats local_block{};
    BlockStats &block;
    uint64_t max_table_bytes;''')
    change('void rewrite_witness(', (HERE/'block_table.inc').read_text()+'\nvoid rewrite_witness(')
    change('ParityStats *p = nullptr, uint64_t bytes = 0)',
           'ParityStats *p = nullptr, uint64_t bytes = 0, BlockStats *b = nullptr, uint64_t table_bytes = 0)')
    change('parity(p ? *p : local_parity), max_parity_bytes(bytes)',
           'parity(p ? *p : local_parity), max_parity_bytes(bytes),\n          block(b ? *b : local_block), max_table_bytes(table_bytes)')
    change('        std::vector<Row> pivots;', '        prepare_tables();\n        std::vector<Row> pivots;')
    change('                        ++stats.pivots;', '                        ++stats.pivots;\n                        note_pivot(column);')
    change('                    xor_row(row, pivots[slots[column]], first, false);',
           '''                    if (!table_reduce(row, column, pivots, slots))
                        xor_row(row, pivots[slots[column]], first, false);''')
    change('        // Back substitution uses the freshly selected pivot columns only.',
           '        release_tables();\n        // Back substitution uses the freshly selected pivot columns only.')
    begin = text.index('void *macaulay_apply_parity(')
    end = text.index('uint64_t macaulay_parity_stats_size()', begin)
    wrapper = text[begin:end].replace('void *macaulay_apply_parity(', 'void *macaulay_apply_block(', 1)
    wrapper = wrapper.replace('ParityStats *parity)',
        'ParityStats *parity, uint32_t bits, uint64_t table_bytes, BlockStats *block)', 1)
    wrapper = wrapper.replace('    failure.clear();', '''    failure.clear();
    if (!block) { failure = "null block stats"; return nullptr; }
    *block = {}; block->bits = bits;''', 1)
    wrapper = wrapper.replace('if (mode > 1 ||', 'if ((bits != 0 && bits != 4) || mode > 1 ||', 1)
    wrapper = wrapper.replace('*stats, parity, bytes);', '*stats, parity, bytes, block, table_bytes);', 1)
    text = text[:end]+wrapper+'uint64_t macaulay_block_stats_size() { return sizeof(BlockStats); }\n'+text[end:]
    return text


if __name__ == '__main__':
    print(block_source())
