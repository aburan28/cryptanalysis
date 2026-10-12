"""Frozen complete-query comparisons with explicit failed attempts and setup."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import platform
from common import Context,HERE,plan,digest

def run(output,*,controls=False):
    output.mkdir(parents=True,exist_ok=False)
    protocol=plan();build=json.loads((HERE/'build/receipt.json').read_text())
    for name,sha in build['sources'].items():
        assert hashlib.sha256((HERE.parent.parent/name).read_bytes()).hexdigest()==sha,name
    for name,sha in {**build['binaries'],**build['generated'],**build['resources'],**build['executables']}.items():
        assert hashlib.sha256((HERE/'build'/name).read_bytes()).hexdigest()==sha,name
    report=dict(schema='normal-scratch-evidence/1',plan=protocol,plan_sha256=digest(protocol),
        build=build,platform=platform.platform(),architecture=platform.machine(),controls=controls,
        timing_eligible=False,qualified_speedup=None,aggregate_speedup=None,online_speedup=None,
        preparation=[],rows=[],status='RUNNING')
    def save():(output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    save()
    for sanitized in ([False,True] if controls else [False]):
        context=Context(sanitizer=sanitized)
        report['preparation'].append(dict(sanitized=sanitized,seconds=context.preparation_seconds,
            cases=list(context.cases),plans=len(context.plans),workspaces=len(context.workspaces),
            numerical_training=False))
        for name,case in context.cases.items():
            for repetition,order in enumerate([protocol['arms']] if controls else protocol['orders']):
                for arm in order:
                    start=datetime.datetime.now(datetime.timezone.utc).isoformat()
                    measured=context.run(name,arm)
                    report['rows'].append(dict(name=name,fixture=case,input_sha256=digest(case),
                        sanitized=sanitized,repetition=repetition,arm=arm,
                        role='control' if controls else ('warmup' if repetition<protocol['warmup_rounds'] else 'observation'),
                        wall_start=start,wall_end=datetime.datetime.now(datetime.timezone.utc).isoformat(),**measured))
            save()
            print('CASE_DONE',name,'ubsan' if sanitized else 'optimized',flush=True)
    report['status']='RECORDED_PENDING_AUDIT';save();print('PANEL_RECORDED',len(report['rows']),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);parser.add_argument('--controls',action='store_true')
    args=parser.parse_args();run(args.output,controls=args.controls)
