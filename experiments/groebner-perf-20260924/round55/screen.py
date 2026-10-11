"""Frozen 23-case algebra screen; all failures retained, timing ineligible."""
import argparse,gzip,hashlib,json,sys
from pathlib import Path
from query import HERE,Query,anf_from_equations
sys.path.insert(0,str(HERE.parent/'round5'))
from algebraic_certificate import verify
LIMITS=dict(max_work=20_000_000,max_nodes=500_000,max_rows=4096,batch=64,max_check_work=20_000_000,max_retained_terms=2_000_000)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    fixture=HERE.parent/'round13/results/confirmation.json.gz'
    old=json.loads(gzip.decompress(fixture.read_bytes()));inputs=old['inputs'];assert len(inputs)==23
    receipt=json.loads((HERE/'build/receipt.json').read_text())
    bindings={str(HERE.parent/name):digest for name,digest in receipt['sources'].items()}
    for kind in ('binaries','generated'):
        bindings.update({str(HERE/'build'/name):digest for name,digest in receipt[kind].items()})
    for p in HERE.glob('*.py'): bindings[str(p)]=sha(p)
    for name in ('algebraic_certificate.py','boolean_sparse.py'):
        p=HERE.parent/'round5'/name
        if p.exists(): bindings[str(p)]=sha(p)
    for p,digest in bindings.items(): assert sha(Path(p))==digest,p
    queries={(mode,ubsan):Query(mode,ubsan) for mode,ubsan in (('prior',False),('cached',False),('probe',False),('probe',True))}
    report={'schema':'checked-chain-algebra-screen/1','status':'RUNNING','fixture_sha256':sha(fixture),'bindings':bindings,'limits':LIMITS,'inputs':inputs,'rows':[],'timing_eligible':False,'candidate_id':None,'online_speedup':None,'scope':'Algebraic basis production and independent certification from frozen equations. Includes no target descent, root extraction or curve replay, so this is not complete query performance.'}
    def save(): args.output.write_bytes(gzip.compress(json.dumps(report,separators=(',',':')).encode(),mtime=0))
    for item in inputs:
        equations=item['equations'];n=item['nvars'];anf=anf_from_equations(equations);answers={}
        for (mode,ubsan),query in queries.items():
            result=query.compute(n,len(equations),anf,export_proof=True,**LIMITS)
            assert result['status'] in ('gb','inconclusive'),(item['name'],mode,result)
            if result['verified']:
                independent=verify(n,equations,result['basis'],result['proof'])
                assert independent['verified'],(item['name'],mode,independent)
                result['python_original_equations_audit']=independent
            answers[mode,ubsan]=result
            report['rows'].append({'name':item['name'],'workload_sha256':item['workload_sha256'],'variant':mode,'sanitizer':ubsan,'result':result})
            save()
            print('CASE',item['name'],mode,ubsan,result['status'],'work',result['producer_stats']['work'],'chains',result.get('chain_stats',{}).get('pruned_pairs',0),flush=True)
        solved=[r['basis'] for r in answers.values() if r['verified']]
        if solved: assert all(g==solved[0] for g in solved)
        a,b=answers['probe',False],answers['probe',True]
        for key in ('status','verified','basis','proof','chain_stats'): assert a.get(key)==b.get(key),(item['name'],key)
        assert {k:v for k,v in a['producer_stats'].items() if not k.endswith('_seconds')}=={k:v for k,v in b['producer_stats'].items() if not k.endswith('_seconds')}
    for p,digest in bindings.items(): assert sha(Path(p))==digest,p
    report['status']='PASS';save();print('ALGEBRA_SCREEN_PASS',len(report['rows']),flush=True)
if __name__=='__main__': main()
