#!/usr/bin/env python3
"""Independent point and phase replay of the frozen K899/K900 screen."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
CRYPTO = Path(os.environ.get('N83_CRYPTO_REPO',
    '/Volumes/SSD990/llm/tmp/n83-packed-root-crypto-20261013'))
ARITHMETIC = CRYPTO / 'experiments/koblitz-single-target-n83-20261006/freeze_target.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()
            if line.strip() and line.lstrip().startswith('{')]


def pair(values):
    return tuple(map(int, values))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    protocol = json.loads((HERE / 'protocol.json').read_text())
    manifest = json.loads((HERE / 'binary_manifest.json').read_text())
    sidecar = json.loads((HERE / 'validation_sidecar.json').read_text())
    target = pair(json.loads((HERE / 'target.jsonl').read_text()))
    spec = importlib.util.spec_from_file_location('n83_arithmetic_replay', ARITHMETIC)
    arithmetic = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(arithmetic)
    checks = {
        'protocol_hash': sha(HERE / 'protocol.json') == manifest['protocol_sha256'],
        'target_hash': sha(HERE / 'target.jsonl') == protocol['target_sha256'] == manifest['target_sha256'],
        'sidecar_hash': sha(HERE / 'validation_sidecar.json') == protocol['validation_sidecar_sha256'],
        'arithmetic_hash': sha(ARITHMETIC) == sidecar['arithmetic_source_sha256'],
        'fixture_point': target == pair(sidecar['point']),
        'fixture_scalar_replay': arithmetic.scalar_mul(int(sidecar['scalar']), arithmetic.GENERATOR) == target,
        'target_curve_and_subgroup': arithmetic.on_curve(target) and arithmetic.scalar_mul(arithmetic.R, target) is None,
    }
    rho_ms = []
    rho_outcomes = []
    ic_ms = {}
    cold_s = {}
    bases = {}
    details = {}
    censored = []
    for name in protocol['arms']:
        arm = HERE / 'runs' / name
        execution = json.loads((arm / 'execution.json').read_text())
        started = json.loads((arm / 'started.json').read_text())
        checks[f'{name}_started'] = (started['arm'] == name
            and started['source_commit'] == protocol['source_commit']
            and started['binary_sha256'] == execution['binary_sha256']
            and started['target_sha256'] == execution['target_sha256']
            and started['timeout_seconds'] == protocol[
                'ic_process_cap_seconds' if name.startswith('K') else 'rho_process_cap_seconds']
            and started['rss_cap_bytes'] == protocol['sampled_rss_cap_bytes'])
        if name.startswith('K'):
            checks[f'{name}_packed_mode'] = started['environment_overrides'].get(
                'KIC_PACKED_ROOT_TABLE') == '1'
        checks[f'{name}_exit'] = execution['exit_code'] == 0 and execution['disposition'] == 'exit'
        checks[f'{name}_rss'] = execution['sampled_peak_rss_bytes'] <= protocol['sampled_rss_cap_bytes']
        checks[f'{name}_target_input_hash'] = execution['target_sha256'] == protocol['target_sha256']
        checks[f'{name}_binary'] = execution['binary_sha256'] == manifest['ic_sha256' if name.startswith('K') else 'rho_sha256']
        checks[f'{name}_raw_hashes'] = sha(arm / 'stdout.txt') == execution['stdout_sha256'] and sha(arm / 'stderr.txt') == execution['stderr_sha256']
        cold_s[name] = execution['process_wall_s']
        if name.startswith('rho'):
            result = json.loads((arm / 'rho.json').read_text())
            checks[f'{name}_output_hash'] = sha(arm / 'rho.json') == execution['output_sha256']
            checks[f'{name}_answer'] = (result['status'] == 'PASS_VERIFIED_PUBLIC_TARGET'
                and result['group_verified'] is True
                and pair(result['published_q']) == target
                and int(result['recovered_scalar']) == int(sidecar['scalar'])
                and result['validation_sidecar_opened'] is False)
            checks[f'{name}_phase_sum'] = abs(result['online_interval_ns'] - result['online_phase_sum_ns']) <= 1000000
            rho_ms.append(float(result['online_ms']))
            rho_outcomes.append(result['outcome'])
            details[name] = {'online_ms': float(result['online_ms']), 'process_wall_s': cold_s[name]}
            continue
        k = int(name[1:])
        if not checks[f'{name}_exit']:
            censored.append(name)
            output_path = arm / 'target.jsonl'
            checks[f'{name}_censored_output_hash'] = (
                output_path.exists() and sha(output_path) == execution.get('output_sha256'))
            details[name] = {'disposition': execution['disposition'],
                             'exit_code': execution['exit_code'],
                             'process_wall_s': cold_s[name],
                             'sampled_peak_rss_bytes': execution['sampled_peak_rss_bytes']}
            continue
        output = rows(arm / 'target.jsonl')
        summaries = [row for row in rows(arm / 'stdout.txt') if row.get('kind') == 'compact_orbit_dlp_summary']
        base = rows(arm / 'base.jsonl')
        checks[f'{name}_output_hash'] = (sha(arm / 'target.jsonl') == execution['output_sha256']
                                         and sha(arm / 'base.jsonl') == execution['base_sha256'])
        checks[f'{name}_one_row'] = len(output) == len(summaries) == len(base) == 1
        if not checks[f'{name}_one_row']:
            continue
        row, summary, base = output[0], summaries[0], base[0]
        points = base['factor_base_point_coordinates']
        checks[f'{name}_base_shape'] = (summary['orbit_columns'] == base['orbit_columns'] == k
             and summary['factor_base_points'] == base['factor_base_points'] == 166 * k
             and summary['base_hash'] == base['base_hash'] and len(points) == 166 * k)
        checks[f'{name}_rank'] = (summary['rank'] == k
             and summary['rank_relations'] >= k
             and summary['rank_attempts'] >= summary['rank_relations']
             and summary['targets'] == summary['targets_solved'] == 1 and summary['targets_failed'] == 0)
        checks[f'{name}_target_point'] = pair(row['published_q']) == pair(row['target']) == target
        checks[f'{name}_answer'] = (row['group_verified'] is True
             and int(row['recovered_scalar']) == int(sidecar['scalar'])
             and row.get('published_fixture_scalar') is None
             and arithmetic.scalar_mul(int(row['recovered_scalar']), arithmetic.GENERATOR) == target)
        indices = row['point_indices']
        acc = None
        for index in indices:
            acc = arithmetic.add(acc, pair(points[index]))
        checks[f'{name}_relation'] = len(indices) == 4 and acc == target
        phases = [row[field] for field in ('target_query_ms', 'target_pdp_ms',
             'target_relation_check_ms', 'target_descent_ms', 'target_recovery_check_ms')]
        checks[f'{name}_phase_sum'] = abs(sum(phases) - row['target_ms']) <= max(0.02, row['target_ms'] * 1e-8)
        ic_ms[name] = float(row['target_ms'])
        bases[name] = base
        details[name] = {'online_ms': ic_ms[name], 'process_wall_s': cold_s[name],
                         'rank_ms': summary['timing_ms']['rank_stage'],
                         'index_ms': summary['timing_ms']['index_build'],
                         'base_load_ms': summary['timing_ms']['base_load'],
                         'root_table_entries': summary['root_table_entries'],
                         'rank_attempts': summary['rank_attempts'],
                         'rank_relations': summary['rank_relations'],
                         'rank_failures': summary['rank_failures'],
                         'rank_rows_without_gain': summary['rank_rows_without_gain'],
                         'rank_probes_mean': summary['rank_probes_mean'],
                         'target_probes': row['probes'],
                         'producer_peak_rss_bytes': summary['peak_rss_bytes']}
    if 'K899' in bases:
        checks['repeated_k899_base'] = (
            sha(HERE / 'runs/K899/base.jsonl') == protocol['expected_repeated_k899_base_sha256'])
    if 'K899' in bases and 'K900' in bases:
        small, large = bases['K899'], bases['K900']
        checks['nested_representatives'] = (small['factor_base_representatives']
            == large['factor_base_representatives'][:899])
        checks['nested_point_coordinates'] = (small['factor_base_point_coordinates']
            == large['factor_base_point_coordinates'][:166 * 899])
        checks['nested_labels'] = (small['factor_base_point_labels']
            == large['factor_base_point_labels'][:166 * 899])
    if len(rho_outcomes) == 2:
        checks['rho_same_walk_charges'] = rho_outcomes[0] == rho_outcomes[1]
    complete = all(checks.values()) and len(ic_ms) == 2 and len(rho_ms) == 2
    valid_censored = (censored == ['K900'] and set(ic_ms) == {'K899'}
        and len(rho_ms) == 2
        and all(details[name]['disposition'] in ('rss_cap', 'time_cap') for name in censored)
        and all(value for key, value in checks.items()
                if not any(key == f'{name}_{suffix}' for name in censored
                           for suffix in ('exit', 'rss'))))
    status = 'PASS' if complete else 'CENSORED_CAP' if valid_censored else 'FAIL_OR_INCOMPLETE'
    receipt = {'status': status, 'checks': checks, 'censored_arms': censored,
               'details': details, 'claim_boundary': 'one frozen public target; shared Mac host; exploratory',
               'rho_online_ms': rho_ms,
               'ic_online_ms': ic_ms,
               'k899_over_k900_online_ratio': ic_ms['K899'] / ic_ms['K900'] if complete else None,
               'rho_mean_over_k900_online_ratio': sum(rho_ms) / (2 * ic_ms['K900']) if complete else None}
    if args.out:
        with args.out.open('x') as out:
            json.dump(receipt, out, indent=2, sort_keys=True)
            out.write('\n')
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if status == 'FAIL_OR_INCOMPLETE':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
