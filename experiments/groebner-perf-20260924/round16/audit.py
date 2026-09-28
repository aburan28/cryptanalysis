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
ARMS = ('ordered', 'gpu')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def paired(rows, arm, metric):
    if not all(r[a]['result'].get('verified') for r in rows for a in ('ordered',arm)):
        return None
    logs = [math.log(r['ordered'][metric]/r[arm][metric]) for r in rows]
    rng = random.Random(2026092604)
    boots = sorted(math.exp(statistics.mean(rng.choices(logs,k=len(logs)))) for _ in range(4000))
    return {'geometric_mean': math.exp(statistics.mean(logs)), 'bootstrap_95': [boots[99],boots[3899]]}


def audit(path):
    report = json.loads(gzip.decompress(path.read_bytes()))
    ARMS=tuple(report['arms'])
    assert report['status']=='RECORDED' and ARMS in (('ordered','gpu'),('ordered','gpu','gpu-spin'))
    assert report['candidate_id'] is None and report['IC_online_ms'] is None and report['rho_online_ms'] is None
    assert report['repetitions']>=2
    assert report['source_snapshot'].keys()==report['source_sha256'].keys()
    for name,source in report['source_snapshot'].items():
        assert hashlib.sha256(source.encode()).hexdigest()==report['source_sha256'][name],name
    for name in ('gpu_certificate.mm','direct_truth.metal','gpu_query.py'):
        assert report['build_receipt']['source_sha256'][name]==report['source_sha256']['experiments/groebner-perf-20260924/round16/'+name]
    assert report['source_sha256']['experiments/groebner-perf-20260924/round15/reference/boolean_certificate.cpp']=='2f0a9df64e77edf2d24d3946b7e52cef8323c2a2c2bcc88726215941edd7d697'
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
                    semantic={k:v for k,v in result['basis_certificate'].items() if k not in ('backend','evaluation_counts','gpu_timing')}
                    answers.append((result['basis_sha256'],answer,json.dumps(semantic,sort_keys=True)))
                    suffix = '.dylib' if 'macOS' in report['host']['platform'] else '.so'
                    receipt=report['build_receipt'] if arm.startswith('gpu') else report['cpu_build_receipt']
                    name='gpu-certificate' if arm.startswith('gpu') else arm
                    assert result['verifier_binary_sha256']==receipt['binaries'][name+suffix]
                    if arm.startswith('gpu'):
                        assert result['basis_certificate']['gpu_timing']['calls']==1
                        assert result['basis_certificate']['evaluation_counts']['gather_words']==fixture['n']*3**max(fixture['nvars']-6,0)
                else:
                    assert result['status'] not in ('solved','gb')
            assert len(set(answers))<=1
        measured=[r for r in rows if not r['warmup']]
        cells.append({'name':fixture['name'], 'verified': {a:sum(bool(r[a]['result'].get('verified')) for r in measured) for a in ARMS},
            'median_wall_ms': {a:statistics.median(r[a]['wall_ns']/1e6 for r in measured) for a in ARMS},
            'median_cpu_ms': {a:statistics.median(r[a]['cpu_ns']/1e6 for r in measured) for a in ARMS},
            'median_certificate_ms': {a:statistics.median(r[a]['result'].get('verification_seconds',0)*1e3 for r in measured) for a in ARMS},
            'median_extraction_ms': {a:statistics.median(r[a]['result'].get('extraction_seconds',0)*1e3 for r in measured) for a in ARMS},
            'median_descent_ms': {a:statistics.median(r[a]['phases_ns']['descent']/1e6 for r in measured) for a in ARMS},
            'wall_ratios': {a:paired(measured,a,'wall_ns') for a in ARMS[1:]},
            'cpu_ratios': {a:paired(measured,a,'cpu_ns') for a in ARMS[1:]}})
    eligible=False
    if 'admission' in report:
        admission=report['admission'];limit=admission['logical_cpus']*admission['max_load_per_cpu']
        eligible=admission['admitted'] and bool(report['rows']) and all(row['load'][0]<=limit for row in report['rows']) and report['host']['load_end'][0]<=limit
        assert report['timing_qualification']['eligible']==eligible
    return {'file':path.name, 'timing_admission_eligible':eligible,
            'statuses_including_warmup':dict(counts), 'host':report['host'],
            'scope':report['scope'], 'cells':cells}


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('reports',nargs='*',type=Path); args=parser.parse_args()
    paths=args.reports or [HERE/'results'/'blocking-screen.json.gz']
    print(json.dumps([audit(path) for path in paths],indent=2))


if __name__=='__main__': main()
