"""Try parity rewriting on the raw graph before ordinary reachability pruning."""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('block_generator_for112', HERE.parent/'round108/generate.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)


def source():
    text = previous.block_source()

    def change(old, new):
        nonlocal text
        assert text.count(old) == 1, old[:100]
        text = text.replace(old, new)

    change('struct BlockStats {', '''struct EarlyStats {
    uint64_t mode, attempted, active_nodes, bound_checks, bound_selected, bound_fallback;
    uint64_t prune_visits;
};
struct BlockStats {''')
    change('    uint64_t max_table_bytes;', '''    uint64_t max_table_bytes;
    EarlyStats local_early{};
    EarlyStats &early;''')
    change('BlockStats *b = nullptr, uint64_t table_bytes = 0)',
           'BlockStats *b = nullptr, uint64_t table_bytes = 0, EarlyStats *e = nullptr)')
    change('block(b ? *b : local_block), max_table_bytes(table_bytes)',
           'block(b ? *b : local_block), max_table_bytes(table_bytes), early(e ? *e : local_early)')
    change('            if (!mask) continue;\n            const auto &node = old[i];',
           '''            if (!mask) continue;
            // Each nonzero output-owner mask certifies ordinary reachability.
            // Monomial-input ancestors need not be counted: this is a lower bound.
            if (early.attempted) ++early.active_nodes;
            const auto &node = old[i];''')
    change('    result.graph.swap(compact);', '''    if (early.attempted) {
        pay();
        ++early.bound_checks;
        if (compact.size() >= early.active_nodes) {
            early.bound_fallback = 1;
            parity.fallback_size = 1;
            return;
        }
        early.bound_selected = 1;
    }
    result.graph.swap(compact);''')
    begin = text.index('        std::vector<uint8_t> needed(graph.size(), 0);')
    end = text.index('        stats.output_nodes = result->graph.size();', begin)
    pruning = text[begin:end].replace('result->', 'result.')
    pruning = pruning.replace('            charge();', '            charge();\n            ++early.prune_visits;')
    old = text[begin:text.index('        result->view =', end)]
    change(old, '''        if (early.mode && parity.mode) {
            early.attempted = 1;
            result->graph.swap(graph);
            rewrite_witness(*result, in.equations);
            if (!parity.selected) {
                // A rejected rewrite never changes graph or output storage.
                result->graph.swap(graph);
                prune_witness(*result);
            }
        } else {
            prune_witness(*result);
            stats.output_nodes = result->graph.size();
            rewrite_witness(*result, in.equations);
        }
        stats.output_nodes = result->graph.size();
''')
    change('void rewrite_witness(', 'void prune_witness(Result &result)\n{\n'+pruning+'}\n\nvoid rewrite_witness(')
    begin = text.index('void *macaulay_apply_block(')
    end = text.index('uint64_t macaulay_block_stats_size()', begin)
    wrapper = text[begin:end].replace('macaulay_apply_block(', 'macaulay_apply_early(', 1)
    wrapper = wrapper.replace('BlockStats *block)', 'BlockStats *block, uint32_t early_mode, EarlyStats *early)', 1)
    wrapper = wrapper.replace('    failure.clear();', '''    failure.clear();
    if (!early) { failure = "null early stats"; return nullptr; }
    *early = {}; early->mode = early_mode;''', 1)
    wrapper = wrapper.replace('if ((bits != 0', 'if (early_mode > 1 || (bits != 0', 1)
    wrapper = wrapper.replace('*stats, parity, bytes, block, table_bytes);', '*stats, parity, bytes, block, table_bytes, early);', 1)
    text = text[:end]+wrapper+'uint64_t macaulay_early_stats_size() { return sizeof(EarlyStats); }\n'+text[end:]
    return text


if __name__ == '__main__':
    print(source())
