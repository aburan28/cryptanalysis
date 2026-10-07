"""Bounded parity compression over the unchanged minimal-row matrix producer."""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE.parent
spec = importlib.util.spec_from_file_location('generator106_for107', P/'round106/generate.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
source, sparse_source, dense_source, reuse_source, normal_source, minimal_source = (
    previous.source, previous.sparse_source, previous.dense_source,
    previous.reuse_source, previous.normal_source, previous.minimal_source)


def parity_source():
    text = minimal_source()

    def change(old, new):
        nonlocal text
        assert text.count(old) == 1, old[:100]
        text = text.replace(old, new)

    change('struct MatrixStats {', '''struct ParityStats {
    uint64_t mode, selected, fallback_outputs, fallback_bytes, fallback_size;
    uint64_t fallback_shape, input_nodes, outputs, peak_metadata_bytes;
    uint64_t visited_nodes, parity_edges, leaves, incidences, emitted_nodes, work;
    double total_seconds;
};
struct MatrixStats {''')
    change('    MatrixStats &stats;', '''    MatrixStats &stats;
    ParityStats local_parity{};
    ParityStats &parity;
    uint64_t max_parity_bytes;''')
    change('  public:\n    Engine(', (HERE/'parity_witness.inc').read_text()+'\n  public:\n    Engine(')
    change('uint32_t rows, MatrixStats &s)\n        : layout(l), max_work(w), max_nodes(nodes), max_rows(rows), stats(s)',
           '''uint32_t rows, MatrixStats &s,
           ParityStats *p = nullptr, uint64_t bytes = 0)
        : layout(l), max_work(w), max_nodes(nodes), max_rows(rows), stats(s),
          parity(p ? *p : local_parity), max_parity_bytes(bytes)''')
    change('        stats.output_nodes = result->graph.size();',
           '''        stats.output_nodes = result->graph.size();
        rewrite_witness(*result, in.equations);
        stats.output_nodes = result->graph.size();''')
    begin = text.index('void *macaulay_apply(')
    end = text.index('const ProofView *macaulay_view(', begin)
    wrapper = text[begin:end].replace('void *macaulay_apply(', 'void *macaulay_apply_parity(', 1)
    wrapper = wrapper.replace('MatrixStats *stats)',
        'MatrixStats *stats, uint32_t mode, uint64_t bytes, ParityStats *parity)', 1)
    wrapper = wrapper.replace('    failure.clear();', '''    failure.clear();
    if (!parity) { failure = "null parity stats"; return nullptr; }
    *parity = {}; parity->mode = mode;''', 1)
    wrapper = wrapper.replace('if (!layout || !in ||', 'if (mode > 1 || !layout || !in ||', 1)
    wrapper = wrapper.replace('work, nodes, rows, *stats);',
                              'work, nodes, rows, *stats, parity, bytes);', 1)
    text = text[:end]+wrapper+'uint64_t macaulay_parity_stats_size() { return sizeof(ParityStats); }\n'+text[end:]
    return text


if __name__ == '__main__':
    print(parity_source())
