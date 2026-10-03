"""Fresh planted PDP queries, bounded extraction and independent curve replay."""
import argparse
from dataclasses import replace
import gzip
import hashlib
import json
from pathlib import Path
import platform
import sys
from query import HERE,Query
from screen import LIMITS
sys.path.insert(0,str(HERE.parent/'round4'))
from descent_plan import DescentPlan
sys.path.insert(0,str(HERE.parent/'round5'))
from algebraic_certificate import verify
from descend import make_instance,verify_solution,GF2n

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def logical(r): return {k:v for k,v in r['producer_stats'].items() if not k.endswith('_seconds')}
def extract(instance,result):
    if not result['verified']: return result
    assert instance.nvars<=12
    result.update(algebra_verified=True,verified=False,assignments_visited=0,roots_replayed=0)
    for assignment in range(1<<instance.nvars):
        result['assignments_visited']+=1
        if any(sum((m&assignment)==m for m in row)%2 for row in result['basis']): continue
        result['roots_replayed']+=1
        if instance.evaluate(assignment)==0 and verify_solution(instance,assignment):
            result.update(status='solved',verified=True,assignment=assignment,curve_replay=True)
            break
    if not result['verified']: result['status']='gb-no-verified-solution'
    return result
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    fixture=HERE.parent/'round13/results/confirmation.json.gz'
    inputs=[i for i in json.loads(gzip.decompress(fixture.read_bytes()))['inputs'] if i['boundary']=='pdp']
    assert len(inputs)==15
    variants=('prior','chain','filter','chain_filter')
    queries={(v,u):Query(v,u) for v in variants for u in (False,True)}
    receipt=json.loads((HERE/'build/receipt.json').read_text())
    bindings={str(HERE.parent/name):d for name,d in receipt['sources'].items()}
    for kind in ('binaries','generated'):
        bindings.update({str(HERE/'build'/name):d for name,d in receipt[kind].items()})
    for directory in (HERE,HERE.parent/'round5',HERE.parent/'round4',HERE.parent.parent/'pdp-scaling'):
        for p in directory.glob('*.py'): bindings[str(p)]=sha(p)
    for p in (HERE.parent.parent/'pdp-scaling').glob('*.json'): bindings[str(p)]=sha(p)
    for p,d in bindings.items(): assert sha(Path(p))==d,p
    report={'schema':'sparse-f4-complete-query-controls/1','status':'RUNNING','fixture_sha256':sha(fixture),'inputs':inputs,'limits':LIMITS,'bindings':bindings,
            'architecture':platform.machine(),'platform':platform.platform(),'rows':[],'timing_eligible':False,'candidate_id':None,'online_speedup':None,
            'scope':'Planted PDP correctness controls. Each call starts from a target coordinate with fresh descent, packing, solve, independent ideal/completion checking, <=4096-assignment extraction, original-equation evaluation and curve replay. Not natural yield or a full IC target solve.'}
    plans={}
    def save(): args.output.write_bytes(gzip.compress(json.dumps(report,separators=(',',':')).encode(),mtime=0))
    for item in inputs:
        original=make_instance(item['n'],item['m'],item['ell'],seed=item['seed'])
        assert (original.mod,original.b,original.xR)==(item['mod'],item['b'],item['target_x'])
        assert [sorted(r) for r in original.equations()]==item['equations']
        shape=(item['n'],item['mod'],item['b'],item['m'],item['ell'])
        if shape not in plans: plans[shape]=DescentPlan(*shape)
        answers={}
        for (variant,ubsan),q in queries.items():
            anf=plans[shape].descend(original.xR)
            assert anf==original.anf
            current=replace(original,anf=anf)
            result=q.compute(current.nvars,len(item['equations']),anf,export_proof=True,**LIMITS)
            assert result['status'] in ('gb','inconclusive'),(item['name'],variant,result)
            if result['verified']:
                audit=verify(current.nvars,item['equations'],result['basis'],result['proof'])
                assert audit['verified']
                result['python_original_equations_audit']=audit
            result=extract(current,result)
            if result['verified']:
                assert original.evaluate(result['assignment'])==0
                assert verify_solution(original,result['assignment'])
                result['reference_equations_and_curve_replay']=True
            if item['nvars']==6: assert result['verified'],(item['name'],variant,result)
            answers[variant,ubsan]=result
            report['rows'].append({'name':item['name'],'workload_sha256':item['workload_sha256'],'variant':variant,'sanitizer':ubsan,'result':result})
            save();print('QUERY',item['name'],variant,ubsan,result['status'],flush=True)
        for variant in variants:
            a,b=answers[variant,False],answers[variant,True]
            for key in ('status','reason','verified','basis','proof','top_stats','assignment','assignments_visited','roots_replayed'):
                assert a.get(key)==b.get(key),(item['name'],variant,key)
            assert logical(a)==logical(b)
        solved=[r['basis'] for r in answers.values() if r['verified']]
        if solved: assert all(g==solved[0] for g in solved)
    for p,d in bindings.items(): assert sha(Path(p))==d,p
    report['status']='PASS';save();print('COMPLETE_QUERY_CONTROLS_PASS',len(report['rows']),flush=True)
if __name__=='__main__': main()
