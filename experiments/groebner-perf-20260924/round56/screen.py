"""Matched frozen algebra controls; retain budgets and independently check success."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import platform
import sys
from query import HERE,Query,VARIANTS,anf_from_equations
sys.path.insert(0,str(HERE.parent/'round5'))
from algebraic_certificate import verify
LIMITS=dict(max_work=20_000_000,max_nodes=500_000,max_rows=4096,batch=64,max_check_work=20_000_000,max_retained_terms=2_000_000)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def logical(r): return {k:v for k,v in r['producer_stats'].items() if not k.endswith('_seconds')}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    fixture=HERE.parent/'round13/results/confirmation.json.gz'
    frozen=json.loads(gzip.decompress(fixture.read_bytes()));inputs=frozen['inputs'];assert len(inputs)==23
    receipt=json.loads((HERE/'build/receipt.json').read_text())
    bindings={str(HERE.parent/name):digest for name,digest in receipt['sources'].items()}
    for kind in ('binaries','generated'):
        bindings.update({str(HERE/'build'/name):digest for name,digest in receipt[kind].items()})
    for p in HERE.glob('*.py'): bindings[str(p)]=sha(p)
    for p in (HERE.parent/'round5').glob('*.py'): bindings[str(p)]=sha(p)
    for p,digest in bindings.items(): assert sha(Path(p))==digest,p
    queries={(mode,ubsan):Query(mode,ubsan) for mode in VARIANTS for ubsan in (False,True)}
    report={'schema':'deferred-tail-algebra-screen/1','status':'RUNNING','fixture_sha256':sha(fixture),'bindings':bindings,'limits':LIMITS,'inputs':inputs,'rows':[],
            'platform':platform.platform(),'architecture':platform.machine(),'timing_eligible':False,'candidate_id':None,'online_speedup':None,
            'scope':'Algebraic production and independent certification from frozen equations. No target descent, root extraction or curve replay; not complete query performance.'}
    def save(): args.output.write_bytes(gzip.compress(json.dumps(report,separators=(',',':')).encode(),mtime=0))
    for item in inputs:
        equations=item['equations'];n=item['nvars'];anf=anf_from_equations(equations);answers={}
        for (mode,ubsan),query in queries.items():
            result=query.compute(n,len(equations),anf,export_proof=True,**LIMITS)
            assert result['status'] in ('gb','inconclusive'),(item['name'],mode,result)
            if result['verified']:
                audit=verify(n,equations,result['basis'],result['proof'])
                assert audit['verified'],(item['name'],mode,audit)
                result['python_original_equations_audit']=audit
            answers[mode,ubsan]=result
            report['rows'].append({'name':item['name'],'workload_sha256':item['workload_sha256'],'variant':mode,'sanitizer':ubsan,'result':result})
            save()
            print('CASE',item['name'],mode,ubsan,result['status'],'work',result['producer_stats']['work'],'top',result['top_stats'],flush=True)
        solved=[r['basis'] for r in answers.values() if r['verified']]
        if solved: assert all(g==solved[0] for g in solved)
        for mode in VARIANTS:
            a,b=answers[mode,False],answers[mode,True]
            for key in ('status','reason','verified','basis','proof','top_stats'):
                assert a.get(key)==b.get(key),(item['name'],mode,key)
            assert logical(a)==logical(b),(item['name'],mode,'work')
    for p,digest in bindings.items(): assert sha(Path(p))==digest,p
    report['status']='PASS';save();print('ALGEBRA_SCREEN_PASS',len(report['rows']),flush=True)
if __name__=='__main__': main()
