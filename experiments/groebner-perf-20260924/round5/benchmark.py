"""Proof-production/check accounting on frozen algebra inputs, including failures."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import resource
import sys
import time

from native_f4 import compute
from algebraic_certificate import verify
from reference_prover import prove, ProverBudget
from workloads import workloads

HERE=Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repetitions',type=int,default=3)
    parser.add_argument('--output',type=Path,default=HERE/'results/proof-benchmark.json.gz')
    args=parser.parse_args()
    report={'scope':'Algebra-only proof production plus checking; not a PDP/IC/rho measurement',
            'candidate_id':None,'IC_online_ms':None,'rho_online_ms':None,
            'boundary':'Per-call wall starts before input preparation and stops after proof parsing and independent verification; native subprocess launch is included. Input fixture generation and prior binary compilation excluded.',
            'untraced_boundary':'Native proof recording disabled and no timed independent verification; compared only for instrumentation overhead, never a certified speedup.',
            'limits':{'native_work':20_000_000,'reference_work':20_000_000,'proof_nodes':500_000,
                      'matrix_rows':4096,'batch':64,'native_timeout_seconds':15,
                      'verifier_work':20_000_000,'verifier_retained_terms':2_000_000},
            'host':{'platform':platform.platform(),'python':sys.version,'logical_cpus':os.cpu_count(),
                    'load_start':os.getloadavg()},'cases':workloads(),'rows':[],'certificates':{}}
    rng=random.Random(2026092512)
    for case in report['cases']:
        case['workload_sha256']=sha(json.dumps(case,sort_keys=True,separators=(',',':')).encode())
        n,equations=case['nvars'],case['equations']
        for rep in range(args.repetitions+1):
            order=['native','untraced','reference']
            rng.shuffle(order)
            row={'name':case['name'],'repetition':rep,'warmup':rep==0,'order':order,'load':os.getloadavg()}
            for arm in order:
                start=time.perf_counter()
                if arm!='reference':
                    result=compute(n,equations,max_work=20_000_000,max_nodes=500_000,max_rows=4096,timeout=15,
                                   record=arm=='native',check=arm=='native')
                else:
                    try:
                        result=prove(n,equations,max_work=20_000_000,max_nodes=500_000)
                        produced=time.perf_counter()
                        certificate=verify(n,equations,result['basis'],result['proof'],max_work=20_000_000,max_retained_terms=2_000_000)
                        result.update(status='gb' if certificate['verified'] else certificate['status'],
                                      verified=certificate['verified'],certificate=certificate,
                                      producer_seconds=produced-start,verification_seconds=time.perf_counter()-produced)
                    except ProverBudget as error:
                        result={'status':'inconclusive','verified':False,'reason':str(error)}
                result['charged_wall_seconds']=time.perf_counter()-start
                if result.get('proof') is not None:
                    proof=result.pop('proof')
                    encoded=json.dumps(proof,separators=(',',':')).encode()
                    result['proof_bytes']=len(encoded)
                    result['proof_nodes']=len(proof['nodes'])
                    result['proof_sha256']=sha(encoded)
                    if result.get('verified'):
                        report['certificates'].setdefault(result['proof_sha256'],
                            {'nvars':n,'equations':equations,'basis':result['basis'],'proof':proof})
                row[arm]=result
            if row['native'].get('verified') and row['untraced']['status']=='gb':
                assert row['native']['basis']==row['untraced']['basis']
            if row['native'].get('verified') and row['reference'].get('verified'):
                assert row['native']['basis']==row['reference']['basis']
            report['rows'].append(row)
            args.output.write_bytes(gzip.compress(json.dumps(report,separators=(',',':')).encode(),mtime=0))
        print(case['name'],{arm:row[arm]['status'] for arm in order},flush=True)
    report['host']['load_end']=os.getloadavg()
    # Process high-water marks, NOT exclusive per-case memory or simultaneous
    # parent+child peak. Units differ by OS and are made explicit here.
    report['memory_high_water']={'unit':'bytes' if sys.platform=='darwin' else 'KiB',
        'parent':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'child':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        'per_case_peak':None,'simultaneous_total_peak':None}
    report['source_sha256']={p.name:sha(p.read_bytes()) for p in HERE.glob('*.py')}
    report['source_sha256']['native_f4.cpp']=sha((HERE/'native_f4.cpp').read_bytes())
    report['status']='RECORDED'
    args.output.write_bytes(gzip.compress(json.dumps(report,separators=(',',':')).encode(),mtime=0))


if __name__=='__main__':
    main()
