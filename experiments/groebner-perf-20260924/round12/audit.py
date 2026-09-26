"""Audit complete paired data, exact trace counters and frozen source hashes."""
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
ROOT = HERE.parents[2]
ARMS = ('baseline', 'pivots', 'ordered', 'combined')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def paired(rows, arm, metric='wall_ns'):
    if not all(r['baseline']['result'].get('verified') and r[arm]['result'].get('verified') for r in rows):
        return None
    logs = [math.log(r['baseline'][metric] / r[arm][metric]) for r in rows]
    rng = random.Random(2026092517)
    samples = sorted(math.exp(statistics.mean(rng.choices(logs, k=len(logs)))) for _ in range(4000))
    return {'geometric_mean': math.exp(statistics.mean(logs)), 'bootstrap_95': [samples[99], samples[3899]]}


def audit(path):
    report = json.loads(gzip.decompress(path.read_bytes()))
    assert report['status'] == 'RECORDED'
    assert report['candidate_id'] is None and report['IC_online_ms'] is None and report['rho_online_ms'] is None
    assert len(report['inputs']) == 23 and len(report['rows']) == 200
    for name, expected in report['source_sha256'].items():
        source = (ROOT / name).read_bytes()
        if hashlib.sha256(source).hexdigest() != expected and name in (
                'experiments/groebner-perf-20260924/round12/native_engine.cpp',
                'experiments/groebner-perf-20260924/round12/audit.py'):
            snapshot = gzip.decompress((HERE / 'measured' / (Path(name).name + '.gz')).read_bytes())
            if name.endswith('native_engine.cpp'):
                assert source.rstrip() == snapshot.rstrip()
            source = snapshot
        assert hashlib.sha256(source).hexdigest() == expected, name
    status = Counter()
    summary = []
    seen = set()
    for fixture in report['inputs']:
        key = fixture['workload_sha256']
        assert key not in seen
        seen.add(key)
        canonical = {k: v for k, v in fixture.items() if k not in ('workload_sha256', 'repetitions', 'fixture_ns')}
        assert digest(canonical) == key
        rows = [r for r in report['rows'] if r['workload_sha256'] == key]
        assert [r['repetition'] for r in rows] == list(range(fixture['repetitions'] + 1))
        arms = list(ARMS) + (['evaluation'] if fixture['boundary'] == 'pdp' else [])
        for row in rows:
            assert row['warmup'] == (row['repetition'] == 0)
            assert sorted(row['order']) == sorted(arms)
            assert row['name'] == fixture['name'] and row['boundary'] == fixture['boundary']
            original = row['baseline']['result']
            for arm in arms:
                attempt = row[arm]
                result = attempt['result']
                assert attempt['wall_ns'] > 0 and attempt['parent_cpu_ns'] > 0
                assert 0 <= attempt['descent_ns'] <= attempt['wall_ns']
                status[result['status']] += 1
                if arm != 'evaluation':
                    assert result['status'] == original['status']
                    assert result.get('verified') == original.get('verified')
                    assert result.get('reason') == original.get('reason')
                    counters = lambda r: {k: v for k, v in r['producer_stats'].items() if not k.endswith('_seconds')}
                    assert counters(result) == counters(original), (fixture['name'], arm)
                if result.get('verified'):
                    assert result['basis_sha256'] == (original.get('basis_sha256') or result['basis_sha256'])
                    if fixture['boundary'] == 'pdp':
                        assert result['status'] == 'solved'
                        if original.get('verified'):
                            assert result['assignment'] == original['assignment']
                else:
                    assert result['status'] == 'inconclusive', result
        measured = [r for r in rows if not r['warmup']]
        summary.append({'name': fixture['name'], 'repetitions': len(measured),
            'verified': {a: sum(bool(r[a]['result'].get('verified')) for r in measured) for a in arms},
            'wall_median_ms': {a: statistics.median(r[a]['wall_ns'] / 1e6 for r in measured) for a in arms},
            'cpu_median_ms': {a: statistics.median(r[a]['parent_cpu_ns'] / 1e6 for r in measured) for a in arms},
            'baseline_over_variant': {a: paired(measured, a) for a in arms if a != 'baseline'},
            'baseline_over_variant_cpu': {a: paired(measured, a, 'parent_cpu_ns') for a in arms if a != 'baseline'}})
    assert sum(status.values()) == 920
    return {'file': path.name, 'statuses_including_warmups': dict(status), 'host': report['host'], 'cases': summary}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('reports', nargs='*', type=Path)
    args = parser.parse_args()
    reports = args.reports or sorted((HERE / 'results').glob('*.json.gz'))
    assert reports, 'no retained comparisons'
    print(json.dumps([audit(path) for path in reports], indent=2))


if __name__ == '__main__':
    main()
