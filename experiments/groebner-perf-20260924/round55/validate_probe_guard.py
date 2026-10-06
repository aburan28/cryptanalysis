"""Exercise probe rollback and resource boundaries in optimized and UBSan code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
HERE=Path(__file__).resolve().parent
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    report={'status':'RUNNING','commands':[],'results':[],'bindings':{},'timing_eligible':False}
    for variant,extra in (('probe',[]),('tiny_probe',['-DCHAIN_PROBE_WORK=8']),('tiny_cache',['-DCHAIN_CACHE_LIMIT=1'])):
        for ubsan in (False,True):
            binary=HERE/'build'/('test-guard-'+variant+('-ubsan' if ubsan else ''))
            flags=['-O1','-g','-fsanitize=undefined','-fsanitize-undefined-trap-on-error','-fno-sanitize-recover=all'] if ubsan else ['-O3']
            cmd=[os.environ.get('CXX','clang++'),'-std=c++17','-Wall','-Wextra','-Werror','-DPERSISTENT_ORDER=1','-DPIVOT_KEYS=1','-DINDEXED_REDUCERS=0',*extra,*flags,str(HERE/'test_probe_guard.cpp'),'-o',str(binary)]
            subprocess.run(cmd,check=True);report['commands'].append(cmd)
            result=json.loads(subprocess.check_output([str(binary)],text=True))
            assert result['work_boundaries']==65 and result['node_boundaries']==9
            assert result['aborted_probes']>0
            if variant=='tiny_probe': assert result['soft_limits']>0
            report['results'].append({'variant':variant,'sanitizer':ubsan,'result':result})
            report['bindings'][str(binary)]=sha(binary)
    for name in ('test_probe_guard.cpp','chain_stats.h','checked_chains.inc','build/checked.inc','validate_probe_guard.py'):
        p=HERE/name;report['bindings'][str(p)]=sha(p)
    for a,b in zip(report['results'][::2],report['results'][1::2]): assert a['result']==b['result']
    report['status']='PASS';args.output.write_text(json.dumps(report,indent=2)+'\n')
    print('PROBE_GUARD_PASS',len(report['results']))
if __name__=='__main__': main()
