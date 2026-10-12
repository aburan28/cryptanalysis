"""Audit a retained complete-query report and summarize paired wall costs."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

from benchmark import ARMS, digest, timing_eligible
from public_replay import Curve, GF2n, Point

PREFIX = 'experiments/groebner-perf-20260924/'
REQUIRED_SOURCES = tuple(PREFIX + name for name in (
    'round17/replay.c', 'round17/public_replay.py', 'round17/public_query.py',
    'round15/ordered_query.py', 'round15/ordered_certificate.cpp',
    'round15/reference/boolean_certificate.cpp', 'round15/reference/packed_certificate.cpp',
    'round14/contraction.cpp', 'round14/native_descent.py', 'round4/packed_query.py',
    'round4/descent_plan.py', 'round4/packed_dual.cpp', 'round2/boolean_dual.cpp')) + (
    'experiments/pdp-degree-heuristics/pdpkernel.c', 'experiments/pdp-scaling/descend.py',
    'experiments/pdp-scaling/gf2n.py', 'experiments/pdp-scaling/sumpoly.py')


def ratio_interval(ratios):
    logs = [math.log(value) for value in ratios]
    rng = random.Random(2026092703)
    values = sorted(math.exp(statistics.mean(rng.choices(logs, k=len(logs)))) for _ in range(2000))
    return {'paired_geomean': math.exp(statistics.mean(logs)),
            'bootstrap95': [values[49], values[1949]], 'pairs': len(logs)}


def audit(path):
    report = json.loads(gzip.decompress(Path(path).read_bytes()))
    assert report['status'] == 'RECORDED', 'incomplete reports remain evidence, not qualified comparisons'
    assert report['candidate_id'] is None and report['IC_online_ms'] is None and report['rho_online_ms'] is None
    assert tuple(report['arms']) == ARMS
    assert set(REQUIRED_SOURCES) <= set(report['source_snapshot'])
    assert set(report['source_snapshot']) == set(report['source_sha256'])
    for name, source in report['source_snapshot'].items():
        assert hashlib.sha256(source.encode()).hexdigest() == report['source_sha256'][name], name
    receipts = report['build_receipts']
    assert set(receipts['17']['source_sha256']) == {
        PREFIX + 'round17/replay.c', 'experiments/pdp-degree-heuristics/pdpkernel.c'}
    for name, expected in receipts['17']['source_sha256'].items():
        assert report['source_sha256'][name] == expected, name
    assert report['source_sha256'][PREFIX + 'round14/contraction.cpp'] == receipts['14']['source_sha256']
    assert report['source_sha256'][PREFIX + 'round15/ordered_certificate.cpp'] == receipts['15']['ordered_source_sha256']
    for name, expected in receipts['15']['reference_sha256'].items():
        assert report['source_sha256'][PREFIX + 'round15/reference/' + name] == expected
    inputs = {}
    for item in report['inputs']:
        frozen = {k: v for k, v in item.items() if k not in ('fixture_ns', 'workload_sha256')}
        assert digest(frozen) == item['workload_sha256']
        assert item['name'] not in inputs
        inputs[item['name']] = item
    assert len(inputs) == 10
    groups, statuses = {}, Counter()
    for row in report['rows']:
        frozen = inputs[row['name']]
        assert row['workload_sha256'] == frozen['workload_sha256']
        assert sorted(row['order']) == sorted(ARMS)
        assert row['warmup'] == (row['repetition'] == 0)
        group = groups.setdefault(row['name'], {})
        assert row['repetition'] not in group
        group[row['repetition']] = row
        curve = Curve(GF2n(frozen['n'], frozen['mod']), frozen['b'])
        target = Point(**frozen['target'])
        for arm in ARMS:
            sample, answer = row[arm], row[arm]['result']
            statuses[arm + ':' + answer['status']] += 1
            assert sample['wall_ns'] == sum(sample['phases_ns'].values())
            if answer.get('verified'):
                assert answer['status'] == 'solved' and answer['groebner_verified']
                assert answer['public_target'] == frozen['target']
                assert answer['complete_query_ns'] == sum(answer['phases_ns'].values())
                assert answer['complete_query_ns'] <= sample['phases_ns']['public_query']
                assignment = answer['assignment']
                assert 0 <= assignment < 1 << frozen['nvars']
                value = 0
                for mask, coefficient in frozen['reference_anf']:
                    if mask & ~assignment == 0: value ^= coefficient
                assert value == 0
                witness = answer['curve_witness']
                points = [Point(**p) for p in witness['points']]
                xs = [(assignment >> (i*frozen['ell'])) & ((1 << frozen['ell'])-1)
                      for i in range(frozen['m'])]
                assert witness['verified'] and witness['code'] == 0
                assert [p.x for p in points] == xs and all(curve.on_curve(p) for p in points)
                assert curve.sum(points) == target
                assert sample['outside_timing_witness_audit']['verified']
                if arm == 'python':
                    assert answer['replay_backend'] == 'python-public-point'
                    assert answer['replay_binary_sha256'] is None
                elif frozen['n'] <= 63:
                    assert answer['replay_backend'] == 'native-public-point'
                    assert answer['replay_binary_sha256'] in receipts['17']['binaries'].values()
                else:
                    assert answer['replay_backend'] == 'python-public-point-wide-field-fallback'
                    assert answer['replay_binary_sha256'] is None
                assert answer['descent_binary_sha256'] in receipts['14']['binaries'].values()
                assert answer['verifier_binary_sha256'] in receipts['15']['binaries'].values()
        if all(row[arm]['result'].get('verified') for arm in ARMS):
            left, right = (row[arm]['result'] for arm in ARMS)
            for key in ('basis_sha256', 'basis_certificate', 'assignment', 'curve_witness'):
                assert left[key] == right[key], (row['name'], key)
    assert report['admission']['timed_attempts'] == len(report['rows']) * len(ARMS)
    eligible = timing_eligible(report, report['host']['logical_cpus'], report['admission']['max_load_per_cpu'])
    assert eligible == report['timing_qualification']['eligible']
    summaries = []
    for name, rows in groups.items():
        assert set(rows) == set(range(report['repetitions'] + 1))
        verified = all(row[arm]['result'].get('verified') for row in rows.values() for arm in ARMS)
        summary = {'name': name, 'all_attempts_verified': verified, 'timing_admission_eligible': eligible}
        if verified:
            measured = [row for rep, row in rows.items() if rep]
            summary['wall_ms_median'] = {arm: statistics.median(r[arm]['wall_ns'] for r in measured)/1e6 for arm in ARMS}
            summary['cpu_python_over_native'] = ratio_interval([r['python']['cpu_ns']/r['native-or-python']['cpu_ns'] for r in measured])
            summary['wall_python_over_native'] = ratio_interval([r['python']['wall_ns']/r['native-or-python']['wall_ns'] for r in measured])
            summary['phase_ns_median'] = {arm: {phase: statistics.median(r[arm]['result']['phases_ns'][phase] for r in measured)
                                              for phase in measured[0][arm]['result']['phases_ns']} for arm in ARMS}
        summaries.append(summary)
    assert set(groups) == set(inputs)
    return {'report': str(path), 'statuses': dict(statuses), 'controls': summaries,
            'timing_admission_eligible': eligible,
            'scope': 'Planted component controls only; load admission does not establish an exclusive host.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    print(json.dumps(audit(parser.parse_args().report), indent=2))
