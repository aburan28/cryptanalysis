#!/usr/bin/env python3
"""Matched coupled-middle runs with cumulative one-target accounting."""

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
Q1437 = STAGE / 'q20261011_seeded_restart'
Q1438 = STAGE / 'q20261011_deep_seeded_budget'
sys.path.insert(0, str(STAGE / 'q20261010_final_link'))
from verify_model import verify  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def state_set(rows):
    return {(sample['row'], sample['x_bits'])
            for row in rows
            for sample in row['result']['early_state_samples']}


def locked_control(binary, n, seed):
    prefix = Path('/private/tmp/q1430_n53_control' if n == 53 else
                  '/private/tmp/q1430_control')
    target = STAGE / 'q20261010_final_link' / f'n{n}_control.targets'
    log = HERE / 'runs' / f'n{n}_control_seed{seed:02d}.log'
    command = [str(binary), str(prefix.with_suffix('.cnf')),
               str(prefix.with_suffix('.map')), str(target), str(STAGE),
               str(ROOT / 'ecc2k130/codegen'), 'seededcoupled', str(seed),
               'satpivot', 'selector', '5', 'eager',
               str(3 if n == 53 else 5), '1000', '10']
    run = subprocess.run(command, cwd=ROOT, capture_output=True,
                         text=True, timeout=40, check=False)
    assert run.returncode == 10, run.stderr or run.stdout
    log.write_text(run.stdout)
    replay = verify(prefix.with_suffix('.json'), log)
    assert replay['status'] == 'verified_s3'
    result = json.loads(run.stdout.splitlines()[0])
    return {'degree': n, 'seed': seed, 'log': str(log.relative_to(HERE)),
            'log_sha256': sha(log), 'status': 'verified_s3',
            'coupled_middle_decisions': result['coupled_middle_decisions']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    args = parser.parse_args()
    screen = json.loads((Q1437 / 'measurements.json').read_text())
    prior = json.loads((Q1438 / 'measurements.json').read_text())
    assert sha(args.binary) != prior['binary_sha256']
    assert all(c['early_state_samples_truncated'] == 0
               for c in screen['campaigns'])
    assert all(c['deeper_state_samples_truncated'] == 0
               for c in prior['cumulative_campaigns'])
    receipt = {
        'proposal_id': 'Q1439', 'candidate_id': None, 'run_id': None,
        'claim_class': 'exploratory_one_target_pdp_policy_comparison',
        'q1437_measurement_sha256': sha(Q1437 / 'measurements.json'),
        'q1438_measurement_sha256': sha(Q1438 / 'measurements.json'),
        'runner_source_sha256': sha(HERE / 'run.py'),
        'source_sha256': sha(HERE / 'insearch.cpp'),
        'binary_sha256': sha(args.binary),
        'counted_field_source_sha256': sha(
            STAGE / 'q20261011_operation_account/counted_onb.py'),
        'input_law': 'same frozen ordinary public point at each degree; '
                     'one fresh coupled-middle process per point; '
                     'no shared clauses; Q1437 and Q1438 selection work '
                     'included in cumulative ledger',
        'schedule': [
            {'degree': 53, 'seed': 2, 'branch': 'seededcoupled'},
            {'degree': 83, 'seed': 8, 'branch': 'seededcoupled'},
        ],
        'controls': [], 'attempts': [], 'cumulative_campaigns': [],
        'n131_total_work_log2': None, 'gap_to_2_pow_61_bits': None,
    }
    (HERE / 'runs').mkdir(exist_ok=True)
    receipt['controls'] = [locked_control(args.binary, 53, 2),
                           locked_control(args.binary, 83, 8)]
    for spec in receipt['schedule']:
        n, seed, branch = (spec['degree'], spec['seed'], spec['branch'])
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
        log = HERE / 'runs' / f'n{n}_{branch}_seed{seed:02d}.log'
        command = [str(args.binary), str(prefix.with_suffix('.cnf')),
                   str(prefix.with_suffix('.map')), str(target), str(STAGE),
                   str(ROOT / 'ecc2k130/codegen'), branch, str(seed),
                   'satpivot', 'selector', '128', 'eager',
                   str(3 if n == 53 else 5), '5000', '30']
        started = time.monotonic()
        run = subprocess.run(command, cwd=ROOT, capture_output=True,
                             text=True, timeout=60, check=False)
        process_seconds = time.monotonic() - started
        assert run.returncode in (0, 10, 20), run.stderr
        log.write_text(run.stdout)
        if run.stderr:
            log.with_suffix('.stderr.log').write_text(run.stderr)
        result = json.loads(run.stdout.splitlines()[0])
        assert result['status'] == run.returncode
        assert result['decision_seed'] == seed
        assert len(result['early_state_samples']) + result[
            'early_state_samples_truncated'] == result['early_queries']
        events = sum(result['field_api_calls'].values())
        row = {
            **spec, 'curve_id': meta['curve_id'],
            'workload_id': meta['workload_id'], 'isogeny': 'none',
            'factor_base_actual_B': meta['factor_base_actual_B'],
            'factor_base_folded_columns': meta['factor_base_folded_columns'],
            'factor_base_enumerated_set_sha256': meta[
                'factor_base_enumerated_set_sha256'],
            'cnf_sha256': meta['cnf_sha256'],
            'map_sha256': sha(prefix.with_suffix('.map')),
            'target_file_sha256': sha(target),
            'early_limit': 128, 'conflict_cap': 5000,
            'wall_cap_seconds': 30,
            'process_wall_seconds': process_seconds,
            'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
            'exit_code': run.returncode, 'result': result,
            'status_label': ('ALGEBRAIC_MODEL' if result['status'] == 10 else
                             'UNSAT' if result['status'] == 20 else
                             'BOUNDED_UNKNOWN'),
            'field_api_method_entry_events': events,
            'field_api_method_entry_log2': math.log2(events),
            's3_verification': (verify(prefix.with_suffix('.json'), log)
                                if result['status'] == 10 else None),
            'group_relation_verification': None,
        }
        receipt['attempts'].append(row)
        print(json.dumps({'degree': n, 'branch': branch, 'seed': seed,
                          'status': row['status_label'],
                          'early_states': result['early_queries'],
                          'field_api_events': events}, sort_keys=True),
              flush=True)
    for n in (53, 83):
        old_rows = ([row for row in screen['attempts'] if row['degree'] == n] +
                    [row for row in prior['attempts'] if row['degree'] == n])
        new_rows = [row for row in receipt['attempts'] if row['degree'] == n]
        old_states, new_states = state_set(old_rows), state_set(new_rows)
        old_api = next(c['cumulative_api_events']
                       for c in prior['cumulative_campaigns'] if c['degree'] == n)
        new_api = sum(row['field_api_method_entry_events']
                      for row in new_rows)
        receipt['cumulative_campaigns'].append({
            'degree': n, 'target_count': 1, 'prior_attempts': 18,
            'coupled_attempts': 1, 'prior_api_events': old_api,
            'coupled_api_events': new_api,
            'cumulative_api_events': old_api + new_api,
            'cumulative_api_log2': math.log2(old_api + new_api),
            'prior_distinct_states': len(old_states),
            'coupled_distinct_states': len(new_states),
            'marginal_new_distinct_states': len(new_states - old_states),
            'cumulative_distinct_states': len(old_states | new_states),
            'coupled_state_samples_truncated': sum(
                row['result']['early_state_samples_truncated']
                for row in new_rows),
            'verified_group_relations': None,
            'cost_per_successful_decomposition_log2': None,
        })
    (HERE / 'measurements.json').write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'campaigns': receipt['cumulative_campaigns']},
                     sort_keys=True))


if __name__ == '__main__':
    main()
