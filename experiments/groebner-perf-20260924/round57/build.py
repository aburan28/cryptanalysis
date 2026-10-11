"""Rebuild unchanged F4/evaluation engines and freeze the query timing sources."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
HERE=Path(__file__).resolve().parent
P=HERE.parent
ROOT=HERE.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    out=HERE/'build';out.mkdir(exist_ok=True);commands=[]
    cmd=[sys.executable,str(P/'round56/build.py')]
    subprocess.run(cmd,check=True);commands.append(cmd)
    # Keep the optimized evaluation build unchanged. Trap-mode UBSan avoids
    # loading a dynamic sanitizer runtime into the host Python process.
    compiler=os.environ.get('CXX','clang++')
    suffix='.dylib' if sys.platform=='darwin' else '.so'
    shared=['-dynamiclib'] if sys.platform=='darwin' else ['-shared','-fPIC']
    (P/'round4/build').mkdir(exist_ok=True)
    for tag,flags in (('', ['-O3']),('-ubsan',['-O1','-g','-fsanitize=undefined','-fsanitize-undefined-trap-on-error','-fno-sanitize-recover=all'])):
        for name in ('packed_dual','packed_certificate'):
            cmd=[compiler,'-std=c++17','-Wall','-Wextra','-Werror',*flags,*shared,str(P/'round4'/(name+'.cpp')),
                 '-o',str(P/'round4/build'/(name+tag+suffix))]
            subprocess.run(cmd,check=True);commands.append(cmd)
    previous=json.loads((P/'round56/build/receipt.json').read_text())
    sources={str((P/name).relative_to(ROOT)):d for name,d in previous['sources'].items()}
    for directory in (HERE,P/'round4',P/'round2',P/'round5',P.parent/'pdp-scaling'):
        for pattern in ('*.py','*.cpp','*.h'):
            for p in directory.glob(pattern):sources[str(p.relative_to(ROOT))]=sha(p)
    sources[str((HERE/'measurement_plan.json').relative_to(ROOT))]=sha(HERE/'measurement_plan.json')
    generated={str((P/'round56/build'/name).relative_to(ROOT)):d for name,d in previous['generated'].items()}
    binaries={str((P/'round56/build'/name).relative_to(ROOT)):d for name,d in previous['binaries'].items()}
    suffix='.dylib' if sys.platform=='darwin' else '.so'
    for p in (P/'round4/build').glob('*'+suffix):binaries[str(p.relative_to(ROOT))]=sha(p)
    receipt={'schema':'sparse-f4-query-build/1','commands':commands,'sources':sources,'generated':generated,'binaries':binaries,
             'plan_sha256':sha(HERE/'measurement_plan.json'),'compiler':subprocess.check_output([os.environ.get('CXX','clang++'),'--version'],text=True),
             'platform':platform.platform(),'architecture':platform.machine(),'timing_eligible':False}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()
