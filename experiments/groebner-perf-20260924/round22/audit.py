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
from compare_query import Curve, GF2n, Point
from build import generated_sources
from journal import recover

PREFIX = 'experiments/groebner-perf-20260924/'
REQUIRED_SOURCES = tuple(PREFIX + name for name in (
    'round22/coefficient_gpu.mm', 'round22/coefficient_truth.metal', 'round22/build.py',
    'round22/coefficient_query.py', 'round22/compare_query.py', 'round22/benchmark.py', 'round22/audit.py',
    'round19/packed_gpu.mm', 'round19/tiled_truth.metal', 'round19/build.py', 'round19/gpu_query.py',
    'round18/packed_verifier.cpp', 'round18/packed_checker.py', 'round18/truth_query.py',
    'round18/build.py', 'round17/replay.c', 'round17/public_replay.py', 'round17/public_query.py',
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


def audit_report(report, path='<in-memory>'):
    assert report['schema'] == 'round22-coefficient-metal/1'
    assert report['status'] == 'RECORDED', 'incomplete reports remain evidence, not qualified comparisons'
    assert report['candidate_id'] is None and report['IC_online_ms'] is None and report['rho_online_ms'] is None
    assert tuple(report['arms']) == ARMS and report['candidates'] == {}
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
    assert set(receipts['18']['source_sha256']) == {
        PREFIX + 'round18/packed_verifier.cpp', PREFIX + 'round15/reference/boolean_certificate.cpp'}
    for name, expected in receipts['18']['source_sha256'].items():
        assert report['source_sha256'][name] == expected, name
    reference = report['source_snapshot'][PREFIX + 'round15/reference/boolean_certificate.cpp']
    helpers = reference.split('extern "C" int boolean_certificate(', 1)[0]
    checks = '        out->roots = alive;' + reference.split('        out->roots = alive;', 1)[1].split(
        '    } catch (const std::invalid_argument&)', 1)[0]
    assert receipts['18']['generated_sha256'] == {
        name: hashlib.sha256(source.encode()).hexdigest() for name, source in (
            ('certificate_helpers.inc', helpers), ('basis_checks.inc', checks))}
    expected_gpu_sources = {PREFIX + name for name in ('round19/packed_gpu.mm',
        'round19/tiled_truth.metal', 'round19/build.py', 'round18/packed_verifier.cpp',
        'round15/reference/boolean_certificate.cpp')}
    assert set(receipts['19']['source_sha256']) == expected_gpu_sources
    for name, expected in receipts['19']['source_sha256'].items():
        assert report['source_sha256'][name] == expected, name
    # Reproduce the old and new generated sources without executing snapshots.
    import importlib.util
    spec = importlib.util.spec_from_file_location('frozen_round19_build',Path(__file__).resolve().parent.parent/'round19/build.py')
    old_build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old_build)
    assert receipts['19']['generated_sha256'] == {name: hashlib.sha256(text.encode()).hexdigest()
        for name,text in old_build.generated_sources(report['source_snapshot']).items()}
    expected_coefficient_sources = {PREFIX+name for name in (
        'round22/coefficient_gpu.mm','round22/coefficient_truth.metal','round22/build.py',
        'round22/test_coefficients.mm','round18/packed_verifier.cpp','round15/reference/boolean_certificate.cpp')}
    assert set(receipts['22']['source_sha256']) == expected_coefficient_sources
    for name,expected in receipts['22']['source_sha256'].items():
        assert report['source_sha256'][name] == expected,name
    assert receipts['22']['generated_sha256'] == {name:hashlib.sha256(text.encode()).hexdigest()
        for name,text in generated_sources(report['source_snapshot']).items()}
    inputs = {}
    for item in report['inputs']:
        frozen = {k: v for k, v in item.items() if k not in ('fixture_ns', 'workload_sha256')}
        assert digest(frozen) == item['workload_sha256']
        assert item['name'] not in inputs
        inputs[item['name']] = item
    assert len(inputs) == 16
    groups, statuses = {}, Counter()
    for row in report['rows']:
        frozen = inputs[row['name']]
        assert row['workload_id'] == row['workload_sha256'] == frozen['workload_sha256']
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
                assert answer['query_arm'] == arm
                if frozen['n'] <= 63:
                    assert answer['replay_backend'] == 'native-public-point'
                    assert answer['replay_binary_sha256'] in receipts['17']['binaries'].values()
                else:
                    assert answer['replay_backend'] == 'python-public-point-wide-field-fallback'
                    assert answer['replay_binary_sha256'] is None
                verifier = '18' if arm == 'cpu' else '19' if arm == 'tiled' else '22'
                assert answer['equation_backend'] == 'independent-native-direct-packed'
                assert answer['equation_binary_sha256'] in receipts[verifier]['binaries'].values()
                assert answer['verifier_binary_sha256'] in receipts[verifier]['binaries'].values()
                expected = ('independent-packed-bitslice-zeta' if arm == 'cpu'
                            else 'independent-packed-metal-tiled-zeta' if arm=='tiled'
                            else 'independent-packed-metal-coefficient-zeta')
                cert = answer['basis_certificate']
                assert cert['backend'] == expected
                if arm != 'cpu':
                    assert answer['gpu_device']
                    stats = cert['gpu_timing']
                    assert stats['calls'] == 1 and stats['dispatches'] == (3 if arm.startswith('coeff') and frozen['nvars']>12 else 2) and stats['threads'] == 256
                    for name in ('prepare','encode','execute','extract','basis_check','total','spin'):
                        assert math.isfinite(stats[name]) and stats[name] >= 0
                    assert stats['device'] is None or (math.isfinite(stats['device']) and stats['device'] >= 0)
                    assert sum(stats[k] for k in ('prepare','encode','execute','extract','basis_check')) <= stats['total'] + 1e-6
                    assert stats['spin'] <= stats['execute'] + 1e-6
                    assert stats['total'] * 1e9 <= answer['phases_ns']['basis_and_certificate'] + 1000
                    assert stats['blocking_fallback'] in (0, 1)
                    if arm != 'coeff-poll': assert stats['spin'] == stats['polls'] == 0
                    assert stats['shared_buffer_bytes'] + (frozen['n'] if arm=='tiled' else 0) == cert['scratch_bytes']
                    assert stats['zeta_words'] == cert['evaluation_counts']['zeta_words']
                    assert stats['high_gather_words'] == cert['evaluation_counts']['high_gather_words']
                    if arm.startswith('coeff'):
                        assert cert['evaluation_counts']['word_bits'] == 32 and stats['high_gather_words'] == 0
                        assert stats['zeta_words'] == ((frozen['n']+31)//32)*(1<<frozen['nvars'])*frozen['nvars']//2
                else:
                    assert answer['gpu_device'] is None
                assert answer['descent_binary_sha256'] in receipts['14']['binaries'].values()
        if all(row[arm]['result'].get('verified') for arm in ARMS):
            left = row['cpu']['result']
            for arm in ARMS[1:]:
                right = row[arm]['result']
                for key in ('basis_sha256', 'assignment', 'curve_witness'):
                    assert left[key] == right[key], (row['name'], key, arm)
                ignored = ('backend', 'evaluation_counts', 'scratch_bytes', 'gpu_timing')
                assert {k:v for k,v in left['basis_certificate'].items() if k not in ignored} == {
                    k:v for k,v in right['basis_certificate'].items() if k not in ignored}
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
            summary['cpu_baseline_over_arm'] = {arm: ratio_interval([r['cpu']['cpu_ns']/r[arm]['cpu_ns'] for r in measured]) for arm in ARMS[1:]}
            summary['wall_baseline_over_arm'] = {arm: ratio_interval([r['cpu']['wall_ns']/r[arm]['wall_ns'] for r in measured]) for arm in ARMS[1:]}
            summary['phase_ns_median'] = {arm: {phase: statistics.median(r[arm]['result']['phases_ns'][phase] for r in measured)
                                              for phase in measured[0][arm]['result']['phases_ns']} for arm in ARMS}
            summary['gpu_phase_ms_median'] = {arm: {phase: statistics.median(
                r[arm]['result']['basis_certificate']['gpu_timing'][phase] for r in measured)*1000
                for phase in ('prepare','encode','execute','extract','basis_check','total','spin')}
                for arm in ARMS[1:]}
            summary['candidate_gpu_win'] = {arm: eligible and summary['wall_baseline_over_arm'][arm]['bootstrap95'][0] > 1
                                            for arm in ARMS[1:]}
        summaries.append(summary)
    assert set(groups) == set(inputs)
    return {'report': str(path), 'statuses': dict(statuses), 'controls': summaries,
            'timing_admission_eligible': eligible,
            'scope': 'Planted component controls only; load admission does not establish an exclusive host.'}


def audit(path):
    report = json.loads(gzip.decompress(Path(path).read_bytes()))
    restored,info = recover(str(path)+'.journal.gz')
    assert not info['truncated_tail'] and restored==report, 'journal and aggregate disagree'
    return audit_report(report,path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    print(json.dumps(audit(parser.parse_args().report), indent=2))
