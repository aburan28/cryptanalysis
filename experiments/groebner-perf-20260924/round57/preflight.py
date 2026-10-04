"""Fresh complete-query and algebra controls before admitting any timed panel."""
import argparse
import gzip
import json
from pathlib import Path
import platform
from common import HERE,P,Context,arms,bindings,fixtures,host_identity,identity,read,sha,verify_bindings
from algebraic_certificate import verify
from boolean_basis import certify_boolean_basis

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    bound=bindings();contexts={}
    prior=read(P/'round56/results/frozen-screen.json.gz')
    previous={(r['name'],r['variant'],r['sanitizer']):r['result'] for r in prior['rows']}
    report={'schema':'sparse-f4-query-preflight/1','status':'RUNNING','plan_sha256':sha(HERE/'measurement_plan.json'),'bindings':bound,
            'inputs':fixtures(),'rows':[],'platform':platform.platform(),'architecture':platform.machine(),'host':host_identity(),'timing_eligible':False}
    def save():args.output.write_bytes(gzip.compress(json.dumps(report,separators=(',',':')).encode(),mtime=0))
    save()
    try:
        for u in (False,True):contexts[u]=Context(u)
        for case in fixtures():
            results={}
            for arm in arms(case):
                for u,context in contexts.items():
                    row=context.run(case['name'],arm,export_proof=True);r=row['result']
                    assert r['status'] in ('solved','gb','inconclusive'),(case['name'],arm,r)
                    if r['verified']:
                        if arm=='evaluation':audit=certify_boolean_basis(case['nvars'],case['equations'],r['basis'])
                        else:audit=verify(case['nvars'],case['equations'],r['basis'],r['proof'])
                        assert audit['verified'],(case['name'],arm,audit)
                        r['python_original_equations_audit']=audit
                    if arm!='evaluation':
                        old=previous[case['name'],arm,u]
                        for key in ('basis','proof','top_stats'):assert old.get(key)==r.get(key),(case['name'],arm,key)
                        logical=lambda v:{k:x for k,x in v['producer_stats'].items() if not k.endswith('_seconds')}
                        assert logical(old)==logical(r)
                        assert old['verified']==r['verified']
                    results[arm,u]=r
                    report['rows'].append({'name':case['name'],'arm':arm,'sanitizer':u,'identity':identity(r),'measurement':row})
                    save();print('PREFLIGHT',case['name'],arm,u,r['status'],flush=True)
                assert identity(results[arm,False])==identity(results[arm,True]),(case['name'],arm)
            bases=[sorted(tuple(sorted(row)) for row in r['basis']) for r in results.values() if r['verified']]
            if bases:assert all(b==bases[0] for b in bases)
    except BaseException as error:
        report.update(status='FAIL',error=repr(error));save();raise
    finally:
        for context in contexts.values():context.close()
    verify_bindings(bound);assert len(report['rows'])==214
    report['status']='PASS';save();print('PREFLIGHT_PASS',len(report['rows']),flush=True)
if __name__=='__main__':main()
