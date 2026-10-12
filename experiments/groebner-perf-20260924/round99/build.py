"""Unchanged producer, packed keys, bounded radix and tiny-cap fallback builds."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
HERE=Path(__file__).resolve().parent
P=HERE.parent
spec=importlib.util.spec_from_file_location('baseline95_for99',P/'round95/build.py')
baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
baseline.HERE=HERE;baseline.native.HERE=HERE
original_sources=baseline.source_paths
POLICIES={'keys':None,'radix':32768,'tiny':256}

def source_paths():
    paths=original_sources()+[P/'round95'/name for name in ('build.py','generate.py','query.py','common.py','audit.py')]
    paths+=[HERE/'monomial_radix.h',P/'round98/monomial_order.h',P/'round98/generate.py']
    return list(dict.fromkeys(paths))

baseline.native.source_paths=source_paths

def build():
    baseline.build()
    from generate import producer_source,adapter_source
    out=HERE/'build';compiler=os.environ.get('CXX','clang++')
    suffix='.dylib' if sys.platform=='darwin' else '.so';shared=['-dynamiclib'] if sys.platform=='darwin' else ['-shared','-fPIC']
    receipt=json.loads((out/'receipt.json').read_text());receipt.update(schema='monomial-radix-build/1',executables={})
    modes=(('', ['-O3']),('-ubsan',['-O1','-g','-fsanitize=undefined','-fsanitize-undefined-trap-on-error','-fno-sanitize-recover=all']))
    for arm,policy in POLICIES.items():
        engine=out/f'f4_radix_{arm}.inc';engine.write_text(producer_source(policy))
        adapter=out/f'radix_{arm}.cpp';adapter.write_text(adapter_source(engine.name))
        for path in (engine,adapter):receipt['generated'][path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
        for tag,flags in modes:
            binary=out/(f'radix_{arm}'+tag+suffix)
            cmd=[compiler,'-std=c++17','-Wall','-Wextra','-Werror',*flags,*shared,'-I',str(P/'round11'),'-I',str(P/'round55'),'-I',str(HERE),'-I',str(P/'round98'),'-DPERSISTENT_ORDER=1','-DPIVOT_KEYS=1','-DINDEXED_REDUCERS=0',str(adapter),'-o',str(binary)]
            subprocess.run(cmd,check=True);receipt['commands'].append(cmd);receipt['binaries'][binary.name]=hashlib.sha256(binary.read_bytes()).hexdigest()
    for tag,flags in modes:
        executable=out/('radix_controls'+tag+'.exe')
        cmd=[compiler,'-std=c++17','-Wall','-Wextra','-Werror',*flags,'-pthread','-I',str(P/'round55'),'-I',str(HERE),'-I',str(P/'round98'),'-I',str(out),'-DPERSISTENT_ORDER=1','-DPIVOT_KEYS=1','-DINDEXED_REDUCERS=0',str(HERE/'radix_controls.cpp'),'-o',str(executable)]
        subprocess.run(cmd,check=True);receipt['commands'].append(cmd);receipt['executables'][executable.name]=hashlib.sha256(executable.read_bytes()).hexdigest()
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('MONOMIAL_RADIX_BUILD_PASS',len(receipt['binaries']),flush=True)

if __name__=='__main__':build()
