#!/usr/bin/env python3
"""Bind the exact N53/N83 pair-table comparators to Q1435's workloads."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'measurements.json'
    measurements = json.loads(path.read_text())
    references = []
    for n, filename in ((53, 'n53_ordinary_matched_pair_table.json'),
                        (83, 'n83_q1400_pair_comparator.json')):
        reference_path = STAGE / 'runs' / filename
        reference = json.loads(reference_path.read_text())
        row = next(row for row in measurements['ordinary_runs']
                   if row['degree'] == n)
        for key in ('curve_id', 'workload_id', 'factor_base_actual_B',
                    'factor_base_enumerated_set_sha256'):
            assert reference[key] == row[key], (n, key)
        folded = reference.get('factor_base_folded_columns',
                               reference.get('factor_base_folded_columns_K'))
        assert folded == row['factor_base_folded_columns']
        assert reference['isogeny'] == 'none'
        references.append({
            'degree': n, 'file': str(reference_path.relative_to(STAGE)),
            'sha256': sha(reference_path),
            'curve_id': reference['curve_id'],
            'workload_id': reference['workload_id'],
            'factor_base_actual_B': reference['factor_base_actual_B'],
            'factor_base_folded_columns': folded,
            'factor_base_enumerated_set_sha256': reference[
                'factor_base_enumerated_set_sha256'],
            'status': reference['status'],
            'verified_relation_count': reference['verified_relation_count'],
            'complete_work_log2': reference['complete_work_log2'],
            'charged_pair_descriptors': reference.get(
                'table_descriptors_charged', reference.get('table_samples')),
            'charged_target_pair_queries': reference.get(
                'target_lifted_pair_queries_charged',
                (reference.get('ordinary_query') or {}).get('query_samples')),
        })
    measurements['pair_references'] = references
    path.write_text(json.dumps(measurements, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'matched_pair_references': len(references),
                      'statuses': [r['status'] for r in references]},
                     sort_keys=True))


if __name__ == '__main__':
    main()
