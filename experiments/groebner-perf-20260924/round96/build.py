"""Fresh baseline and profiled kernels with the same exact checker."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
HERE=Path(__file__).resolve().parent
P=HERE.parent
spec=importlib.util.spec_from_file_location('baseline95_for96',P/'round95/build.py')
baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
baseline.HERE=HERE;baseline.native.HERE=HERE
original_sources=baseline.source_paths

def source_paths():
    paths=original_sources()+[P/'round95'/name for name in ('build.py','generate.py','query.py','common.py','audit.py')]
    paths+=[HERE/'profile.h',HERE/'profile_controls.cpp',P/'round62/query.py']
    return list(dict.fromkeys(paths))

baseline.native.source_paths=source_paths

def build():
    baseline.build()
    from generate import producer_source,adapter_source
    out=HERE/'build';(out/'profiled_engine.inc').write_text(producer_source());(out/'profiled_adapter.cpp').write_text(adapter_source())
    compiler=os.environ.get('CXX','clang++');suffix='.dylib' if sys.platform=='darwin' else '.so'
    shared=['-dynamiclib'] if sys.platform=='darwin' else ['-shared','-fPIC']
    receipt=json.loads((out/'receipt.json').read_text());receipt['schema']='producer-profile-build/1';receipt['executables']={}
    for tag,flags in (('', ['-O3']),('-ubsan',['-O1','-g','-fsanitize=undefined','-fsanitize-undefined-trap-on-error','-fno-sanitize-recover=all'])):
        common=[compiler,'-std=c++17','-Wall','-Wextra','-Werror',*flags,'-I',str(P/'round11'),'-I',str(P/'round55'),'-I',str(HERE),'-I',str(out),'-DPERSISTENT_ORDER=1','-DPIVOT_KEYS=1','-DINDEXED_REDUCERS=0']
        binary=out/('profiled_producer'+tag+suffix)
        cmd=[*common,*shared,str(out/'profiled_adapter.cpp'),'-o',str(binary)]
        subprocess.run(cmd,check=True);receipt['commands'].append(cmd)
        receipt['binaries'][binary.name]=hashlib.sha256(binary.read_bytes()).hexdigest()
        executable=out/('profile_controls'+tag+'.exe')
        cmd=[*common,str(HERE/'profile_controls.cpp'),'-o',str(executable)]
        subprocess.run(cmd,check=True);receipt['commands'].append(cmd)
        receipt['executables'][executable.name]=hashlib.sha256(executable.read_bytes()).hexdigest()
    for name in ('profiled_engine.inc','profiled_adapter.cpp'):receipt['generated'][name]=hashlib.sha256((out/name).read_bytes()).hexdigest()
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('PROFILE_BUILD_PASS',len(receipt['binaries']),flush=True)

if __name__=='__main__':build()
