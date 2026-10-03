"""Match every frozen answer, proof and work prefix; replay successful proofs."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
from query import HERE, Query, VARIANTS, anf_from_equations
from test_columns import trace
from algebraic_certificate import verify

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(path,value):
    path.write_bytes(gzip.compress(json.dumps(value,sort_keys=True,separators=(',',':')).encode(),mtime=0))
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True,type=Path);args=parser.parse_args()
    frozen=HERE.parent/'round56/results/frozen-screen.json.gz'
    screen=json.loads(gzip.decompress(frozen.read_bytes()))
    baseline={r['name']:r['result'] for r in screen['rows'] if r['variant']=='chain_filter' and not r['sanitizer']}
    receipt=json.loads((HERE/'build/receipt.json').read_text())
    bindings={}
    for group in ('sources','generated','binaries'):
        root=HERE.parent if group=='sources' else HERE/'build'
        for name,wanted in receipt[group].items():
            path=root/name;assert sha(path)==wanted;bindings[str(path)]=wanted
    report={'status':'RUNNING','scope':'Algebra-stage correctness; not latency or complete IC evidence',
            'candidate_id':None,'online_speedup':None,'timing_eligible':False,'frozen_sha256':sha(frozen),
            'bindings':bindings,'limits':screen['limits'],'inputs':screen['inputs'],'rows':[],'independent_proof_replays':0}
    for case in screen['inputs']:
        expected=baseline[case['name']]
        if expected['verified']:
            result=verify(case['nvars'],case['equations'],expected['basis'],expected['proof'],
                          max_work=screen['limits']['max_check_work'],max_retained_terms=screen['limits']['max_retained_terms'])
            assert result['verified'],case['name'];report['independent_proof_replays']+=1
        for variant in VARIANTS:
            for sanitizer in (False,True):
                answer=Query(variant,sanitizer).compute(case['nvars'],len(case['equations']),
                    anf_from_equations(case['equations']),export_proof=True,**screen['limits'])
                assert trace(answer)==trace(expected),(case['name'],variant,sanitizer)
                report['rows'].append({'name':case['name'],'variant':variant,'sanitizer':sanitizer,'result':answer})
        print('EXACT_TRACE_PASS',case['name'],expected['status'],flush=True)
    for path,wanted in bindings.items():assert sha(Path(path))==wanted,path
    report['status']='PASS';save(args.out,report)
    print('VALIDATION_PASS',len(report['rows']),report['independent_proof_replays'],flush=True)
if __name__=='__main__':main()
