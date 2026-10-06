"""Check exact historical inputs/sources and paired complete-query accounting."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

HERE = Path(__file__).resolve().parent
ARMS = ('python', 'native-dict', 'native-packed')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def paired(rows, arm, metric):
    if not all(r[a]['result'].get('verified') for r in rows for a in ('python',arm)):
        return None
    logs = [math.log(r['python'][metric]/r[arm][metric]) for r in rows]
    rng = random.Random(2026092602)
    boots = sorted(math.exp(statistics.mean(rng.choices(logs,k=len(logs)))) for _ in range(4000))
    return {'geometric_mean': math.exp(statistics.mean(logs)), 'bootstrap_95': [boots[99],boots[3899]]}


def audit(path):
    report = json.loads(gzip.decompress(path.read_bytes()))
    assert report['status']=='RECORDED' and tuple(report['arms'])==ARMS
    assert report['candidate_id'] is None and report['IC_online_ms'] is None and report['rho_online_ms'] is None
    assert report['repetitions']>=2
    assert report['source_snapshot'].keys()==report['source_sha256'].keys()
    for name,source in report['source_snapshot'].items():
        assert hashlib.sha256(source.encode()).hexdigest()==report['source_sha256'][name],name
    assert len(report['inputs'])==10
    assert len(report['rows'])==10*(report['repetitions']+1)
    seen=set(); counts=Counter(); cells=[]
    for fixture in report['inputs']:
        identity={k:v for k,v in fixture.items() if k not in ('workload_sha256','fixture_ns')}
        workload=fixture['workload_sha256']; assert digest(identity)==workload and workload not in seen
        seen.add(workload)
        rows=[r for r in report['rows'] if r['workload_sha256']==workload]
        assert [r['repetition'] for r in rows]==list(range(report['repetitions']+1))
        for row in rows:
            assert row['name']==fixture['name'] and row['warmup']==(row['repetition']==0)
            assert sorted(row['order'])==sorted(ARMS)
            answers=[]
            for arm in ARMS:
                attempt=row[arm]; result=attempt['result']; counts[result['status']]+=1
                assert attempt['wall_ns']>0 and attempt['cpu_ns']>0
                assert all(v>=0 for v in attempt['phases_ns'].values())
                assert sum(attempt['phases_ns'].values())==attempt['wall_ns']
                if result.get('verified'):
                    assert result['status']=='solved' and result['basis_certificate']['verified']
                    assert result['basis_certificate']['ideal_equality'] and result['basis_certificate']['reduced_groebner_basis']
                    answer=result['assignment']; value=0
                    for mask,coefficient in fixture['reference_anf']:
                        if mask&~answer==0: value^=coefficient
                    assert value==0
                    answers.append((result['basis_sha256'],answer))
                else:
                    assert result['status'] not in ('solved','gb')
            assert len(set(answers))<=1
        measured=[r for r in rows if not r['warmup']]
        cells.append({'name':fixture['name'], 'verified': {a:sum(bool(r[a]['result'].get('verified')) for r in measured) for a in ARMS},
            'median_wall_ms': {a:statistics.median(r[a]['wall_ns']/1e6 for r in measured) for a in ARMS},
            'median_cpu_ms': {a:statistics.median(r[a]['cpu_ns']/1e6 for r in measured) for a in ARMS},
            'median_descent_ms': {a:statistics.median(r[a]['phases_ns']['descent']/1e6 for r in measured) for a in ARMS},
            'wall_ratios': {a:paired(measured,a,'wall_ns') for a in ARMS[1:]},
            'cpu_ratios': {a:paired(measured,a,'cpu_ns') for a in ARMS[1:]}})
    return {'file':path.name, 'statuses_including_warmup':dict(counts), 'host':report['host'],
            'scope':report['scope'], 'cells':cells}


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('reports',nargs='*',type=Path); args=parser.parse_args()
    paths=args.reports or [HERE/'results'/name for name in
                          ('packed-view-screen.json.gz','screen.json.gz','confirmation.json.gz')]
    print(json.dumps([audit(path) for path in paths],indent=2))


if __name__=='__main__': main()
