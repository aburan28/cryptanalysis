"""Paired leased Macaulay comparison with explicit timeout and process-failure rows."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
from common import HERE,fixtures,plan,digest

def run_command(command,log_path,timeout):
    start=time.perf_counter_ns()
    with log_path.open('w') as log:
        process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            code=process.wait(timeout=timeout)
            result=dict(execution='completed' if code==0 else 'process-failure',exit_code=code)
        except subprocess.TimeoutExpired:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            code=process.wait()
            result=dict(execution='timeout',exit_code=code)
    return dict(**result,process_elapsed_ns=time.perf_counter_ns()-start)

def run(output,*,controls=False):
    output.mkdir(parents=True,exist_ok=False);(output/'cells').mkdir()
    protocol=plan();build=json.loads((HERE/'build/receipt.json').read_text())
    for name,sha in build['sources'].items():
        assert hashlib.sha256((HERE.parent.parent/name).read_bytes()).hexdigest()==sha,name
    for group in ('binaries','executables','generated','resources'):
        for name,sha in build[group].items():assert hashlib.sha256((HERE/'build'/name).read_bytes()).hexdigest()==sha,name
    report=dict(schema='minimal-macaulay-evidence/1',plan=protocol,plan_sha256=digest(protocol),
        build=build,platform=platform.platform(),architecture=platform.machine(),controls=controls,
        gpu=protocol['gpu'],timing_eligible=False,qualified_speedup=None,aggregate_speedup=None,
        online_speedup=None,rows=[],status='RUNNING')
    def save():
        temp=output/'report.tmp';temp.write_text(json.dumps(report,indent=2)+'\n');temp.replace(output/'report.json')
    save()
    for sanitized in ([False,True] if controls else [False]):
        for case in fixtures():
            for budget in protocol['budgets']:
                for repetition,order in enumerate([protocol['arms']] if controls else protocol['orders']):
                    for arm in order:
                        index=len(report['rows']);stem=f'{index:04d}';result_path=output/'cells'/(stem+'.json')
                        command=[sys.executable,str(HERE/'worker.py'),'--name',case['name'],'--arm',arm,
                            '--budget',str(budget),'--output',str(result_path)]
                        if sanitized:command.append('--sanitized')
                        row=dict(name=case['name'],fixture=case,input_sha256=digest(case),budget=budget,
                            limits={**protocol['limits'],'max_work':budget},arm=arm,sanitized=sanitized,repetition=repetition,
                            role='control' if controls else ('warmup' if repetition<protocol['warmup_rounds'] else 'observation'),
                            wall_start=datetime.datetime.now(datetime.timezone.utc).isoformat(),command=command,cell=stem)
                        row.update(run_command(command,output/'cells'/(stem+'.log'),protocol['worker_timeout_seconds']))
                        row.update(wall_end=datetime.datetime.now(datetime.timezone.utc).isoformat())
                        if row['execution']=='completed':row.update(json.loads(result_path.read_text()))
                        report['rows'].append(row);save()
                print('MINIMAL_MACAULAY_CELL',case['name'],budget,'ubsan' if sanitized else 'optimized',flush=True)
    report['status']='RECORDED_PENDING_AUDIT';save();print('PANEL_RECORDED',len(report['rows']),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--controls',action='store_true')
    a=p.parse_args();run(a.output,controls=a.controls)
