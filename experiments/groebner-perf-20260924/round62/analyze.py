"""Reuse paired statistics and require every exclusive query phase to be present."""
import argparse
import json
from pathlib import Path
import runpy
from common import HERE,P,arm_order,arms,fixtures,identity,plan,read,schedule,sha,verify_bindings

shared=runpy.run_path(str(P/'round57/analyze.py'))
assert shared['HERE']==HERE
PHASES={'descent_ns','algebra_and_certificate_ns','extraction_and_curve_ns','reference_replay_ns'}
def validate_measurement(measurement,matches=True):
    phases=measurement['phases']
    if phases is None:
        assert not matches and measurement['result']['status']=='exception'
        return
    assert set(phases)==PHASES
    assert all(type(v) is int and v>=0 for v in phases.values())
    assert sum(phases.values())==measurement['wall_ns']
    assert type(measurement['parent_cpu_ns']) is int and measurement['parent_cpu_ns']>=0
def summarize(report,records,config,cases):
    for row in records:validate_measurement(row['measurement'],row['matches_preflight'])
    return shared['summarize'](report,records,config,cases)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    report=read(args.input/'report.json');config=plan()
    assert report['plan_sha256']==sha(HERE/'measurement_plan.json') and report['schedule']==schedule()
    verify_bindings(report['bindings'])
    preflight=Path(report['preflight_path']);assert sha(preflight)==report['preflight_sha256']
    preflight_report=read(preflight)
    assert preflight_report['status']=='PASS' and preflight_report['bindings']==report['bindings']
    attempts=args.input/'attempts.jsonl'
    rows=[json.loads(line) for line in attempts.read_text().splitlines()] if attempts.exists() else []
    expected={(r['name'],r['arm']):r['identity'] for r in preflight_report['rows'] if not r['sanitizer']}
    for row in rows:assert row['matches_preflight']==(identity(row['measurement']['result'])==expected[row['case'],row['arm']])
    result=summarize(report,rows,config,{c['name']:c for c in fixtures()})
    result.update(panel_sha256=sha(args.input/'report.json'),plan_sha256=report['plan_sha256'])
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='trials'},indent=2))
if __name__=='__main__':main()
