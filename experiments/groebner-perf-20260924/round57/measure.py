"""Load-gated, paired complete-query timing with every failure and omission retained."""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import time
from common import HERE,Context,arm_order,arms,bindings,fixtures,host_identity,identity,plan,read,schedule,sha,verify_bindings

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--preflight',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    config=plan();preflight=read(args.preflight);bound=bindings()
    assert preflight['status']=='PASS' and preflight['plan_sha256']==sha(HERE/'measurement_plan.json')
    assert preflight['bindings']==bound and preflight['inputs']==fixtures()
    assert preflight['architecture']==platform.machine() and preflight['platform']==platform.platform()
    expected={(r['name'],r['arm']):r['identity'] for r in preflight['rows'] if not r['sanitizer']}
    cases={c['name']:c for c in fixtures()};tasks=schedule()
    out=args.output;out.mkdir(parents=True,exist_ok=False)
    threshold=os.cpu_count()*config['max_load_per_logical_cpu']
    report={'schema':'sparse-f4-complete-query-panel/1','status':'RUNNING','plan':config,'plan_sha256':sha(HERE/'measurement_plan.json'),
            'preflight_sha256':sha(args.preflight),'preflight_path':str(args.preflight.resolve()),'bindings':bound,'schedule':tasks,'trials':[],
            'host':host_identity()|{'load_threshold':threshold},
            'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'candidate_id':None,'online_speedup':None,
            'boundary':config['boundary'],'cache_policy':config['cache_policy'],'rows':0,'rejected_admissions':0,'unrun':[],
            'offline_python_replay_charged':False,'source_bindings_unchanged':False}
    def save():
        temporary=out/'report.tmp';temporary.write_text(json.dumps(report,indent=2)+'\n');temporary.replace(out/'report.json')
    save();context=None
    try:
        for index,task in enumerate(tasks):
            case=cases[task['case']];load=os.getloadavg()
            trial={**task,'admission_load':load,'admitted':load[0]<=threshold,'complete':False,'qualified':False,'pairs':[]}
            report['trials'].append(trial)
            if not trial['admitted']:
                report['rejected_admissions']+=1;trial['reason']='host load exceeds frozen threshold';save()
                if report['rejected_admissions']>=config['max_rejected_admissions']:
                    report['unrun']=tasks[index+1:];report['stop_reason']='rejected admission limit';break
                continue
            if context is None:
                start=time.perf_counter_ns();context=Context();report['reusable_setup_ns']=time.perf_counter_ns()-start
                # Fixture/layout setup is excluded, but cannot conceal a busy host.
                if os.getloadavg()[0]>threshold:
                    trial['reason']='host load rose during excluded setup';save();continue
            trial_good=True;fatal=False
            for repetition in range(config['warmups']+task['pairs']):
                order=arm_order(case,task['trial'],repetition)
                pair={'repetition':repetition,'warmup':repetition<config['warmups'],'order':order,'rows':[]}
                trial['pairs'].append(pair)
                for arm in order:
                    before=os.getloadavg();outer_start=time.perf_counter_ns()
                    try:
                        measurement=context.run(case['name'],arm)
                        matches=identity(measurement['result'])==expected[case['name'],arm]
                    except Exception as error:
                        measurement={'wall_ns':time.perf_counter_ns()-outer_start,'parent_cpu_ns':None,'phases':None,
                                     'result':{'status':'exception','verified':False,'detail':repr(error)}}
                        matches=False
                    after=os.getloadavg();result=measurement['result']
                    # Identity checks and evidence formatting are outside the query clock.
                    if 'basis' in result:
                        result['basis_sha256']=identity(result)['basis_sha256'];result.pop('basis')
                    record={'case':case['name'],'trial':task['trial'],'repetition':repetition,'warmup':pair['warmup'],'arm':arm,
                            'load_before':before,'load_after':after,'matches_preflight':matches,'measurement':measurement}
                    with (out/'attempts.jsonl').open('a') as log:log.write(json.dumps(record,separators=(',',':'))+'\n')
                    pair['rows'].append(report['rows']);report['rows']+=1
                    trial_good=trial_good and max(before[0],after[0])<=threshold and matches
                    fatal=fatal or not matches
                save()
                if not trial_good:break
            trial['complete']=len(trial['pairs'])==config['warmups']+task['pairs'] and all(len(p['rows'])==len(arms(case)) for p in trial['pairs'])
            trial['qualified']=trial_good and trial['complete']
            if fatal:
                report['unrun']=tasks[index+1:];report['stop_reason']='query differs from independent preflight';break
            if not trial_good:trial['reason']='load gate failed within trial'
            save();print('TRIAL',task['case'],task['trial'],'qualified',trial['qualified'],flush=True)
        verify_bindings(bound);report['source_bindings_unchanged']=True
        report['status']='RECORDED'
    except BaseException as error:
        report.update(status='INTERRUPTED',error=repr(error))
        seen={(t['case'],t['trial']) for t in report['trials']}
        report['unrun']=[t for t in tasks if (t['case'],t['trial']) not in seen]
        raise
    finally:
        if context is not None:context.close()
        report['ended_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
    print('PANEL_RECORDED',report['rows'],sum(t['qualified'] for t in report['trials']),flush=True)
if __name__=='__main__':main()
