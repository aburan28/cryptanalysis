#!/usr/bin/env python3
"""Screen alternate decision seeds at a fixed field API-entry budget."""

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
Q1443 = STAGE / 'q20261011_api_budget_stop'
sys.path.insert(0, str(STAGE / 'q20261010_final_link'))
from verify_model import verify  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inputs(n, mode):
    prefix = Path('/private/tmp/q1430_n53_' + mode if n == 53 else
                  '/private/tmp/q1430_' + mode)
    target = STAGE / 'q20261010_final_link' / f'n{n}_{mode}.targets'
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


def run_one(binary, n, mode, seed, early_limit, budget, conflict_cap,
            wall_cap):
    prefix, target, meta = inputs(n, mode)
    label = f'n{n}_{mode}_seed{seed:02d}_early{early_limit}_api{budget}'
    log = HERE / 'runs' / f'{label}.log'
    command = [str(binary), str(prefix.with_suffix('.cnf')),
               str(prefix.with_suffix('.map')), str(target), str(STAGE),
               str(ROOT / 'ecc2k130/codegen'), 'seededpos', str(seed),
               'satpivot', 'selector', str(early_limit), 'eager',
               str(3 if n == 53 else 5), str(conflict_cap), str(wall_cap),
               str(budget)]
    started = time.monotonic()
    run = subprocess.run(command, cwd=ROOT, capture_output=True,
                         text=True, timeout=wall_cap + 30, check=False)
    process_seconds = time.monotonic() - started
    assert run.returncode in (0, 10, 20), run.stderr
    log.write_text(run.stdout)
    if run.stderr:
        log.with_suffix('.stderr.log').write_text(run.stderr)
    result = json.loads(run.stdout.splitlines()[0])
    assert result['status'] == run.returncode
    assert result['decision_seed'] == seed
    assert result['api_budget'] == budget
    assert len(result['early_state_samples']) + result[
        'early_state_samples_truncated'] == result['early_queries']
    events = sum(result['field_api_calls'].values())
    return {
        'degree': n, 'mode': mode, 'seed': seed, 'branch': 'seededpos',
        'early_limit': early_limit, 'curve_id': meta['curve_id'],
        'workload_id': meta['workload_id'], 'isogeny': 'none',
        'factor_base_actual_B': meta['factor_base_actual_B'],
        'factor_base_folded_columns': meta['factor_base_folded_columns'],
        'factor_base_enumerated_set_sha256': meta[
            'factor_base_enumerated_set_sha256'],
        'cnf_sha256': meta['cnf_sha256'],
        'map_sha256': sha(prefix.with_suffix('.map')),
        'target_file_sha256': sha(target),
        'api_budget': budget, 'conflict_cap': conflict_cap,
        'wall_cap_seconds': wall_cap,
        'process_wall_seconds': process_seconds,
        'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
        'exit_code': run.returncode, 'result': result,
        'status_label': ('ALGEBRAIC_MODEL' if result['status'] == 10 else
                         'UNSAT' if result['status'] == 20 else
                         'BOUNDED_UNKNOWN'),
        'field_api_method_entry_events': events,
        'field_api_method_entry_log2': math.log2(events),
        'api_budget_overshoot': max(0, events - budget) if budget else None,
        's3_verification': (verify(prefix.with_suffix('.json'), log)
                            if result['status'] == 10 else None),
        'group_relation_verification': None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    args = parser.parse_args()
    (HERE / 'runs').mkdir(exist_ok=True)
    prior = json.loads((Q1443 / 'measurements.json').read_text())
    assert sha(args.binary) == prior['binary_sha256']
    receipt = {
        'proposal_id': 'Q1444', 'candidate_id': None, 'run_id': None,
        'claim_class': 'exploratory_one_target_pdp_seed_screen',
        'runner_source_sha256': sha(HERE / 'run.py'),
        'solver_source_sha256': sha(Q1443 / 'insearch.cpp'),
        'build_script_sha256': sha(Q1443 / 'build.sh'),
        'binary_sha256': sha(args.binary),
        'counted_field_source_sha256': sha(
            STAGE / 'q20261011_operation_account/counted_onb.py'),
        'prior_measurement_sha256': sha(Q1443 / 'measurements.json'),
        'input_law': 'one frozen ordinary public point per degree; fresh '
                     'processes; no shared clauses; cap 1 fixed; '
                     'seeds 5,9 at N53 and 10,14 at N83',
        'operation_boundary': 'sum public CountedOnb method entries during '
                              'solver.solve; checked after each target-coset '
                              'S3 root query and propagator batch',
        'controls': 'Q1443 locked controls, same executable and inputs',
        'schedule': [
            {'degree': 53, 'seed': 5}, {'degree': 53, 'seed': 9},
            {'degree': 83, 'seed': 10}, {'degree': 83, 'seed': 14},
        ],
        'attempts': [], 'cumulative_campaigns': [],
        'n131_total_work_log2': None, 'gap_to_2_pow_61_bits': None,
    }
    for spec in receipt['schedule']:
        n, seed = spec['degree'], spec['seed']
        row = run_one(args.binary, n, 'ordinary', seed, 1,
                      500000, 5000, 180)
        receipt['attempts'].append(row)
        print(json.dumps({'degree': n, 'seed': seed,
                          'status': row['status_label'],
                          'api_budget_hit': row['result']['api_budget_hit'],
                          'api_events': row['field_api_method_entry_events'],
                          'overshoot': row['api_budget_overshoot'],
                          'final_checks': row['result']['final_link_checks']},
                         sort_keys=True), flush=True)
    for n in (53, 83):
        rows = [row for row in receipt['attempts'] if row['degree'] == n]
        old = next(c['cumulative_api_events']
                   for c in prior['cumulative_campaigns'] if c['degree'] == n)
        new = sum(row['field_api_method_entry_events'] for row in rows)
        receipt['cumulative_campaigns'].append({
            'degree': n, 'target_count': 1,
            'prior_archived_api_events': old,
            'frozen_new_api_events': new,
            'cumulative_api_events': old + new,
            'cumulative_api_log2': math.log2(old + new),
            'new_seed_results': [{
                'seed': row['seed'],
                'final_link_checks': row['result']['final_link_checks'],
                'field_api_events': row['field_api_method_entry_events'],
                'final_checks_per_million_api_events':
                    row['result']['final_link_checks'] * 1e6 /
                    row['field_api_method_entry_events'],
            } for row in rows],
            'verified_group_relations': None,
            'cost_per_successful_decomposition_log2': None,
        })
    (HERE / 'measurements.json').write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'campaigns': receipt['cumulative_campaigns']},
                     sort_keys=True))


if __name__ == '__main__':
    main()
