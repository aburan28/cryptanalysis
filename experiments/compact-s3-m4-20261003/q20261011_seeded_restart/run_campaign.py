#!/usr/bin/env python3
"""Charge all attempts in a fixed-seed compact S3 one-target campaign."""

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = STAGE.parents[1]
sys.path.insert(0, str(STAGE / 'q20261010_final_link'))
from verify_model import verify  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inputs(n):
    prefix = Path('/private/tmp/q1430_n53_ordinary' if n == 53 else
                  '/private/tmp/q1430_ordinary')
    target = STAGE / 'q20261010_final_link' / f'n{n}_ordinary.targets'
    meta = json.loads(prefix.with_suffix('.json').read_text())
    manifest = json.loads(target.with_suffix('.targets.json').read_text())
    for key in ('curve_id', 'workload_id', 'factor_base_actual_B',
                'factor_base_folded_columns',
                'factor_base_enumerated_set_sha256'):
        assert meta[key] == manifest[key]
    assert meta['isogeny'] == 'none'
    assert sha(prefix.with_suffix('.cnf')) == meta['cnf_sha256']
    assert sha(target) == manifest['target_file_sha256']
    return prefix, target, meta


def operation_events(result):
    calls = result['field_api_calls']
    total = sum(calls.values())
    conversions = calls['fromCoords'] + calls['toCoords']
    assert total > 0 and conversions <= total
    return {'field_api_method_entry_events': total,
            'field_api_method_entry_log2': math.log2(total),
            'conversion_method_entry_events': conversions,
            'other_field_method_entry_events': total - conversions,
            'field_api_calls': calls}


def one_attempt(binary, n, seed, prefix, target, meta):
    cap = 500
    wall = 5 if n == 53 else 10
    early_limit = 8 if n == 53 else 25
    log = HERE / 'runs' / f'n{n}_seed{seed:02d}.log'
    command = [str(binary), str(prefix.with_suffix('.cnf')),
               str(prefix.with_suffix('.map')), str(target), str(STAGE),
               str(ROOT / 'ecc2k130/codegen'), 'seededpos', str(seed),
               'satpivot', 'selector', str(early_limit), 'eager',
               str(3 if n == 53 else 5), str(cap), str(wall)]
    started = time.monotonic()
    completed = subprocess.run(command, cwd=ROOT, capture_output=True,
                               text=True, timeout=wall + 30, check=False)
    process_seconds = time.monotonic() - started
    log.write_text(completed.stdout)
    if completed.stderr:
        log.with_suffix('.stderr.log').write_text(completed.stderr)
    assert completed.returncode in (0, 10, 20), completed.stderr
    result = json.loads(completed.stdout.splitlines()[0])
    assert result['decision_seed'] == seed
    assert result['status'] in (0, 10, 20)
    assert (len(result['early_state_samples']) +
            result['early_state_samples_truncated'] == result['early_queries'])
    row = {
        'degree': n, 'seed': seed, 'branch': 'seededpos',
        'early_limit': early_limit, 'leaf_mode': 'eager',
        'root_encoding': 'satpivot',
        'curve_id': meta['curve_id'], 'workload_id': meta['workload_id'],
        'isogeny': 'none',
        'factor_base_actual_B': meta['factor_base_actual_B'],
        'factor_base_folded_columns': meta['factor_base_folded_columns'],
        'factor_base_enumerated_set_sha256': meta[
            'factor_base_enumerated_set_sha256'],
        'cnf_sha256': meta['cnf_sha256'],
        'map_sha256': sha(prefix.with_suffix('.map')),
        'target_file_sha256': sha(target),
        'conflict_cap': cap, 'wall_cap_seconds': wall,
        'process_wall_seconds': process_seconds,
        'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
        'exit_code': completed.returncode, 'result': result,
        'status_label': ('ALGEBRAIC_MODEL' if result['status'] == 10 else
                         'UNSAT' if result['status'] == 20 else
                         'BOUNDED_UNKNOWN'),
        'field_api_events': operation_events(result),
        's3_verification': (verify(prefix.with_suffix('.json'), log)
                            if result['status'] == 10 else None),
        'group_relation_verification': None,
    }
    return row


def aggregate(n, rows):
    states = [(entry['row'], entry['x_bits'])
              for row in rows for entry in row['result']['early_state_samples']]
    truncated = sum(row['result']['early_state_samples_truncated']
                    for row in rows)
    api = sum(row['field_api_events']['field_api_method_entry_events']
              for row in rows)
    conversions = sum(row['field_api_events']['conversion_method_entry_events']
                      for row in rows)
    calls = {key: sum(row['field_api_events']['field_api_calls'][key]
                      for row in rows)
             for key in rows[0]['field_api_events']['field_api_calls']}
    return {
        'degree': n, 'target_count': 1, 'attempts': len(rows),
        'seeds': [row['seed'] for row in rows],
        'all_attempt_statuses': [row['status_label'] for row in rows],
        'total_conflicts': sum(row['result']['conflicts'] for row in rows),
        'total_pair_root_queries': sum(row['result']['root_queries']
                                       for row in rows),
        'total_early_target_states': sum(row['result']['early_queries']
                                         for row in rows),
        'distinct_recorded_early_states': len(set(states)),
        'early_state_samples_truncated': truncated,
        'total_leaf_rationality_checks': sum(
            row['result']['leaf_rationality_checks'] for row in rows),
        'total_nonrational_leaf_rejections': sum(
            row['result']['leaf_nonrational_rejections'] for row in rows),
        'total_final_link_checks': sum(row['result']['final_link_checks']
                                       for row in rows),
        'total_solver_cpu_seconds': sum(row['result']['cpu_seconds']
                                        for row in rows),
        'total_solver_wall_seconds': sum(row['result']['seconds']
                                         for row in rows),
        'total_process_wall_seconds': sum(row['process_wall_seconds']
                                          for row in rows),
        'total_field_api_method_entry_events': api,
        'total_field_api_method_entry_log2': math.log2(api),
        'total_conversion_method_entry_events': conversions,
        'total_field_api_calls': calls,
        'verified_group_relations': None,
        'cost_per_successful_decomposition_log2': None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    args = parser.parse_args()
    (HERE / 'runs').mkdir(exist_ok=True)
    receipt = {
        'proposal_id': 'Q1437', 'candidate_id': None, 'run_id': None,
        'claim_class': 'exploratory_one_target_pdp_campaign',
        'source_sha256': sha(HERE / 'insearch.cpp'),
        'binary_sha256': sha(args.binary),
        'build_script_sha256': sha(HERE / 'build.sh'),
        'counted_field_source_sha256': sha(
            STAGE / 'q20261011_operation_account/counted_onb.py'),
        'field_source_sha256': sha(ROOT / 'ecc2k130/codegen/field.py'),
        'input_law': 'fixed ordinary public point per field; seeds 0..15 '
                     'in order, fresh solver state per seed, no shared clauses',
        'operation_boundary': 'sum every counted Onb public method entry '
                              'during solver.solve for all sixteen seeds; '
                              'record process wall separately; input formula '
                              'construction and complete IC stages remain '
                              'outside this PDP stage total',
        'attempts': [], 'campaigns': [],
        'n131_total_work_log2': None, 'gap_to_2_pow_61_bits': None,
    }
    for n in (53, 83):
        prefix, target, meta = inputs(n)
        rows = []
        for seed in range(16):
            row = one_attempt(args.binary, n, seed, prefix, target, meta)
            rows.append(row)
            receipt['attempts'].append(row)
            print(json.dumps({'degree': n, 'seed': seed,
                              'status': row['status_label'],
                              'early_states': row['result']['early_queries'],
                              'api_events': row['field_api_events'][
                                  'field_api_method_entry_events']},
                             sort_keys=True), flush=True)
        receipt['campaigns'].append(aggregate(n, rows))
    (HERE / 'measurements.json').write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'campaigns': [
        {'degree': c['degree'], 'attempts': c['attempts'],
         'distinct_early_states': c['distinct_recorded_early_states'],
         'total_api_events': c['total_field_api_method_entry_events']}
        for c in receipt['campaigns']]}, sort_keys=True))


if __name__ == '__main__':
    main()
