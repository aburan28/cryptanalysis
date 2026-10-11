"""Replay portable evidence without executing downloaded native binaries."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from query import HERE,VARIANTS
from test_columns import trace
from algebraic_certificate import verify

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_text())
def audit(folder):
    assert read(folder/'validation.json')['status']=='PASS'
    receipt=read(folder/'native/round58/receipt.json')
    checked=0
    for group in ('sources','generated','binaries'):
        base=HERE.parent if group=='sources' else folder/'native/round58'
        for name,wanted in receipt[group].items():
            assert sha(base/name)==wanted,(group,name);checked+=1
    report=read(folder/'screen.json.gz')
    frozen=HERE.parent/'round56/results/frozen-screen.json.gz'
    assert report['status']=='PASS' and report['frozen_sha256']==sha(frozen)
    prior=read(frozen)
    assert report['inputs']==prior['inputs'] and report['limits']==prior['limits']
    baseline={r['name']:r['result'] for r in prior['rows'] if r['variant']=='chain_filter' and not r['sanitizer']}
    cases={c['name']:c for c in prior['inputs']}
    expected={(name,v,s) for name in cases for v in VARIANTS for s in (False,True)}
    seen=set();replayed=set();statuses={}
    for row in report['rows']:
        key=(row['name'],row['variant'],row['sanitizer'])
        assert key in expected and key not in seen;seen.add(key)
        answer=row['result'];assert trace(answer)==trace(baseline[row['name']]),key
        statuses[answer['status']]=statuses.get(answer['status'],0)+1
        if answer['verified'] and row['name'] not in replayed:
            case=cases[row['name']]
            result=verify(case['nvars'],case['equations'],answer['basis'],answer['proof'],
                          max_work=report['limits']['max_check_work'],
                          max_retained_terms=report['limits']['max_retained_terms'])
            assert result['verified'],key;replayed.add(row['name'])
    assert seen==expected
    assert report['independent_proof_replays']==len(replayed)
    # Bind the report's original absolute paths to the same archived binaries
    # and checked-out sources; never load a foreign-platform shared library.
    prefix='experiments/groebner-perf-20260924/'
    for name,wanted in report['bindings'].items():
        suffix=name.split(prefix,1)[1]
        if suffix.startswith('round58/build/'):
            path=folder/'native/round58'/suffix.removeprefix('round58/build/')
        else:path=HERE.parent/suffix
        assert sha(path)==wanted,name;checked+=1
    return {'status':'PASS','rows':len(seen),'statuses':statuses,'bindings_checked':checked,
            'independent_proof_replays':len(replayed),'screen_sha256':sha(folder/'screen.json.gz'),
            'timing_eligible':False,'candidate_id':None,'online_speedup':None}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    report=audit(args.evidence)
    args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
