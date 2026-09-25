"""Audit retained query receipts and recompute paired wall-time summaries.

This audit checks evidence integrity; it does not execute Metal or certify bases.
"""
import hashlib
import gzip
import json
import math
from pathlib import Path
import random
import statistics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def ratio(rows,numerator,denominator):
    logs = [math.log(r[numerator]['wall_ns']/r[denominator]['wall_ns']) for r in rows]
    rng = random.Random(2026092513)
    boot = sorted(math.exp(statistics.mean(rng.choices(logs,k=len(logs)))) for _ in range(4000))
    return {'paired_geomean':math.exp(statistics.mean(logs)),'bootstrap_95':[boot[99],boot[3899]]}


def main():
    inventory = json.loads((HERE/'results/inventory.json').read_text())
    for name,expected in inventory['sha256'].items():
        path = Path(name)
        assert not path.is_absolute() and '..' not in path.parts
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected,name
    report = json.loads(gzip.decompress((HERE/'results/query-comparison.json.gz').read_bytes()))
    for name,expected in report['source_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
    assert report['candidate_id'] is None and report['IC_online_ms'] is None and report['rho_online_ms'] is None
    assert report['status']=='PASS' and report['capacity']==8192
    assert report['arms']==['cpu','gpu-direct','gpu-indirect','evaluation']
    arms = report['arms']
    cells = []
    for fixture in report['inputs']:
        identity = {k:v for k,v in fixture.items() if k not in ('workload_sha256','fixture_ns')}
        assert hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()==fixture['workload_sha256']
        rows = [r for r in report['rows'] if r['workload_sha256']==fixture['workload_sha256']]
        assert len(rows)==report['repetitions']+1
        assert sorted(r['repetition'] for r in rows)==list(range(report['repetitions']+1))
        assert sum(r['warmup'] for r in rows)==1
        for row in rows:
            assert (row['nvars'],row['seed'])==(3*fixture['ell'],fixture['seed'])
            assert sorted(row['order'])==sorted(arms)
            assert all(row[a]['wall_ns']>0 and row[a]['result'].get('verified') for a in arms)
            assert len({row[a]['result']['basis_sha256'] for a in arms})==1
            assert len({row[a]['result']['assignment'] for a in arms})==1
        rows = [r for r in rows if not r['warmup']]
        cells.append({'nvars':3*fixture['ell'],'seed':fixture['seed'],'pairs':len(rows),
            'median_ms':{a:statistics.median(r[a]['wall_ns'] for r in rows)/1e6 for a in arms},
            'cpu_over_gpu_indirect':ratio(rows,'cpu','gpu-indirect'),
            'cpu_over_gpu_direct':ratio(rows,'cpu','gpu-direct'),
            'direct_over_indirect':ratio(rows,'gpu-direct','gpu-indirect'),
            'gpu_indirect_over_evaluation':ratio(rows,'gpu-indirect','evaluation')})
    validation = json.loads((HERE/'results/query-validation.json').read_text())
    assert validation['status']=='PASS' and validation['basis_checks']==345
    workspace = json.loads((HERE/'results/workspace-validation-final.json').read_text())
    assert workspace['status']=='PASS' and workspace['exact_rank_rref_checks']==942
    assert len(report['inputs'])==15 and len(report['rows'])==240
    print(json.dumps({'audit':'PASS','scope':'retained evidence only','cells':cells},indent=2))


if __name__=='__main__':
    main()
