"""Replay certificates and timing analysis without loading archived binaries."""
import argparse
import json
from pathlib import Path
from common import HERE,P,ROOT,arms,digest,fixtures,identity,make_instance,plan,read,schedule,sha,verify_solution
from analyze import summarize,validate_measurement
from algebraic_certificate import verify

def bound_path(folder,name):
    if name=='experiments/pdp-scaling/sumpoly_cache.pkl':
        return folder/'native/resources/sumpoly_cache.pkl'
    parts=Path(name).parts
    if len(parts)>3 and parts[:2]==('experiments','groebner-perf-20260924') and parts[3]=='build':
        return folder/'native'/parts[2]/Path(*parts[4:])
    return ROOT/name
def audit(folder):
    preflight=read(folder/'preflight.json.gz');report=read(folder/'panel/report.json');analysis=read(folder/'analysis.json')
    assert preflight['status']=='PASS'
    assert preflight['plan_sha256']==report['plan_sha256']==sha(HERE/'measurement_plan.json')
    assert preflight['inputs']==fixtures() and report['schedule']==schedule()
    assert preflight['bindings']==report['bindings']
    assert report['preflight_sha256']==sha(folder/'preflight.json.gz')
    for name,wanted in preflight['bindings'].items():assert sha(bound_path(folder,name))==wanted,name
    cases={c['name']:c for c in fixtures()};seen=set();proofs=set();verified=0;identities={};solved=0
    frozen={(r['name'],r['variant'],r['sanitizer']):r['result'] for r in read(P/'round58/results/frozen-screen.json.gz')['rows']}
    for row in preflight['rows']:
        key=(row['name'],row['arm'],row['sanitizer']);assert key not in seen;seen.add(key)
        result=row['measurement']['result'];case=cases[row['name']]
        assert identity(result)==row['identity'];identities[key]=row['identity']
        validate_measurement(row['measurement'])
        old=frozen[key]
        for field in ('basis','proof','top_stats','column_stats'):assert old.get(field)==result.get(field),(key,field)
        counters=lambda value:{k:v for k,v in value['producer_stats'].items() if not k.endswith('_seconds')}
        assert counters(old)==counters(result)
        if result.get('verified'):
            payload=[case['nvars'],case['equations'],result['basis'],result['proof']]
            token=digest(payload)
            if token not in proofs:
                check=verify(*payload);assert check['verified'],(key,check);proofs.add(token)
            if case['boundary']=='pdp':
                instance=make_instance(case['n'],case['m'],case['ell'],seed=case['seed'])
                assert instance.xR==case['target_x'] and [sorted(p) for p in instance.equations()]==case['equations']
                assert instance.evaluate(result['assignment'])==0 and verify_solution(instance,result['assignment'])
                assert result['reference_equations_and_curve_replay'] and result['status']=='solved'
                solved+=1
            verified+=1
        else:assert result['status']=='inconclusive' and 'budget' in result['reason']
    grid={(c['name'],a,u) for c in cases.values() for a in arms(c) for u in (False,True)}
    assert seen==grid and len(seen)==92 and verified==40 and solved==20
    for name,arm,sanitizer in grid:assert identities[name,arm,False]==identities[name,arm,True]
    attempts=folder/'panel/attempts.jsonl'
    records=[json.loads(line) for line in attempts.read_text().splitlines()] if attempts.exists() else []
    for row in records:
        assert row['matches_preflight']==(identity(row['measurement']['result'])==identities[row['case'],row['arm'],False])
    replay=summarize(report,records,plan(),cases)
    replay.update(panel_sha256=sha(folder/'panel/report.json'),plan_sha256=report['plan_sha256'])
    assert replay==analysis
    return {'status':'PASS','rows':len(seen),'verified':verified,'inconclusive':len(seen)-verified,
            'complete_pdp_successes':solved,'unique_proofs':len(proofs),'bindings_checked':len(preflight['bindings']),
            'queries':len(records),'timing_analysis':replay,'candidate_id':None,'online_speedup':None}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=audit(args.evidence);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='timing_analysis'},indent=2))
if __name__=='__main__':main()
