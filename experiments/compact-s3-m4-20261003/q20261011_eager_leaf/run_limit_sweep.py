#!/usr/bin/env python3
"""Sweep the N83 target-support cap reached by Q1435 pair1spread."""

import argparse
import hashlib
import json
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    args = parser.parse_args()
    output = HERE / 'measurements.json'
    data = json.loads(output.read_text())
    assert data['source_sha256'] == sha(HERE / 'insearch.cpp')
    assert data['binary_sha256'] == sha(args.binary)
    base = next(row for row in data['ordinary_runs']
                if row['degree'] == 83 and row['branch'] == 'pair1spread')
    prefix = Path('/private/tmp/q1430_ordinary')
    target = STAGE / 'q20261010_final_link' / 'n83_ordinary.targets'
    meta = json.loads(prefix.with_suffix('.json').read_text())
    assert sha(prefix.with_suffix('.cnf')) == base['cnf_sha256']
    assert sha(prefix.with_suffix('.map')) == base['map_sha256']
    assert sha(target) == base['target_file_sha256']
    assert meta['curve_id'] == base['curve_id']
    assert meta['workload_id'] == base['workload_id']
    assert meta['factor_base_actual_B'] == base['factor_base_actual_B']
    assert meta['factor_base_enumerated_set_sha256'] == base[
        'factor_base_enumerated_set_sha256']
    rows = []
    for limit in (0, 10, 25, 50, 500, 2000):
        log = HERE / f'n83_pair1spread_eager_early{limit}.log'
        command = [str(args.binary), str(prefix.with_suffix('.cnf')),
                   str(prefix.with_suffix('.map')), str(target), str(STAGE),
                   str(ROOT / 'ecc2k130/codegen'), 'pair1spread',
                   'satpivot', 'selector', str(limit), 'eager', '5',
                   '5000', '10']
        completed = subprocess.run(command, cwd=ROOT, text=True,
                                   capture_output=True, timeout=40, check=False)
        log.write_text(completed.stdout)
        if completed.stderr:
            (HERE / f'n83_pair1spread_eager_early{limit}.stderr.log').write_text(
                completed.stderr)
        assert completed.returncode in (0, 10, 20), completed.stderr
        result = json.loads(completed.stdout.splitlines()[0])
        row = {key: base[key] for key in (
            'degree', 'curve_id', 'workload_id', 'isogeny',
            'factor_base_actual_B', 'factor_base_folded_columns',
            'factor_base_enumerated_set_sha256', 'target_file_sha256',
            'cnf_sha256', 'map_sha256', 'branch', 'root_encoding',
            'early_mode', 'leaf_mode')}
        row.update({'early_limit': limit, 'log': log.name,
                    'log_sha256': sha(log), 'exit_code': completed.returncode,
                    'result': result,
                    'status_label': ('SAT' if result['status'] == 10 else
                                     'UNSAT' if result['status'] == 20 else
                                     'BOUNDED_UNKNOWN'),
                    'verification': (verify(prefix.with_suffix('.json'), log)
                                     if result['status'] == 10 else None)})
        rows.append(row)
        print(json.dumps({'limit': limit, 'status': row['status_label'],
                          'early_queries': result['early_queries'],
                          'skipped': result['early_skipped_limit'],
                          'final_rejections': result['final_link_rejections'],
                          'root_queries': result['root_queries']},
                         sort_keys=True), flush=True)
    data['limit_sweep_runs'] = rows
    output.write_text(json.dumps(data, sort_keys=True, indent=2) + '\n')


if __name__ == '__main__':
    main()
