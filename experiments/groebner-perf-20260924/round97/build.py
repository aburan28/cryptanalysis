"""Fresh baseline, fresh-vector control, bounded scratch, and tiny-cap builds."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
HERE=Path(__file__).resolve().parent
P=HERE.parent
spec=importlib.util.spec_from_file_location('baseline95_for97',P/'round95/build.py')
baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
baseline.HERE=HERE;baseline.native.HERE=HERE
original_sources=baseline.source_paths
CAPS={'fresh':0,'scratch':32768,'tiny':4}

def source_paths():
    paths=original_sources()+[P/'round95'/name for name in ('build.py','generate.py','query.py','common.py','audit.py')]
    paths+=[HERE/'normal_scratch.h',HERE/'normal_scratch.inc']
    return list(dict.fromkeys(paths))

baseline.native.source_paths=source_paths

def build():
    baseline.build()
    from generate import producer_source,adapter_source
    out=HERE/'build';compiler=os.environ.get('CXX','clang++')
    suffix='.dylib' if sys.platform=='darwin' else '.so';shared=['-dynamiclib'] if sys.platform=='darwin' else ['-shared','-fPIC']
    receipt=json.loads((out/'receipt.json').read_text());receipt.update(schema='normal-scratch-build/1',executables={})
    modes=(('', ['-O3']),('-ubsan',['-O1','-g','-fsanitize=undefined','-fsanitize-undefined-trap-on-error','-fno-sanitize-recover=all']))
    for arm,cap in CAPS.items():
        engine=out/f'f4_normal_{arm}.inc';engine.write_text(producer_source(cap))
        adapter=out/f'normal_{arm}.cpp';adapter.write_text(adapter_source(engine.name))
        for path in (engine,adapter):receipt['generated'][path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
        for tag,flags in modes:
            binary=out/(f'normal_{arm}'+tag+suffix)
            cmd=[compiler,'-std=c++17','-Wall','-Wextra','-Werror',*flags,*shared,'-I',str(P/'round11'),'-I',str(P/'round55'),'-I',str(HERE),'-DPERSISTENT_ORDER=1','-DPIVOT_KEYS=1','-DINDEXED_REDUCERS=0',str(adapter),'-o',str(binary)]
            subprocess.run(cmd,check=True);receipt['commands'].append(cmd);receipt['binaries'][binary.name]=hashlib.sha256(binary.read_bytes()).hexdigest()
    for tag,flags in modes:
        executable=out/('normal_controls'+tag+'.exe')
        cmd=[compiler,'-std=c++17','-Wall','-Wextra','-Werror',*flags,'-pthread','-I',str(P/'round55'),'-I',str(HERE),'-I',str(out),'-DPERSISTENT_ORDER=1','-DPIVOT_KEYS=1','-DINDEXED_REDUCERS=0',str(HERE/'normal_controls.cpp'),'-o',str(executable)]
        subprocess.run(cmd,check=True);receipt['commands'].append(cmd);receipt['executables'][executable.name]=hashlib.sha256(executable.read_bytes()).hexdigest()
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('NORMAL_SCRATCH_BUILD_PASS',len(receipt['binaries']),flush=True)

if __name__=='__main__':build()
