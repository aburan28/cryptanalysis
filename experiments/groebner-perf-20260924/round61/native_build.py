"""Build bounded scratch XOR variants with the unchanged independent checker."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

HERE=Path(__file__).resolve().parent
P=HERE.parent
VARIANTS={'baseline':0,'scratch':32768,'tiny':4}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def change(s,a,b):
    assert s.count(a)==1,a
    return s.replace(a,b)
def source(cap):
    spec=importlib.util.spec_from_file_location('columns_build61',P/'round58/build.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    s=module.source(262144)
    s=change(s,'"../../../../round55/chain_stats.h"','"../../../../../round55/chain_stats.h"')
    header='struct ScratchStats { uint64_t xors=0,fresh_vectors=0,growths=0,reused=0,trimmed_pivots=0,trimmed_capacity_words=0,peak_capacity_words=0; };\nstatic thread_local ScratchStats scratch_stats{};\n'
    s=change(s,'class Engine {',header+'class Engine {')
    anchor='    std::vector<Row> column_matrix('
    s=change(s,anchor,(HERE/'scratch_add.inc').read_text()+'\n'+anchor)
    s=change(s,'        for (auto& initial : rows) {','        Poly scratch;\n        for (auto& initial : rows) {')
    s=change(s,'            Row row = std::move(initial);','            Row row = std::move(initial);\n            size_t last_xor_capacity = row.terms.capacity();')
    s=change(s,'                    pivot_slot[column] = pivots.size();','                    trim_pivot(row,last_xor_capacity);\n                    pivot_slot[column] = pivots.size();')
    s=change(s,'                row = add(row, pivots[slot]);',
             f'                last_xor_capacity = row.terms.size()+pivots[slot].terms.size();\n                scratch_add(row,pivots[slot],scratch,{cap});')
    return s
def main():
    out=HERE/'build/engines';out.mkdir(exist_ok=True)
    suffix='.dylib' if sys.platform=='darwin' else '.so'
    shared=['-dynamiclib'] if sys.platform=='darwin' else ['-shared','-fPIC']
    compiler=os.environ.get('CXX','clang++');commands=[]
    modes=(('', ['-O3']),('-ubsan',['-O1','-g','-fsanitize=undefined',
            '-fsanitize-undefined-trap-on-error','-fno-sanitize-recover=all']))
    for variant,cap in VARIANTS.items():
        directory=out/variant/'build';directory.mkdir(parents=True,exist_ok=True)
        (directory/'engine.inc').write_text(source(cap))
        adapter=(P/'round11/packed_producer.cpp').read_text()
        adapter=change(adapter,'#include "build/native_engine.inc"','#include "engine.inc"')
        adapter=change(adapter,'auto start=Clock::now();failure.clear();',
                       'auto start=Clock::now();failure.clear();top_stats={};column_stats={};scratch_stats={};chain_stats={};chain_stats.mode=1;')
        for label,kind in (('top','Top'),('column','Column'),('chain','Chain'),('scratch','Scratch')):
            adapter+=f'\nextern "C" uint64_t producer_{label}_stats_size(){{return sizeof({kind}Stats);}}\n'
            adapter+=f'extern "C" const {kind}Stats* producer_{label}_stats(){{return &{label}_stats;}}\n'
        path=directory/'adapter.cpp';path.write_text(adapter)
        for tag,flags in modes:
            command=[compiler,'-std=c++17','-Wall','-Wextra','-Werror',*flags,*shared,'-I',str(P/'round11'),
                     '-DPERSISTENT_ORDER=1','-DPIVOT_KEYS=1','-DINDEXED_REDUCERS=0',str(path),
                     '-o',str(directory/('packed_producer'+tag+suffix))]
            subprocess.run(command,check=True);commands.append(command)
        print('BUILT',variant,flush=True)
    for tag,flags in modes:
        binary=out/('native_checker'+tag+suffix)
        command=[compiler,'-std=c++17','-Wall','-Wextra','-Werror',*flags,*shared,
                 str(P/'round11/native_checker.cpp'),'-o',str(binary)]
        subprocess.run(command,check=True);commands.append(command)
        for variant in VARIANTS:
            link=out/variant/'build'/binary.name
            if not link.exists():link.symlink_to('../../'+binary.name)
    sources=[*HERE.glob('*.py'),*HERE.glob('*.inc'),P/'round58/build.py',P/'round58/column_matrix.inc',P/'round56/build.py',P/'round56/top_normal.inc',
             P/'round55/build.py',P/'round55/checked_chains.inc',P/'round55/chain_stats.h',
             P/'round12/native_engine.cpp',P/'round13/cache_transform.py',P/'round13/normal_frontier.inc',
             *[P/'round11'/name for name in ('proof_abi.h','packed_producer.cpp','native_checker.cpp','packed_proof.py')]]
    receipt={'commands':commands,'sources':{str(p.relative_to(P)):sha(p) for p in sources},
             'binaries':{str(p.relative_to(out)):sha(p) for p in out.rglob('*'+suffix)},
             'generated':{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.suffix in ('.cpp','.inc')},
             'compiler':subprocess.check_output([compiler,'--version'],text=True),
             'platform':platform.platform(),'architecture':platform.machine()}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()
