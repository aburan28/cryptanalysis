#!/usr/bin/env python3
"""Independently replay the 256 public targets and paired finalist receipts."""

import argparse
import hashlib
import importlib.util
import json
import math
import os
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
CRYPTO = Path(os.environ.get('N83_CRYPTO_REPO',
    '/Volumes/SSD990/llm/tmp/n83-packed-root-crypto-20261013'))
ARITHMETIC = CRYPTO / 'experiments/koblitz-single-target-n83-20261006/freeze_target.py'
PRIOR_REPLAY = {
    800: 'n83-compact-orbit-size-sweep-20261012',
    899: 'n83-compact-orbit-k899-20261012',
    900: 'n83-packed-root-k900-20261013',
    1200: 'n83-packed-root-capacity-20261013',
    1271: 'n83-packed-root-capacity-20261013',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def pair(encoded):
    return tuple(map(int, encoded))


def check_and_summarize():
    protocol = json.loads((HERE / 'protocol.json').read_text())
    manifest = json.loads((HERE / 'binary_manifest.json').read_text())
    sidecar = json.loads((HERE / 'validation_sidecar.json').read_text())
    targets = [pair(row) for row in rows(HERE / 'targets.jsonl')]
    spec = importlib.util.spec_from_file_location('n83_panel_replay_arithmetic', ARITHMETIC)
    arithmetic = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(arithmetic)
    checks = {
        'protocol_hash': sha(HERE / 'protocol.json') == manifest['protocol_sha256'],
        'targets_hash': sha(HERE / 'targets.jsonl') == protocol['targets_sha256'] == manifest['targets_sha256'],
        'sidecar_hash': sha(HERE / 'validation_sidecar.json') == protocol['validation_sidecar_sha256'],
        'arithmetic_hash': sha(ARITHMETIC) == protocol['arithmetic_source_sha256'] == sidecar['arithmetic_source_sha256'],
        'target_count': len(targets) == len(sidecar['rows']) == protocol['target_count'],
        'target_distinct': len(set(targets)) == len(targets),
    }
    for index, (target, fixture) in enumerate(zip(targets, sidecar['rows'])):
        checks[f'fixture_{index}'] = (fixture['index'] == index
            and pair(fixture['point']) == target
            and arithmetic.on_curve(target)
            and arithmetic.scalar_mul(arithmetic.R, target) is None
            and arithmetic.scalar_mul(int(fixture['scalar']), arithmetic.GENERATOR) == target)
    details = {}
    complete = {}
    bases = {}
    censored = []
    for name in protocol['arms']:
        arm = HERE / 'runs' / name
        if not (arm / 'execution.json').exists():
            checks[f'{name}_execution_present'] = False
            continue
        started = json.loads((arm / 'started.json').read_text())
        execution = json.loads((arm / 'execution.json').read_text())
        checks[f'{name}_started'] = (started['arm'] == name
            and started['source_commit'] == protocol['source_commit']
            and started['binary_sha256'] == manifest['ic_sha256']
            and started['targets_sha256'] == protocol['targets_sha256']
            and started['timeout_seconds'] == protocol['ic_process_cap_seconds']
            and started['rss_cap_bytes'] == protocol['sampled_rss_cap_bytes']
            and started['environment_overrides']['KIC_PACKED_ROOT_TABLE'] == '1'
            and started['environment_overrides']['KIC_RANK_THREADS'] == str(protocol['rank_threads'])
            and started['environment_overrides']['KIC_TARGET_THREADS'] == str(protocol['target_threads']))
        checks[f'{name}_raw_hashes'] = (sha(arm / 'stdout.txt') == execution['stdout_sha256']
            and sha(arm / 'stderr.txt') == execution['stderr_sha256'])
        checks[f'{name}_resource_receipt'] = (
            execution['sampled_peak_rss_bytes'] <= protocol['sampled_rss_cap_bytes']
            or execution['disposition'] == 'rss_cap')
        for label in ('targets', 'base'):
            path = arm / f'{label}.jsonl'
            if path.exists():
                checks[f'{name}_{label}_hash'] = sha(path) == execution[f'{label}_output_sha256']
        details[name] = {'disposition': execution['disposition'],
                         'exit_code': execution['exit_code'],
                         'process_wall_s': execution['process_wall_s'],
                         'sampled_peak_rss_bytes': execution['sampled_peak_rss_bytes']}
        if execution['disposition'] != 'exit' or execution['exit_code'] != 0:
            censored.append(name)
            continue
        target_rows = rows(arm / 'targets.jsonl')
        summaries = [row for row in rows(arm / 'stdout.txt')
                     if row.get('kind') == 'compact_orbit_dlp_summary']
        base_rows = rows(arm / 'base.jsonl')
        checks[f'{name}_row_counts'] = (len(target_rows) == protocol['target_count']
                                       and len(summaries) == len(base_rows) == 1)
        if not checks[f'{name}_row_counts']:
            continue
        k = int(name[1:])
        summary, base = summaries[0], base_rows[0]
        points = base['factor_base_point_coordinates']
        checks[f'{name}_base_shape'] = (
            summary['orbit_columns'] == base['orbit_columns'] == k
            and summary['factor_base_points'] == base['factor_base_points'] == 166 * k
            and len(base['factor_base_representatives']) == k
            and len(points) == len(base['factor_base_point_labels']) == 166 * k
            and summary['base_hash'] == base['base_hash'])
        checks[f'{name}_rank'] = (summary['rank'] == k
            and summary['rank_relations'] >= k
            and summary['rank_attempts'] >= summary['rank_relations']
            and summary['targets'] == summary['targets_solved'] == protocol['target_count']
            and summary['targets_failed'] == 0)
        checks[f'{name}_layout'] = (summary['root_table_layout'] == 'packed_u128'
            and summary['root_table_slot_bytes'] == 16
            and summary['root_table_allocated_bytes'] <= 8 * (1 << 30))
        if k in PRIOR_REPLAY:
            prior_dir = HERE.parent / PRIOR_REPLAY[k]
            prior_receipt = json.loads((prior_dir / 'full_base_replay.json').read_text())
            prior_matches = [entry for entry in prior_receipt['records'] if entry['K'] == k]
            checks[f'{name}_prior_base_replay'] = (
                prior_receipt['status'] == 'PASS'
                and len(prior_matches) == 1
                and prior_matches[0]['base_sha256'] == sha(arm / 'base.jsonl')
                and sha(prior_dir / 'runs' / name / 'base.jsonl') == sha(arm / 'base.jsonl'))
        else:
            replay_path = HERE / 'full_base_replay.json'
            replay = json.loads(replay_path.read_text()) if replay_path.exists() else {}
            matches = [entry for entry in replay.get('records', []) if entry['K'] == k]
            checks[f'{name}_new_base_replay'] = (
                replay.get('status') == 'PASS' and len(matches) == 1
                and matches[0]['base_sha256'] == sha(arm / 'base.jsonl')
                and matches[0]['point_and_label_rows_checked'] == 166 * k)
        online = []
        probes = []
        for index, (row, target, fixture) in enumerate(zip(target_rows, targets, sidecar['rows'])):
            checks[f'{name}_target_{index}'] = (
                row['fixture_index'] == index
                and pair(row['published_q']) == pair(row['target']) == target
                and row['published_fixture_scalar'] is None
                and row['group_verified'] is True
                and int(row['recovered_scalar']) == int(fixture['scalar'])
                and arithmetic.scalar_mul(int(row['recovered_scalar']), arithmetic.GENERATOR) == target)
            indices = row['point_indices']
            acc = None
            if indices is not None and len(indices) == 4 and all(0 <= i < len(points) for i in indices):
                for point_index in indices:
                    acc = arithmetic.add(acc, pair(points[point_index]))
            checks[f'{name}_relation_{index}'] = acc == target
            phases = [row[field] for field in ('target_query_ms', 'target_pdp_ms',
                'target_relation_check_ms', 'target_descent_ms', 'target_recovery_check_ms')]
            checks[f'{name}_phase_{index}'] = (all(math.isfinite(x) and x >= 0 for x in phases)
                and abs(sum(phases) - row['target_ms']) <= max(0.02, row['target_ms'] * 1e-8))
            checks[f'{name}_probes_{index}'] = isinstance(row['probes'], int) and row['probes'] >= 0
            online.append(float(row['target_ms']))
            probes.append(row['probes'])
        complete[name] = {'online_ms': online, 'probes': probes}
        bases[name] = base
        details[name].update({'actual_usable_points': 166 * k,
            'effective_columns': k, 'base_sha256': sha(arm / 'base.jsonl'),
            'root_table_entries': summary['root_table_entries'],
            'root_table_allocated_bytes': summary['root_table_allocated_bytes'],
            'index_ms': summary['timing_ms']['index_build'],
            'rank_ms': summary['timing_ms']['rank_stage'],
            'target_median_probes': statistics.median(probes),
            'target_mean_probes': statistics.mean(probes),
            'target_max_probes': max(probes),
            'target_median_online_ms': statistics.median(online),
            'target_mean_online_ms': statistics.mean(online),
            'target_max_online_ms': max(online)})
    ordered = sorted(bases, key=lambda name: int(name[1:]))
    for smaller, larger in zip(ordered, ordered[1:]):
        small, large = bases[smaller], bases[larger]
        n = int(smaller[1:])
        checks[f'nested_{smaller}_{larger}'] = (
            small['factor_base_representatives'] == large['factor_base_representatives'][:n]
            and small['factor_base_point_coordinates'] == large['factor_base_point_coordinates'][:166 * n]
            and small['factor_base_point_labels'] == large['factor_base_point_labels'][:166 * n])
    if len(complete) == len(protocol['arms']) and all(checks.values()):
        status = 'PASS'
    elif (censored
          and all(details[name]['disposition'] in ('rss_cap', 'time_cap') for name in censored)
          and len(complete) + len(censored) == len(protocol['arms'])
          and all(checks[key] for key in checks if not key.endswith('_resource_receipt'))):
        status = 'CENSORED'
    else:
        status = 'FAIL_OR_INCOMPLETE'
    return {'status': status, 'checks': checks, 'details': details,
            'censored_arms': censored, 'complete_arm_count': len(complete),
            'claim_boundary': 'secondary 256-point shared-preparation finalist panel on shared Mac CPU; CPU online timing exploratory',
            'per_target': complete}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    receipt = check_and_summarize()
    if args.out:
        with args.out.open('x') as out:
            json.dump(receipt, out, indent=2, sort_keys=True)
            out.write('\n')
    print(json.dumps({'status': receipt['status'],
                      'complete_arm_count': receipt['complete_arm_count'],
                      'censored_arms': receipt['censored_arms'],
                      'failing_checks': [key for key, valid in receipt['checks'].items() if not valid],
                      'details': receipt['details']}, indent=2, sort_keys=True))
    if receipt['status'] == 'FAIL_OR_INCOMPLETE':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
