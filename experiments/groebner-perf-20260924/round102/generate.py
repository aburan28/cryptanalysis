"""Add an opt-in bounded proof-value representation to the independent checker."""
import hashlib
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE.parent


def load(number):
    spec = importlib.util.spec_from_file_location(f'generator{number}_for102', P/f'round{number}/generate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source():
    return load(94).source()


def sparse_source():
    return load(101).sparse_source()


def dense_source():
    text = source()

    def change(old, new):
        nonlocal text
        assert text.count(old) == 1, old[:100]
        text = text.replace(old, new)

    inc = (HERE/'dense_values.inc').read_text()
    declaration, methods = inc.split('// BEGIN METHODS\n')
    methods = methods.split('// END METHODS')[0]
    stats = '''struct DenseStats {
    uint64_t selected, fallback_large_ring, words_per_value, word_work;
    uint64_t metadata_bytes, live_bytes, peak_bytes, created_values, released_values;
};
'''
    change('namespace {', stats + 'namespace {\n' + declaration)
    change('LiveStats& live;', '''LiveStats& live;
    uint32_t dense_mode;
    uint64_t max_dense_bytes;
    DenseStats& dense;
''' + methods)
    change('Checker(uint32_t n,uint64_t work,uint64_t terms,uint32_t p,LiveStats& l,CheckStats& s)\n        :variables(n),max_work(work),max_terms(terms),policy(p),live(l),stats(s){}',
        '''Checker(uint32_t n,uint64_t work,uint64_t terms,uint32_t p,LiveStats& l,
                uint32_t mode,uint64_t bytes,DenseStats& d,CheckStats& s)
        :variables(n),max_work(work),max_terms(terms),policy(p),live(l),
         dense_mode(mode),max_dense_bytes(bytes),dense(d),stats(s){}''')
    begin = text.index('        auto derivation = [&]() {')
    end = text.index('        auto membership = [&]() {', begin)
    original = text[begin:end]
    dense_code = original.replace('auto derivation =', 'auto dense_derivation =', 1)
    start = '''
        dense.selected=1;
        dense.words_per_value=((UINT64_C(1)<<variables)+63)/64;
        // Include reserved vector storage and last-use counters in the byte cap.
        // Allocator bookkeeping and the unchanged input/basis sets are separate.
        dense.metadata_bytes=proof.nodes*(sizeof(DenseValue)+(policy?sizeof(uint32_t):0));
        if(dense.metadata_bytes>max_dense_bytes)throw Exhausted("dense proof metadata budget");
        dense.live_bytes=dense.peak_bytes=dense.metadata_bytes;
        std::vector<DenseValue> values;
'''
    dense_code = dense_code.replace('auto dense_derivation = [&]() {', 'auto dense_derivation = [&]() {'+start, 1)
    replacements = {
        'Polynomial{}.swap(values[i]);': '''dense.live_bytes-=values[i].words.size()*sizeof(uint64_t);
            ++dense.released_values;
            DenseValue{}.swap(values[i]);''',
        'const ProofNode& node=proof.graph[i];Polynomial value;': 'const ProofNode& node=proof.graph[i];DenseValue value;',
        'value=originals[node.a];': 'value=dense_input(originals[node.a]);',
        'value=multiply(values[node.a],node.b);': 'value=dense_multiply(values[node.a],node.b);',
        'value=add(values[node.a],values[node.b]);': 'value=dense_add(values[node.a],values[node.b]);',
        'values[proof.outputs[i]]!=basis[i]': '!dense_equal(values[proof.outputs[i]],basis[i])',
    }
    for old, new in replacements.items():
        assert dense_code.count(old) == 1, old
        dense_code = dense_code.replace(old, new)
    dense_code=dense_code.rsplit('        };',1)[0]+'        dense.live_bytes=0;\n        };\n'
    # Do not duplicate or replace the existing sparse fallback's arithmetic.
    change(original, original+dense_code+'''        auto selected_derivation = [&]() {
            if(dense_mode && variables<=12) dense_derivation();
            else {
                dense.fallback_large_ring=(dense_mode && variables>12);
                derivation();
            }
        };
''')
    assert text.count('select_phase(1); derivation();') == 2
    text = text.replace('select_phase(1); derivation();', 'select_phase(1); selected_derivation();')
    change('int check_packed_live(', 'uint64_t dense_stats_size(){return sizeof(DenseStats);}\nint check_packed_dense(')
    change('CheckStats* stats,LiveStats* live)',
           'uint32_t mode,uint64_t max_dense_bytes,CheckStats* stats,LiveStats* live,DenseStats* dense)')
    change('if(!stats||!live)', 'if(!stats||!live||!dense)')
    change('*live=LiveStats{};', '*live=LiveStats{};*dense=DenseStats{};')
    change('if(policy>2||schedule>1', 'if(mode>1||policy>2||schedule>1')
    change('Checker checker(input->nvars,max_work,max_retained_terms,policy,*live,*stats);',
           'Checker checker(input->nvars,max_work,max_retained_terms,policy,*live,mode,max_dense_bytes,*dense,*stats);')
    return text


if __name__ == '__main__':
    print(dense_source())
