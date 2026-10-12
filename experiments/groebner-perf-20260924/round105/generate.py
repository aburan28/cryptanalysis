"""Bounded quotient-map membership; forward proofs and completion stay unchanged."""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE.parent
spec = importlib.util.spec_from_file_location('generator104_for105', P/'round104/generate.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
source, sparse_source, dense_source, reuse_source = (
    previous.source, previous.sparse_source, previous.dense_source, previous.reuse_source)


def normal_source():
    text = reuse_source()

    def change(old, new):
        nonlocal text
        assert text.count(old) == 1, old[:100]
        text = text.replace(old, new)

    change('struct ReuseStats {', '''struct NormalStats {
    uint64_t mode, selected, fallback_large_ring, fallback_sparse;
    uint64_t fallback_dimension, fallback_bytes, input_terms, universe;
    uint64_t dimension, peak_bytes, planning_work, table_products;
    uint64_t table_terms, input_xors, work;
};
struct ReuseStats {''')
    change('    ReuseStats& reuse;', '''    ReuseStats& reuse;
    NormalStats& normal;
    uint64_t max_normal_bytes;
''' + (HERE/'normal_form.inc').read_text())
    change('ReuseStats& r,CheckStats& s)', 'ReuseStats& r,NormalStats& q,uint64_t map_bytes,CheckStats& s)')
    change('dense(d),reuse(r),stats(s){}',
           'dense(d),reuse(r),normal(q),max_normal_bytes(map_bytes),stats(s){}')
    change('        // Reverse inclusion: every original generator must lie in <basis>.',
           '''        if(quotient_membership(originals,basis,leads))return;
        // Reverse inclusion: every original generator must lie in <basis>.''')
    change('int check_packed_reuse(', 'int check_packed_normal(')
    change('uint64_t reuse_stats_size(){return sizeof(ReuseStats);}',
           'uint64_t reuse_stats_size(){return sizeof(ReuseStats);}\nuint64_t normal_stats_size(){return sizeof(NormalStats);}')
    change('uint32_t reuse_mode,CheckStats* stats',
           'uint32_t reuse_mode,uint32_t normal_mode,uint64_t normal_bytes,NormalStats* normal,CheckStats* stats')
    change('if(!stats||!live||!dense||!reuse)', 'if(!normal||!stats||!live||!dense||!reuse)')
    change('*reuse=ReuseStats{};reuse->enabled=reuse_mode;',
           '*reuse=ReuseStats{};reuse->enabled=reuse_mode;*normal=NormalStats{};normal->mode=normal_mode;')
    change('if(reuse_mode>1||mode>1', 'if(normal_mode>2||reuse_mode>1||mode>1')
    change('max_dense_bytes,*dense,*reuse,*stats);',
           'max_dense_bytes,*dense,*reuse,*normal,normal_bytes,*stats);')
    return text


if __name__ == '__main__':
    print(normal_source())
