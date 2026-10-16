#!/usr/bin/env python3
"""Independently audit a frozen Tier 1 joint-rho panel and its raw ledger."""
import argparse
from hashlib import sha256
import json
from math import exp, isfinite, log
from pathlib import Path
import random
import statistics
import tarfile

from check_secp256k1_tau_generator import G, N, add, mul
from make_tier1_rho_joint import expected_hashes

HERE = Path(__file__).resolve().parent
ORDER = ('cal_before', 'compare_demand', 'compare_graph',
         'compare_graph_planned', 'compare_root_first', 'compare_weighted',
         'compare_weighted_vs_root_first', 'compare_two_parent',
         'compare_two_parent_vs_root_first', 'compare_steiner',
         'compare_steiner_vs_two_parent', 'cal_mid', 'compare_fused',
         'compare_fused_graph', 'compare_fused_graph_planned', 'cal_after')
AA = ('cal_before', 'cal_mid', 'cal_after')
COMPARE = ('compare_demand', 'compare_graph', 'compare_graph_planned',
           'compare_root_first', 'compare_weighted',
           'compare_weighted_vs_root_first', 'compare_two_parent',
           'compare_two_parent_vs_root_first', 'compare_steiner',
           'compare_steiner_vs_two_parent',
           'compare_fused', 'compare_fused_graph', 'compare_fused_graph_planned')


def digest(data):
    return sha256(data).hexdigest()


def unit(pair, code):
    assert 0 <= code < 6
    a, b = pair
    for _ in range(code // 2):
        a, b = a + 3*b, -a - 2*b
    return (-a, -b) if code & 1 else (a, b)


def validate_plan_graph(graph):
    seen = set()
    for row in graph['nodes']:
        assert len(row) == 3
        seed = tuple(row[:2])
        assert len(seed) == 2 and all(isinstance(x, int) for x in seed)
        assert seed not in seen
        op = row[2]
        if op[0] == 'direct':
            assert len(op) == 1
        elif op[0] == 'step':
            assert len(op) == 7
            parent, parent_unit = tuple(op[1:3]), op[3]
            base, bit, step_unit = op[4:7]
            assert parent in seen and base in (0, 1) and 0 <= bit < 8
            power = ((1 << bit, 0) if base == 0 else (0, 1 << bit))
            p, q = unit(parent, parent_unit), unit(power, step_unit)
            assert seed == (p[0] + q[0], p[1] + q[1])
        elif op[0] == 'sum':
            assert len(op) == 7
            left, left_unit = tuple(op[1:3]), op[3]
            right, right_unit = tuple(op[4:6]), op[6]
            assert left in seen and right in seen
            p, q = unit(left, left_unit), unit(right, right_unit)
            assert seed == (p[0] + q[0], p[1] + q[1])
        else:
            raise AssertionError('unknown graph operation')
        seen.add(seed)
    assert len(seen) == len(graph['nodes'])
    return seen


def number(fields, key, *, positive=False):
    value = float(fields[key])
    assert isfinite(value) and (value > 0 if positive else value >= 0), key
    return value


def interval(ratios):
    assert len(ratios) == 16
    values = [log(x) for x in ratios]
    rng = random.Random(20261015)
    draws = sorted(exp(statistics.median(values[rng.randrange(16)] for _ in range(16)))
                   for _ in range(10000))
    return [draws[250], draws[9749]]


def audit(count, manifest_path, rules_path, raw_path):
    assert count in (1, 128)
    manifest = json.loads(manifest_path.read_bytes())
    rules = json.loads(rules_path.read_bytes())
    fixture_path = HERE / 'rho-restart-first128-fixture.json'
    fixture = json.loads(fixture_path.read_bytes())
    assert rules['expected_count'] == count
    assert rules['repetitions'] == manifest['repetitions'] == 16
    assert tuple(rules['case_order']) == ORDER
    assert tuple(case['id'] for case in manifest['cases']) == ORDER
    assert manifest['measurement_tier'] == rules['tier'] == 'tier1_instance'
    assert manifest['allocation']['instance_id'] == 'thyvmdqmzsz5ik'
    assert manifest['isolation']['execution_cpu'] == rules['execution_cpu'] == 40
    assert manifest['pair_fields'] == ['count', 'point']
    binary = rules['paths']['binary']
    fixture_remote = rules['paths']['fixture']
    forest = HERE.parent / 'joint-seed-spanning-forest-20261016'
    plans = {'plan': HERE / f'rho-joint-graph-plan-{count}.json',
             'root_first': forest / f'root-first-plan-{count}.json',
             'two_parent': forest / f'two-parent-plan-{count}.json',
             'steiner': forest / f'steiner-plan-{count}.json',
             'weighted': forest / f'weighted-plan-{count}.json'}
    plan_identity = None
    for stem, plan_path in plans.items():
        plan_bytes = plan_path.read_bytes()
        assert digest(plan_bytes) == rules['hashes'][f'{stem}_{count}']
        assert b'q_hex' not in plan_bytes
        frozen_plan = json.loads(plan_bytes)
        assert frozen_plan['schema'] == 1 and frozen_plan['count'] == count
        assert frozen_plan['b_hex'] == [row['b_hex'] for row in fixture['cases'][:count]]
        assert len(frozen_plan['choices']) == count
        assert all(len(row) == 23 for row in frozen_plan['choices'])
        graph = frozen_plan['graph']
        identity = (frozen_plan['choices'], graph['digit_ids'],
                    graph['terminal_ids'], validate_plan_graph(graph))
        if plan_identity is None:
            plan_identity = identity
        elif stem == 'steiner':
            assert identity[:3] == plan_identity[:3]
            assert plan_identity[3] <= identity[3]
            assert len(identity[3] - plan_identity[3]) <= 16
        else:
            assert identity == plan_identity, 'plan changed scalar choices or requested seeds'
    reference = [binary, '--pilot-rho-restart', 'openssl_nowarm', fixture_remote, str(count)]
    candidates = {
        'compare_demand': [binary, '--pilot-rho-restart-joint-demand', fixture_remote, str(count)],
        'compare_graph': [binary, '--pilot-rho-restart-joint-graph', fixture_remote, str(count)],
        'compare_graph_planned': [binary, '--pilot-rho-restart-joint-graph-planned', fixture_remote, str(count), rules['paths'][f'plan_{count}']],
        'compare_root_first': [binary, '--pilot-rho-restart-joint-graph-planned', fixture_remote, str(count), rules['paths'][f'root_first_{count}']],
        'compare_weighted': [binary, '--pilot-rho-restart-joint-graph-planned', fixture_remote, str(count), rules['paths'][f'weighted_{count}']],
        'compare_weighted_vs_root_first': [binary, '--pilot-rho-restart-joint-graph-planned', fixture_remote, str(count), rules['paths'][f'weighted_{count}']],
        'compare_two_parent': [binary, '--pilot-rho-restart-joint-graph-planned', fixture_remote, str(count), rules['paths'][f'two_parent_{count}']],
        'compare_two_parent_vs_root_first': [binary, '--pilot-rho-restart-joint-graph-planned', fixture_remote, str(count), rules['paths'][f'two_parent_{count}']],
        'compare_steiner': [binary, '--pilot-rho-restart-joint-graph-planned', fixture_remote, str(count), rules['paths'][f'steiner_{count}']],
        'compare_steiner_vs_two_parent': [binary, '--pilot-rho-restart-joint-graph-planned', fixture_remote, str(count), rules['paths'][f'steiner_{count}']],
        'compare_fused': [binary, '--pilot-rho-restart-joint-fused', fixture_remote, str(count)],
        'compare_fused_graph': [binary, '--pilot-rho-restart-joint-fused-graph', fixture_remote, str(count)],
        'compare_fused_graph_planned': [binary, '--pilot-rho-restart-joint-fused-graph-planned', fixture_remote, str(count), rules['paths'][f'plan_{count}']],
    }
    for case in manifest['cases']:
        expected_reference = (candidates['compare_root_first']
                              if case['id'] in ('compare_two_parent_vs_root_first',
                                                'compare_weighted_vs_root_first')
                              else candidates['compare_two_parent']
                              if case['id'] == 'compare_steiner_vs_two_parent'
                              else reference)
        assert case['reference'] == expected_reference
        assert case['candidate'] == candidates.get(case['id'], reference)
        assert case['expected_fields'] == {'count': str(count)}
        assert case['expected_result'] == rules['expected_point_hex']
    assert digest(fixture_path.read_bytes()) == rules['fixture_sha256'] == rules['hashes']['fixture']
    assert fixture['q_hex'] == rules['q_hex']
    q = tuple(int(x, 16) for x in fixture['q_hex'].split(':'))
    for row in fixture['cases'][:count]:
        a, b = int(row['a_hex'], 16) % N, int(row['b_hex'], 16) % N
        point = add(mul(a, G), mul(b, q))
        assert point is not None
        assert ':'.join(f'{x:064x}' for x in point) == row['point_hex']
    assert fixture['cases'][count - 1]['point_hex'] == rules['expected_point_hex']
    for key in ('joint', 'joint_windows', 'overlay'):
        name = {'joint': 'rho_restart_joint.rs',
                'joint_windows': 'joint_norm4033.rs',
                'overlay': 'native_rho_restart_joint_overlay.py'}[key]
        assert digest((HERE / name).read_bytes()) == rules['hashes'][key]
    assert rules['hashes'] == expected_hashes(rules['hashes']['binary'],
                                               rules['hashes']['libcrypto'])
    expected_artifacts = {str(manifest['allocation']['receipt']),
                          '/workspace/isolated-bench/panels/host-probe.json',
                          *rules['paths'].values(),
                          '/workspace/isolated-bench/panels/' + rules_path.name}
    assert len(manifest['artifacts']) == len(expected_artifacts)
    assert set(manifest['artifacts']) == expected_artifacts

    with tarfile.open(raw_path) as archive:
        names = archive.getnames()
        roots = {name.split('/')[0] for name in names}
        assert len(roots) == 1
        job = roots.pop()
        assert all(name == job or name.startswith(job + '/') for name in names)

        def read(name):
            member = archive.extractfile(job + '/' + name)
            assert member is not None, name
            return member.read()

        assert json.loads(read('manifest.json')) == manifest
        preflight = json.loads(read('preflight.json'))
        assert preflight['evidence']['measurement_tier'] == 'tier1_instance'
        assert preflight['evidence']['allocation']['instance_id'] == manifest['allocation']['instance_id']
        summary = json.loads(read('summary.json'))
        runs_bytes, pairs_bytes = read('runs.jsonl'), read('pairs.jsonl')
        runs = [json.loads(line) for line in runs_bytes.splitlines()]
        pairs = [json.loads(line) for line in pairs_bytes.splitlines()]
        expected_pairs = len(ORDER) * 16
        assert len(runs) <= expected_pairs * 2 and len(pairs) == expected_pairs
        assert summary['expected_pairs'] == expected_pairs
        assert summary['manifest_sha256'] == digest(read('manifest.json'))
        assert summary['measurement_tier'] == 'tier1_instance'
        artifacts = summary['artifact_sha256']
        assert artifacts['/workspace/isolated-bench/panels/' + rules_path.name] == digest(rules_path.read_bytes())
        for key, path in rules['paths'].items():
            assert artifacts[path] == rules['hashes'][key], key
        for path in (manifest['allocation']['receipt'],
                     '/workspace/isolated-bench/panels/host-probe.json'):
            assert path in artifacts
        cases = {case['id']: case for case in manifest['cases']}
        lookup, invalid, phases = {}, [], {}
        for serial, run in enumerate(runs, 1):
            assert run['serial'] == serial
            repeat, case_id, variant = run['repeat'], run['case'], run['variant']
            assert repeat in range(16) and case_id in ORDER
            assert variant in ('reference', 'candidate')
            assert run['command'] == cases[case_id][variant]
            assert run['binary_sha256'] == rules['hashes']['binary']
            assert run['measurement_tier'] == 'tier1_instance'
            assert run['postflight']['evidence']['measurement_tier'] == 'tier1_instance'
            assert run['postflight']['evidence']['allocation']['instance_id'] == manifest['allocation']['instance_id']
            assert 'tier1_observations' in run and 'counter_deltas' in run['tier1_observations']
            stderr = read(run['stderr_file'])
            stdout = read(run['stdout_file'])
            fields = dict(word.split('=', 1) for word in stdout.decode().split()
                          if '=' in word)
            assert fields == run['fields']
            mode = {'cal_before': 'openssl_nowarm', 'compare_demand': 'joint_demand',
                    'compare_graph': 'joint_graph', 'cal_mid': 'openssl_nowarm',
                    'compare_graph_planned': 'joint_graph_planned',
                    'compare_root_first': 'joint_graph_planned',
                    'compare_weighted': 'joint_graph_planned',
                    'compare_weighted_vs_root_first': 'joint_graph_planned',
                    'compare_two_parent': 'joint_graph_planned',
                    'compare_two_parent_vs_root_first': 'joint_graph_planned',
                    'compare_steiner': 'joint_graph_planned',
                    'compare_steiner_vs_two_parent': 'joint_graph_planned',
                    'compare_fused': 'joint_fused',
                    'compare_fused_graph': 'joint_fused_graph',
                    'compare_fused_graph_planned': 'joint_fused_graph_planned',
                    'cal_after': 'openssl_nowarm'}[case_id]
            if variant == 'reference':
                mode = ('joint_graph_planned' if case_id in
                        ('compare_two_parent_vs_root_first',
                         'compare_weighted_vs_root_first',
                         'compare_steiner_vs_two_parent') else 'openssl_nowarm')
            key = (repeat, case_id, variant)
            assert key not in lookup
            lookup[key] = run
            valid = (run['status'] == 'valid' and not run['issues'] and
                     run['returncode'] == 0 and not run['timed_out'] and
                     run['postflight']['ok'] and not stderr)
            if valid:
                assert fields['verified'] == '1' and fields['count'] == str(count)
                assert fields['point'] == rules['expected_point_hex']
                assert fields['mode'] == mode
                online = number(fields, 'online_ms', positive=True)
                assert abs(online - float(run['online_ms'])) < 0.000001
                if mode == 'openssl_nowarm':
                    assert number(fields, 'openssl_warmup_ms') == 0
                else:
                    prep = number(fields, 'target_preparation_ms')
                    evaluation = number(fields, 'restart_eval_ms')
                    assert abs(online - prep - evaluation) <= 0.00001
                    phase = phases.setdefault(case_id + ':' + variant, {'graph_plan_ms': [],
                        'plan_load_ms': [],
                        'target_preparation_ms': [], 'restart_eval_ms': []})
                    phase['graph_plan_ms'].append(number(fields, 'graph_plan_ms'))
                    phase['plan_load_ms'].append(number(fields, 'plan_load_ms'))
                    phase['target_preparation_ms'].append(prep)
                    phase['restart_eval_ms'].append(evaluation)
                    assert int(fields['constructed_q_points']) >= 0
                    if mode in ('joint_fused', 'joint_fused_graph',
                                'joint_fused_graph_planned'):
                        assert int(fields['fused_pair_sums']) >= 0
                    if mode in ('joint_graph', 'joint_fused_graph',
                                'joint_graph_planned', 'joint_fused_graph_planned'):
                        assert (int(fields['graph_edges']) + int(fields['direct_seeds']) ==
                                int(fields['constructed_q_points']))
                    if mode in ('joint_graph_planned', 'joint_fused_graph_planned'):
                        assert number(fields, 'graph_plan_ms') == 0
                        assert number(fields, 'plan_load_ms') >= 0
                        assert int(fields['plan_bytes']) > 0
            else:
                invalid.append({'serial': serial, 'status': run['status'],
                                'issues': run['issues'], 'stderr_sha256': digest(stderr)})
        pair_lookup = {}
        for position, pair in enumerate(pairs):
            assert pair['repeat'] == position // len(ORDER)
            assert pair['case'] == ORDER[position % len(ORDER)]
            key = (pair['repeat'], pair['case'])
            assert key not in pair_lookup
            pair_lookup[key] = pair
        assert len(pair_lookup) == expected_pairs
        aa_failures, comparisons = [], {case: [] for case in COMPARE}
        low, high = rules['aa_acceptance']
        observed_serials = []
        for repeat in range(16):
            for case_index, case_id in enumerate(ORDER):
                pair = pair_lookup[(repeat, case_id)]
                a = lookup.get((repeat, case_id, 'reference'))
                b = lookup.get((repeat, case_id, 'candidate'))
                expected_serials = {}
                if a is not None:
                    expected_serials['reference'] = a['serial']
                if b is not None:
                    expected_serials['candidate'] = b['serial']
                assert pair['run_serials'] == expected_serials
                first = ('reference' if (repeat + case_index) % 2 == 0 else 'candidate')
                second = 'candidate' if first == 'reference' else 'reference'
                observed_serials.extend(expected_serials[v] for v in (first, second)
                                        if v in expected_serials)
                ratio = None
                if a is not None and b is not None and 'online_ms' in a['fields'] and 'online_ms' in b['fields']:
                    ratio = float(a['fields']['online_ms']) / float(b['fields']['online_ms'])
                    assert isfinite(ratio) and ratio > 0
                if pair['status'] == 'valid' and ratio is not None:
                    assert abs(pair['speedup'] - ratio) < 0.000001
                if case_id in AA:
                    if (pair['status'] != 'valid' or pair['issues'] or ratio is None
                            or not low <= ratio <= high):
                        aa_failures.append({'repeat': repeat, 'case': case_id,
                                            'ratio': ratio, 'status': pair['status']})
                elif pair['status'] == 'valid' and not pair['issues'] and ratio is not None:
                    comparisons[case_id].append(ratio)
        assert observed_serials == list(range(1, len(runs) + 1))

    gate = (preflight['ok'] and summary['status'] == 'completed' and summary['artifacts_stable']
            and not invalid and not aa_failures)
    result = {}
    for case_id in COMPARE:
        ratios = comparisons[case_id]
        bounds = interval(ratios) if len(ratios) == 16 else None
        qualified = bool(gate and bounds and (bounds[0] > 1 or bounds[1] < 1))
        result[case_id] = {
            'valid_pairs': len(ratios),
            'descriptive_reference_over_candidate_median': statistics.median(ratios) if ratios else None,
            'paired_bootstrap95_by_repeat': bounds,
            'aggregate_status': 'qualified' if qualified else 'unknown_after_tier_gate',
            'qualified_ratio': statistics.median(ratios) if qualified else None,
        }
    return {
        'schema': 1, 'job_id': job, 'measurement_tier': 'tier1_instance',
        'frozen_restart_outputs_independently_replayed': count,
        'runner_status': summary['status'], 'artifacts_stable': summary['artifacts_stable'],
        'completed_arms': len(runs), 'completed_pairs': len(pairs),
        'invalid_arms': invalid, 'aa_failures': aa_failures,
        'tier_gate_passed': gate, 'comparison': result,
        'phase_ms_mean_by_arm': {arm: {name: statistics.mean(values)
            for name,values in group.items()} for arm,group in phases.items()},
        'raw_archive_sha256': digest(raw_path.read_bytes()),
        'manifest_sha256': digest(manifest_path.read_bytes()),
        'rules_sha256': digest(rules_path.read_bytes()),
        'runs_sha256': digest(runs_bytes), 'pairs_sha256': digest(pairs_bytes),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('count', type=int, choices=(1, 128))
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--rules', type=Path, required=True)
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    receipt = audit(args.count, args.manifest, args.rules, args.raw)
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
