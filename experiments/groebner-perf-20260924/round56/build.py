"""Ablate deferred tails against the cached and checked-chain F4 engines."""
import hashlib
import importlib.util
import json
import os
import platform
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
P=HERE.parent
VARIANTS={'prior':(False,0,False),'chain':(True,0,False),'top_new':(False,1,False),
          'top_all':(False,2,False),'chain_top_new':(True,1,False),'chain_top_all':(True,2,False),
          'filter':(False,0,True),'chain_filter':(True,0,True),
          'filter_top':(False,1,True),'chain_filter_top':(True,1,True)}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def change(s,a,b):
    assert s.count(a)==1,a
    return s.replace(a,b)
def source(chain,mode,select):
    spec=importlib.util.spec_from_file_location('chain_build56',P/'round55/build.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    s=module.cached_source()
    if chain:
        s=change(s,'    void install(Row row) {',(P/'round55/checked_chains.inc').read_text()+'\n    void install(Row row) {')
        s=change(s,'                Row row;\n                if (p.field)',
                 '                if (!p.field && chain_prune(p)) continue;\n'
                 '                if (p.field) ++chain_stats.field_pairs;\n'
                 '                Row row;\n                if (p.field)')
        s=change(s,'                if (!row.terms.empty()) batch.push_back(std::move(row));',
                 '                if (!p.field && row.terms.empty()) {\n'
                 '                    ++chain_stats.raw_zero_pairs; chain_remember(p.i,p.j);\n'
                 '                }\n                if (!row.terms.empty()) batch.push_back(std::move(row));')
        s='#include "../../../../round55/chain_stats.h"\n'+s
    header='struct TopStats { uint64_t calls=0,reductions=0,irreducible_heads=0,deferred_terms=0,zero_rows=0,output_pivots=0,skipped_reducer_pivots=0; };\nstatic thread_local TopStats top_stats{};\n'
    s=change(s,'class Engine {',header+'class Engine {')
    s=change(s,'    void install(Row row) {',(HERE/'top_normal.inc').read_text()+'\n    void install(Row row) {')
    if mode:
        s=change(s,'Row candidate=normal(std::move(row),basis);','Row candidate=top_normal(std::move(row));')
    if mode==2:
        s=change(s,'Row row=normal({input[i],emit(0,i)},basis);','Row row=top_normal({input[i],emit(0,i)});')
    if select:
        s=change(s,'    std::vector<Row> matrix(std::vector<Row> rows) {',
                 '    std::vector<Row> matrix(std::vector<Row> rows) {\n'
                 '        std::set<Mask> reducer_heads;')
        s=change(s,'                Row shifted=multiply(basis[i],monomial&~leads[i]);',
                 '                Row shifted=multiply(basis[i],monomial&~leads[i]);\n'
                 '                charge(); reducer_heads.insert(monomial);')
        s=change(s,'        for (auto it:order) out.push_back(std::move(it->second));',
                 '        // Every retained reducer has this pivot and lower terms.\n'
                 '        // Echelon rows at those pivots are redundant modulo the\n'
                 '        // old basis and the output rows at the other pivots.\n'
                 '        for (auto it:order) {\n'
                 '            charge(); ++top_stats.output_pivots;\n'
                 '            if (reducer_heads.count(it->first)) {\n'
                 '                ++top_stats.skipped_reducer_pivots; continue;\n'
                 '            }\n'
                 '            out.push_back(std::move(it->second));\n'
                 '        }')
    return s
def main():
    out=HERE/'build';out.mkdir(exist_ok=True)
    suffix='.dylib' if sys.platform=='darwin' else '.so'
    shared=['-dynamiclib'] if sys.platform=='darwin' else ['-shared','-fPIC']
    compiler=os.environ.get('CXX','clang++');commands=[]
    for variant,(chain,mode,select) in VARIANTS.items():
        directory=out/variant/'build';directory.mkdir(parents=True,exist_ok=True)
        engine=directory/'engine.inc';engine.write_text(source(chain,mode,select))
        adapter=(P/'round11/packed_producer.cpp').read_text()
        adapter=change(adapter,'#include "build/native_engine.inc"','#include "engine.inc"')
        adapter=change(adapter,'auto start=Clock::now();failure.clear();',
                       'auto start=Clock::now();failure.clear();top_stats={};'+('chain_stats={};chain_stats.mode=1;' if chain else ''))
        adapter+='\nextern "C" uint64_t producer_top_stats_size(){return sizeof(TopStats);}\nextern "C" const TopStats* producer_top_stats(){return &top_stats;}\n'
        if chain:
            adapter+='\nextern "C" uint64_t producer_chain_stats_size(){return sizeof(ChainStats);}\nextern "C" const ChainStats* producer_chain_stats(){return &chain_stats;}\n'
        path=directory/'adapter.cpp';path.write_text(adapter)
        for tag,flags in (('', ['-O3']),('-ubsan',['-O1','-g','-fsanitize=undefined','-fsanitize-undefined-trap-on-error','-fno-sanitize-recover=all'])):
            cmd=[compiler,'-std=c++17','-Wall','-Wextra','-Werror',*flags,*shared,'-I',str(P/'round11'),'-DPERSISTENT_ORDER=1','-DPIVOT_KEYS=1','-DINDEXED_REDUCERS=0',str(path),'-o',str(directory/('packed_producer'+tag+suffix))]
            subprocess.run(cmd,check=True);commands.append(cmd)
        print('BUILT',variant,flush=True)
    for tag,flags in (('', ['-O3']),('-ubsan',['-O1','-g','-fsanitize=undefined','-fsanitize-undefined-trap-on-error','-fno-sanitize-recover=all'])):
        binary=out/('native_checker'+tag+suffix)
        cmd=[compiler,'-std=c++17','-Wall','-Wextra','-Werror',*flags,*shared,str(P/'round11/native_checker.cpp'),'-o',str(binary)]
        subprocess.run(cmd,check=True);commands.append(cmd)
        for variant in VARIANTS:
            link=out/variant/'build'/binary.name
            if not link.exists(): link.symlink_to('../../'+binary.name)
    sources=[*HERE.glob('*.py'),*HERE.glob('*.inc'),P/'round55/build.py',P/'round55/checked_chains.inc',P/'round55/chain_stats.h',P/'round12/native_engine.cpp',P/'round13/cache_transform.py',P/'round13/normal_frontier.inc',*[P/'round11'/name for name in ('proof_abi.h','packed_producer.cpp','native_checker.cpp','packed_proof.py')]]
    receipt={'commands':commands,'sources':{str(p.relative_to(P)):sha(p) for p in sources},'binaries':{str(p.relative_to(out)):sha(p) for p in out.rglob('*'+suffix)},'generated':{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.suffix in ('.cpp','.inc')},'compiler':subprocess.check_output([compiler,'--version'],text=True),'platform':platform.platform(),'architecture':platform.machine()}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__': main()
