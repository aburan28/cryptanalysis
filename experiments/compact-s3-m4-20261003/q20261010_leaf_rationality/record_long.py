#!/usr/bin/env python3
"""Bind the two extended capped Q1434 runs to frozen inputs and source."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
sys.path.insert(0, str(STAGE / 'q20261010_final_link'))
from verify_model import verify  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    args = parser.parse_args()
    path = HERE / 'measurements.json'
    data = json.loads(path.read_text())
    assert data['binary_sha256'] == sha(args.binary)
    assert data['source_sha256'] == sha(HERE / 'insearch.cpp')
    rows = []
    for n in (53, 83):
        prefix = Path('/private/tmp/q1430_n53_ordinary' if n == 53 else
                      '/private/tmp/q1430_ordinary')
        target = STAGE / 'q20261010_final_link' / f'n{n}_ordinary.targets'
        meta = json.loads(prefix.with_suffix('.json').read_text())
        manifest = json.loads(target.with_suffix('.targets.json').read_text())
        assert meta['curve_id'] == manifest['curve_id']
        assert meta['workload_id'] == manifest['workload_id']
        assert meta['factor_base_actual_B'] == manifest['factor_base_actual_B']
        assert meta['factor_base_enumerated_set_sha256'] == manifest[
            'factor_base_enumerated_set_sha256']
        assert sha(prefix.with_suffix('.cnf')) == meta['cnf_sha256']
        assert sha(target) == manifest['target_file_sha256']
        log = HERE / f'n{n}_allpos_leaf_sat_long.log'
        result = json.loads(log.read_text().splitlines()[0])
        assert result['status'] in (0, 10, 20)
        assert result['seconds'] <= 122
        row = {
            'degree': n, 'curve_id': meta['curve_id'],
            'workload_id': meta['workload_id'], 'isogeny': 'none',
            'factor_base_actual_B': meta['factor_base_actual_B'],
            'factor_base_folded_columns': meta['factor_base_folded_columns'],
            'factor_base_enumerated_set_sha256': meta[
                'factor_base_enumerated_set_sha256'],
            'target_file_sha256': sha(target),
            'cnf_sha256': meta['cnf_sha256'],
            'map_sha256': sha(prefix.with_suffix('.map')),
            'branch': 'allpos', 'root_encoding': 'satpivot',
            'early_mode': 'selector',
            'early_limit': 20 if n == 53 else 100,
            'leaf_mode': 'sat',
            'conflict_cap': 100000, 'wall_cap_seconds': 120,
            'log': log.name, 'log_sha256': sha(log),
            'result': result,
            'status_label': ('SAT' if result['status'] == 10 else
                             'UNSAT' if result['status'] == 20 else
                             'BOUNDED_UNKNOWN'),
            'verification': (verify(prefix.with_suffix('.json'), log)
                             if result['status'] == 10 else None),
        }
        rows.append(row)
    data['long_runs'] = rows
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'long_rows': len(rows),
                      'statuses': [row['status_label'] for row in rows]},
                     sort_keys=True))


if __name__ == '__main__':
    main()
