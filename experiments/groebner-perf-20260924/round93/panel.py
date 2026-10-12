"""Balanced complete algebra calls; fresh proofs, unchanged producer/layout policy."""
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
    report=dict(schema='scheduled-checker-evidence/1',plan=plan,plan_sha256=digest(plan),build=build,
        platform=platform.platform(),architecture=platform.machine(),controls=controls,
        timing_eligible=False,qualified_speedup=None,aggregate_speedup=None,online_speedup=None,
        preparation=[],rows=[])
    def save():(output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    for sanitized in ([False,True] if controls else [False]):
        queries={mode:Query(sanitizer=sanitized,checker_order=mode) for mode in ('legacy','completion-first')}
        for family in plan['families']:
            n=family['nvars'];e=len(family['training']);d=family['degree_bound'];r=0 if d<=1 else 1
            start=time.perf_counter()
            layouts={mode:q.layout(n,e,d,r) for mode,q in queries.items()}
            setup=time.perf_counter()-start
            assert all(l._handle for l in layouts.values())
            assert layouts['legacy'].support==layouts['completion-first'].support
            report['preparation'].append(dict(family=family['name'],sanitized=sanitized,shape=[n,e,d,r],
                layouts={mode:l.stats for mode,l in layouts.items()},total_seconds=setup,numerical_training=False))
            evaluation=Evaluation(n,e,sanitizer=sanitized)
            try:
                for target,rows in enumerate(family['targets']):
                    original=DenseInput(n,rows,layouts['legacy'].support)
                    for repetition,order in enumerate([plan['arms']] if controls else plan['orders']):
                        for arm in order:
                            wall_start=datetime.datetime.now(datetime.timezone.utc).isoformat()
                            start=time.perf_counter()
                            if arm=='signature':result=signature(n,original)
                            elif arm=='evaluation':result=evaluation.compute(original)
                            else:
                                engine,mode=arm.split('-',1)
                                result=queries[mode].compute(original,layout=layouts[mode] if engine=='matrix' else None,
                                    export_proof=True,**plan['limits'])
                            elapsed=time.perf_counter()-start
                            report['rows'].append(dict(family=family['name'],target=target,nvars=n,equations=rows,
                                input_sha256=digest(dict(nvars=n,equations=rows)),sanitized=sanitized,repetition=repetition,arm=arm,
                                role='control' if controls else ('warmup' if repetition<plan['warmup_rounds'] else 'observation'),
                                wall_start=wall_start,wall_end=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                complete_call_seconds=elapsed,result=result))
                    save()
            finally:
                evaluation.close()
                for layout in layouts.values():layout.close()
            print('FAMILY_DONE',family['name'],'ubsan' if sanitized else 'optimized',flush=True)
    report['status']='RECORDED_PENDING_AUDIT';save();print('PANEL_RECORDED',len(report['rows']),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);parser.add_argument('--controls',action='store_true')
    args=parser.parse_args();run(args.output,controls=args.controls)
