"""Retain exact larger-system certificates; no full IC or speedup claim."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import platform
import random
import time

from conditional import Basis, HERE, Packed
from reference import branch_counts, evaluate, verify_basis

SHAPES=((11,11,31),(12,12,31),(8,24,65),(5,43,83),(1,62,128))


def fixture(x,y,e,seed):
    rng=random.Random(seed)
    target=rng.randrange(1<<(x+y))
    masks=[*[1<<j for j in range(x+y)],*[(1<<i)|(1<<(x+j)) for i in range(x) for j in range(y)]]
    items=[(m,rng.randrange(1<<e)) for m in masks]
    return [(0,evaluate(items,target)),*items],target


def source_hashes():
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(HERE.iterdir()) if p.suffix in ('.py','.cpp','.hpp','.h')}


def audit_report(report):
    assert report['schema']=='round27-large-certificates/1'
    assert report['source_sha256']==source_hashes()
    assert report['build_receipt']['sources']==report['source_sha256']
    for component in ('producer','checker'):
        assert report['binaries'][component] in {
            v for k,v in report['build_receipt']['binaries'].items()
            if k in (component+'.so',component+'.dylib')}
    assert report['candidate_id'] is report['IC_online_ms'] is report['rho_online_ms'] is None
    assert len(report['rows'])==len(SHAPES)
    for row,shape in zip(report['rows'],SHAPES):
        x,y,e=shape
        assert row['shape']==list(shape)
        items,target=fixture(x,y,e,1000+x+y)
        assert row['items']==[list(p) for p in items] and row['planted_assignment']==target
        counts=branch_counts(x,y,e,items)
        assert row['independent_counts']==counts
        result=row['result']
        assert result['status']=='gb' and result['complete'] and result['groebner_verified']
        cert=result['basis_certificate']
        roots=cert['solutions']
        assert cert['verified'] and cert['ideal_equality'] and cert['reduced_groebner_basis']
        assert cert['stats']['branches']==result['metrics']['branches']==1<<x
        consistent=sum(v['branches'] for v in counts['histogram'] if v['status']=='consistent')
        assert cert['stats']['consistent']==result['metrics']['consistent']==consistent
        assert cert['root_count']==cert['standard_monomials']==len(roots)==counts['root_count']
        assert target in roots and verify_basis(x+y,items,roots,result['basis_terms'],counts['root_count'])
        assert result['basis_sha256']==hashlib.sha256(json.dumps(result['basis_terms'],sort_keys=True).encode()).hexdigest()
        assert result['binary_sha256']==report['binaries']['producer']
        assert result['verifier_binary_sha256']==report['binaries']['checker']
        assert row['complete_certified_ns']>0 and row['independent_python_audit_ns']>0
    return {'verified':True,'systems':len(report['rows']),
            'variables':[x+y for x,y,_ in SHAPES],'enumerated_full_cubes':False,
            'scope':'Planted generic bilinear Boolean controls; no curve query or IC recovery.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--audit',type=Path)
    args=parser.parse_args()
    if args.audit:
        print(json.dumps(audit_report(json.loads(gzip.decompress(args.audit.read_bytes()))),indent=2))
        return
    if args.output is None or args.output.exists():
        parser.error('provide a fresh --output or existing --audit')
    report={'schema':'round27-large-certificates/1','candidate_id':None,'IC_online_ms':None,
            'rho_online_ms':None,'source_sha256':source_hashes(),'rows':[],
            'build_receipt':json.loads((HERE/'build/receipt.json').read_text()),
            'host':{'platform':platform.platform(),'architecture':platform.machine(),
                    'python':platform.python_version()},
            'timing_eligible':False,'scope':'Correctness controls, no performance admission or speedup claim'}
    for x,y,e in SHAPES:
        items,target=fixture(x,y,e,1000+x+y)
        with Basis(x,y,e) as b:
            report['binaries']={'producer':b.producer.binary_sha256,'checker':b.checker.binary_sha256}
            start=time.perf_counter_ns()
            result=b.compute(Packed(x+y,e,items))
            elapsed=time.perf_counter_ns()-start
        start=time.perf_counter_ns()
        counts=branch_counts(x,y,e,items)
        roots=result['basis_certificate']['solutions']
        assert verify_basis(x+y,items,roots,result['basis_terms'],counts['root_count'])
        report['rows'].append({'shape':[x,y,e],'items':[list(p) for p in items],
            'planted_assignment':target,'result':result,'independent_counts':counts,
            'complete_certified_ns':elapsed,'independent_python_audit_ns':time.perf_counter_ns()-start})
    audit_report(report)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('xb') as stream:
        stream.write(gzip.compress(json.dumps(report,sort_keys=True).encode(),mtime=0))
    print(json.dumps(audit_report(report)))


if __name__=='__main__':
    main()
