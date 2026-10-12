"""One frozen algebra system per query; reused layouts contain no training data."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import platform
import time
from query import HERE,Query,DenseInput
from comparators import Evaluation,signature

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def run(output,*,controls=False):
    output.mkdir(parents=True,exist_ok=False)
    plan=json.loads((HERE/'panel.json').read_text())
    build=json.loads((HERE/'build/receipt.json').read_text())
    for name,sha in build['sources'].items():
        assert hashlib.sha256((HERE.parent.parent/name).read_bytes()).hexdigest()==sha,name
    for name,sha in build['binaries'].items():
        assert hashlib.sha256((HERE/'build'/name).read_bytes()).hexdigest()==sha,name
    report=dict(schema='reusable-macaulay-evidence/1',plan=plan,plan_sha256=digest(plan),build=build,
        platform=platform.platform(),architecture=platform.machine(),controls=controls,
        timing_eligible=False,qualified_speedup=None,aggregate_speedup=None,online_speedup=None,
        preparation=[],rows=[])
    def save(): (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    for sanitized in ([False,True] if controls else [False]):
        query=Query(sanitizer=sanitized)
        for family in plan['families']:
            n=family['nvars'];equations=len(family['training']);d=family['degree_bound']
            r1,r2=(0,0) if d<=1 else (1,2)
            start=time.perf_counter()
            l1=query.layout(n,equations,d,r1)
            l2=query.layout(n,equations,d,r2)
            setup=time.perf_counter()-start
            assert l1._handle and l2._handle,(family['name'],l1.reason,l2.reason)
            assert l1.support==l2.support
            report['preparation'].append(dict(family=family['name'],sanitized=sanitized,
                shape_r1=list(l1.shape),shape_r2=list(l2.shape),r1_stats=l1.stats,r2_stats=l2.stats,
                total_seconds=setup,numerical_training=False))
            evaluation=Evaluation(n,equations,sanitizer=sanitized)
            try:
                for target_index,rows in enumerate(family['targets']):
                    original=DenseInput(n,rows,l1.support)
                    orders=[plan['arms']] if controls else plan['orders']
                    for repetition,order in enumerate(orders):
                        for arm in order:
                            wall_start=datetime.datetime.now(datetime.timezone.utc).isoformat()
                            start=time.perf_counter()
                            if arm=='fresh-f4': result=query.compute(original,export_proof=True,**plan['limits'])
                            elif arm=='fresh-layout-r1': result=query.compute(original,fresh_shape=l1.shape,export_proof=True,**plan['limits'])
                            elif arm=='reused-r1': result=query.compute(original,layout=l1,export_proof=True,**plan['limits'])
                            elif arm=='reused-r2': result=query.compute(original,layout=l2,export_proof=True,**plan['limits'])
                            elif arm=='signature': result=signature(n,original)
                            else: result=evaluation.compute(original)
                            elapsed=time.perf_counter()-start
                            report['rows'].append(dict(family=family['name'],target=target_index,nvars=n,equations=rows,
                                input_sha256=digest(dict(nvars=n,equations=rows)),sanitized=sanitized,repetition=repetition,arm=arm,
                                role='control' if controls else ('warmup' if repetition<plan['warmup_rounds'] else 'observation'),
                                wall_start=wall_start,wall_end=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                complete_call_seconds=elapsed,result=result))
                    save()
            finally:
                evaluation.close();l1.close();l2.close()
            print('FAMILY_DONE',family['name'],'ubsan' if sanitized else 'optimized',flush=True)
    report['status']='RECORDED_PENDING_AUDIT';save()
    print('PANEL_RECORDED',len(report['rows']),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--controls',action='store_true')
    args=parser.parse_args();run(args.output,controls=args.controls)
