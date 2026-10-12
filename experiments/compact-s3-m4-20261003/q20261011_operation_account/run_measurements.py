#!/usr/bin/env python3
"""Freeze exact field API vectors for Q1436 ordinary N53/N83 searches."""

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = STAGE.parents[1]
sys.path.insert(0, str(STAGE / 'q20261010_final_link'))
from verify_model import verify  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def operation_counts(result):
    calls = result['field_api_calls']
    names = ('fromCoords', 'toCoords', 'add', 'mul', 'sqr', 'frob',
             'inv', 'trace', 'one', 'zero', 'pow')
    assert set(calls) == set(names)
    assert all(isinstance(calls[name], int) and calls[name] >= 0
               for name in names)
    total = sum(calls.values())
    conversions = calls['fromCoords'] + calls['toCoords']
    return {'api_method_entry_events': total,
            'api_method_entry_log2': math.log2(total),
            'conversion_method_entry_events': conversions,
            'arithmetic_method_entry_events': total - conversions,
            'field_api_calls': calls}


def run(binary, n, mode, branch, early_limit, wall, conflicts):
    prefix = Path('/private/tmp/q1430_n53_' + mode if n == 53 else
                  '/private/tmp/q1430_' + mode)
    target = STAGE / 'q20261010_final_link' / f'n{n}_{mode}.targets'
    manifest = json.loads(target.with_suffix('.targets.json').read_text())
    meta = json.loads(prefix.with_suffix('.json').read_text())
    for key in ('curve_id', 'workload_id', 'factor_base_actual_B',
                'factor_base_enumerated_set_sha256'):
        assert meta[key] == manifest[key]
    assert meta['factor_base_folded_columns'] == manifest[
        'factor_base_folded_columns']
    assert sha(prefix.with_suffix('.cnf')) == meta['cnf_sha256']
    assert sha(target) == manifest['target_file_sha256']
    label = f'n{n}_{mode}_{branch}_early{early_limit}'
    log = HERE / f'{label}.log'
    command = [str(binary), str(prefix.with_suffix('.cnf')),
               str(prefix.with_suffix('.map')), str(target),
               str(STAGE), str(ROOT / 'ecc2k130/codegen'), branch,
               'satpivot', 'selector', str(early_limit), 'eager',
               str(3 if n == 53 else 5), str(conflicts), str(wall)]
    completed = subprocess.run(command, cwd=ROOT, text=True,
                               capture_output=True, timeout=wall + 30,
                               check=False)
    log.write_text(completed.stdout)
    if completed.stderr:
        (HERE / f'{label}.stderr.log').write_text(completed.stderr)
    assert completed.returncode in (0, 10, 20), completed.stderr
    result = json.loads(completed.stdout.splitlines()[0])
    assert result['status'] in (0, 10, 20)
    row = {
        'degree': n, 'mode': mode, 'branch': branch,
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
        'wall_cap_seconds': wall, 'conflict_cap': conflicts,
        'log': log.name, 'log_sha256': sha(log),
        'exit_code': completed.returncode, 'result': result,
        'status_label': ('SAT' if result['status'] == 10 else
                         'UNSAT' if result['status'] == 20 else
                         'BOUNDED_UNKNOWN'),
        'operations': operation_counts(result),
        'verification': (verify(prefix.with_suffix('.json'), log)
                         if result['status'] == 10 else None),
    }
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    args = parser.parse_args()
    receipt = {
        'proposal_id': 'Q1436', 'candidate_id': None, 'run_id': None,
        'claim_class': 'exploratory_stage_diagnostic',
        'source_sha256': sha(HERE / 'insearch.cpp'),
        'counter_source_sha256': sha(HERE / 'counted_onb.py'),
        'build_script_sha256': sha(HERE / 'build.sh'),
        'binary_sha256': sha(args.binary),
        'field_source_sha256': sha(ROOT / 'ecc2k130/codegen/field.py'),
        's3_root_oracle_source_sha256': sha(STAGE / 's3_root_oracle.py'),
        'chain_s3_source_sha256': sha(STAGE / 'chain_s3.py'),
        'operation_boundary': ('CountedOnb public method entries from immediately '
                               'before solver.solve through its return; nested '
                               'method entries and executed oracle assertions '
                               'are included. CNF load, target-coset construction, '
                               'field setup, final matrix, and target DLP stages '
                               'are outside this stage counter.'),
        'ordinary_runs': [], 'control_runs': [],
        'cost_per_successful_decomposition_log2': None,
        'n131_total_work_log2': None, 'gap_to_2_pow_61_bits': None,
    }
    for n, branch, limit in ((53, 'allpos', 20),
                             (83, 'allpos', 100),
                             (83, 'pair1spread', 25)):
        row = run(args.binary, n, 'ordinary', branch, limit, 30, 5000)
        receipt['ordinary_runs'].append(row)
        print(json.dumps({'degree': n, 'branch': branch,
                          'status': row['status_label'],
                          'field_api_events': row['operations'][
                              'api_method_entry_events'],
                          'field_api_log2': row['operations'][
                              'api_method_entry_log2'],
                          'root_queries': row['result']['root_queries']},
                         sort_keys=True), flush=True)
    for n in (53, 83):
        row = run(args.binary, n, 'control', 'pair1pos', 5, 10, 1000)
        assert row['status_label'] == 'SAT'
        assert row['verification']['status'] == 'verified_s3'
        receipt['control_runs'].append(row)
    (HERE / 'measurements.json').write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'ordinary_rows': len(receipt['ordinary_runs']),
                      'control_rows': len(receipt['control_runs'])},
                     sort_keys=True))


if __name__ == '__main__':
    main()
