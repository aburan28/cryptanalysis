"""Paired wall-time summaries; incomplete, failed or unqualified cells cannot win."""
import argparse
import json
from pathlib import Path
import random
import statistics
from common import HERE,arm_order,arms,fixtures,identity,plan,read,schedule,sha,verify_bindings

def interval(ratios,seed,samples):
    if not ratios:return None
    rng=random.Random(seed);n=len(ratios)
    boot=sorted(statistics.median(rng.choices(ratios,k=n)) for _ in range(samples))
    return {'median_ratio':statistics.median(ratios),'paired_ratios':ratios,
            'bootstrap_95_low':boot[int(.025*(samples-1))],'bootstrap_95_high':boot[int(.975*(samples-1))]}
def summarize(report,records,config,cases):
    assert report['schema']=='sparse-f4-complete-query-panel/1'
    assert report['status'] in ('RECORDED','INTERRUPTED')
    assert report['plan']==config and report['candidate_id'] is None and report['online_speedup'] is None
    assert len(records)==report['rows']
    table={};used=set();summaries=[]
    threshold=report['host']['logical_cpus']*config['max_load_per_logical_cpu']
    assert report['host']['load_threshold']==threshold
    for trial in report['trials']:
        key=(trial['case'],trial['trial']);assert key not in table;table[key]=trial
        case=cases[trial['case']];samples={a:[] for a in arms(case)};paired={a:[] for a in arms(case) if a!=config['primary']}
        computed_good=trial['admitted'] and trial['admission_load'][0]<=threshold
        assert [p['repetition'] for p in trial['pairs']]==list(range(len(trial['pairs'])))
        for pair in trial['pairs']:
            assert pair['warmup']==(pair['repetition']<config['warmups'])
            assert pair['order']==arm_order(case,trial['trial'],pair['repetition'])
            rowmap={}
            for index in pair['rows']:
                assert index not in used and 0<=index<len(records);used.add(index)
                row=records[index];arm=row['arm'];assert arm not in rowmap;rowmap[arm]=row
                assert (row['case'],row['trial'],row['repetition'],row['warmup'])==(trial['case'],trial['trial'],pair['repetition'],pair['warmup'])
                m=row['measurement'];assert type(m['wall_ns']) is int and m['wall_ns']>0
                if m['phases'] is not None:assert all(v>=0 for v in m['phases'].values()) and sum(m['phases'].values())==m['wall_ns']
                computed_good=computed_good and row['matches_preflight'] and max(row['load_before'][0],row['load_after'][0])<=threshold
                if not pair['warmup']:samples[arm].append(row)
            assert list(rowmap)==pair['order'][:len(rowmap)]
            if not pair['warmup'] and len(rowmap)==len(pair['order']):
                primary=rowmap[config['primary']]['measurement']
                for arm in paired:
                    other=rowmap[arm]['measurement']
                    if primary['result'].get('verified') and other['result'].get('verified'):
                        paired[arm].append(other['wall_ns']/primary['wall_ns'])
        # The schedule's pair count is retained separately from observed pairs.
        wanted=next(t for t in report['schedule'] if (t['case'],t['trial'])==key)['pairs']
        complete=len(trial['pairs'])==config['warmups']+wanted and all(len(p['rows'])==len(arms(case)) for p in trial['pairs'])
        if report['status']=='RECORDED':assert trial['complete']==complete
        else:assert not trial['complete'] or complete
        qualified=computed_good and complete and trial['qualified']
        if report['status']=='RECORDED':assert trial['qualified']==(computed_good and complete)
        else:assert not trial['qualified'] or qualified
        ratios={}
        for arm,values in paired.items():
            ratios[arm]=interval(values,config['bootstrap_seed']+len(summaries),config['bootstrap_samples']) if qualified and len(values)==wanted else None
        summary={'case':key[0],'trial':key[1],'qualified':qualified,'arms':{},'comparator_over_primary':ratios}
        for arm,rows in samples.items():
            statuses={}
            for r in rows:
                status=r['measurement']['result']['status'];statuses[status]=statuses.get(status,0)+1
            summary['arms'][arm]={'attempts':len(rows),'statuses':statuses,
                'wall_median_ms':statistics.median(r['measurement']['wall_ns'] for r in rows)/1e6 if qualified and rows else None,
                'wall_samples_ns':[r['measurement']['wall_ns'] for r in rows]}
        summaries.append(summary)
    assert used==set(range(len(records)))
    declared={(t['case'],t['trial']) for t in report['schedule']}
    omitted={(t['case'],t['trial']) for t in report['unrun']}
    assert not(set(table)&omitted) and set(table)|omitted==declared
    accepted=report['status']=='RECORDED' and report['source_bindings_unchanged']
    two_times=accepted
    bykey={(s['case'],s['trial']):s for s in summaries}
    for case in config['primary_cases']:
        for trial in range(config['primary_trials']):
            row=bykey.get((case,trial))
            for arm in config['confirmatory_comparators']:
                value=row['comparator_over_primary'].get(arm) if row and row['qualified'] else None
                accepted=accepted and value is not None and value['bootstrap_95_low']>1
                two_times=two_times and value is not None and value['bootstrap_95_low']>=2
    return {'status':'PASS','primary_acceptance':bool(accepted),'two_times_target_met':bool(two_times),
            'queries':len(records),'qualified_trials':sum(s['qualified'] for s in summaries),'rejected_admissions':report['rejected_admissions'],
            'unrun_trials':len(omitted),'trials':summaries,'candidate_id':None,'online_speedup':None}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
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
    result['panel_sha256']=sha(args.input/'report.json');result['plan_sha256']=report['plan_sha256']
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='trials'},indent=2))
if __name__=='__main__':main()
