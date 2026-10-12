"""Add explicit dense-buffer transfer to the hash-independent certificate checker."""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE.parent
spec = importlib.util.spec_from_file_location('generator102_for104', P/'round102/generate.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
source, sparse_source, dense_source = previous.source, previous.sparse_source, previous.dense_source


def reuse_source():
    text = dense_source()

    def change(old, new):
        nonlocal text
        assert text.count(old) == 1, old[:100]
        text = text.replace(old, new)

    change('struct DenseStats {', '''struct ReuseStats {
    uint64_t enabled, checks, transfers, left_transfers, right_transfers;
    uint64_t payload_allocations, payload_releases;
};
struct DenseStats {''')
    change('    DenseStats& dense;', '    DenseStats& dense;\n    ReuseStats& reuse;\n'+(HERE/'reuse_values.inc').read_text())
    change('uint32_t mode,uint64_t bytes,DenseStats& d,CheckStats& s)',
           'uint32_t mode,uint64_t bytes,DenseStats& d,ReuseStats& r,CheckStats& s)')
    change('dense_mode(mode),max_dense_bytes(bytes),dense(d),stats(s){}',
           'dense_mode(mode),max_dense_bytes(bytes),dense(d),reuse(r),stats(s){}')
    change('    ++dense.created_values;\n    return value;',
           '    ++dense.created_values;\n    ++reuse.payload_allocations;\n    return value;')
    change('dense.live_bytes-=values[i].words.size()*sizeof(uint64_t);',
           'if(!values[i].words.empty())++reuse.payload_releases;\n            dense.live_bytes-=values[i].words.size()*sizeof(uint64_t);')
    change('value=dense_add(values[node.a],values[node.b]);', '''const bool eligible=reuse.enabled && policy && node.a!=node.b;
                reuse.checks+=eligible;
                const bool take_left=eligible && uses[node.a]==1;
                const bool take_right=eligible && !take_left && uses[node.b]==1;
                value=dense_add_reuse(values[node.a],values[node.b],take_left,take_right);''')
    change('        dense.live_bytes=0;', '''        // Remaining owned buffers (keep-policy only) die at this scope exit.
        reuse.payload_releases=reuse.payload_allocations;
        dense.live_bytes=0;''')
    change('uint64_t dense_stats_size(){return sizeof(DenseStats);}',
           'uint64_t dense_stats_size(){return sizeof(DenseStats);}\nuint64_t reuse_stats_size(){return sizeof(ReuseStats);}')
    change('int check_packed_dense(', 'int check_packed_reuse(')
    change('CheckStats* stats,LiveStats* live,DenseStats* dense)',
           'uint32_t reuse_mode,CheckStats* stats,LiveStats* live,DenseStats* dense,ReuseStats* reuse)')
    change('if(!stats||!live||!dense)', 'if(!stats||!live||!dense||!reuse)')
    change('*dense=DenseStats{};', '*dense=DenseStats{};*reuse=ReuseStats{};reuse->enabled=reuse_mode;')
    change('if(mode>1||policy>2||schedule>1', 'if(reuse_mode>1||mode>1||policy>2||schedule>1')
    change('policy,*live,mode,max_dense_bytes,*dense,*stats);',
           'policy,*live,mode,max_dense_bytes,*dense,*reuse,*stats);')
    return text


if __name__ == '__main__':
    print(reuse_source())
