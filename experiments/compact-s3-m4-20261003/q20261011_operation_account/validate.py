#!/usr/bin/env python3
"""Validate counted field arithmetic, receipts, and unchanged N53 search."""

import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = STAGE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'ecc2k130/codegen'))
sys.path.insert(0, str(STAGE))
from counted_onb import CountedOnb  # noqa: E402
from field import Onb  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_field():
    rng = random.Random(1436)
    cases = []
    for n in (11, 53, 83):
        ordinary, counted = Onb(n), CountedOnb(n)
        for _ in range(12):
            ac = rng.randrange(1, 1 << n)
            bc = rng.randrange(1, 1 << n)
            a, b = ordinary.fromCoords(ac), ordinary.fromCoords(bc)
            ca, cb = counted.fromCoords(ac), counted.fromCoords(bc)
            assert (a, b) == (ca, cb)
            assert ordinary.add(a, b) == counted.add(ca, cb)
            assert ordinary.mul(a, b) == counted.mul(ca, cb)
            assert ordinary.sqr(a) == counted.sqr(ca)
            assert ordinary.inv(a) == counted.inv(ca)
            assert ordinary.trace(a) == counted.trace(ca)
            assert ordinary.toCoords(a) == counted.toCoords(ca)
            assert s3_roots(ordinary, a, b) == s3_roots(counted, ca, cb)
        counted.reset_counts()
        counted.sqr(counted.fromCoords(3))
        assert counted.calls['sqr'] == counted.calls['frob'] == 1
        cases.append({'degree': n, 'compared_pairs': 12,
                      'nested_square_frobenius_count': 1})
    return cases


def validate_receipts(measurements):
    assert measurements['source_sha256'] == sha(HERE / 'insearch.cpp')
    assert measurements['counter_source_sha256'] == sha(HERE / 'counted_onb.py')
    assert measurements['field_source_sha256'] == sha(
        ROOT / 'ecc2k130/codegen/field.py')
    assert measurements['s3_root_oracle_source_sha256'] == sha(
        STAGE / 's3_root_oracle.py')
    assert measurements['chain_s3_source_sha256'] == sha(STAGE / 'chain_s3.py')
    checked_samples = 0
    for row in [*measurements['ordinary_runs'], *measurements['control_runs']]:
        log = HERE / row['log']
        assert sha(log) == row['log_sha256']
        result = json.loads(log.read_text().splitlines()[0])
        assert result == row['result']
        calls = result['field_api_calls']
        assert calls == row['operations']['field_api_calls']
        total = sum(calls.values())
        assert total == row['operations']['api_method_entry_events']
        assert math.isclose(math.log2(total),
                            row['operations']['api_method_entry_log2'])
        conversions = calls['fromCoords'] + calls['toCoords']
        assert conversions == row['operations'][
            'conversion_method_entry_events']
        assert total - conversions == row['operations'][
            'arithmetic_method_entry_events']
        field = Onb(row['degree'])
        for sample in result['leaf_rejection_samples']:
            xcoords = sum(int(bit) << i for i, bit in
                          enumerate(sample['x_bits']))
            x = field.fromCoords(xcoords)
            assert x and field.trace(field.add(x, field.sqr(field.inv(x)))) == 1
            checked_samples += 1
    assert all(row['status_label'] == 'BOUNDED_UNKNOWN' and
               row['verification'] is None
               for row in measurements['ordinary_runs'])
    assert all(row['status_label'] == 'SAT' and
               row['verification']['status'] == 'verified_s3'
               for row in measurements['control_runs'])
    prior = json.loads((STAGE / 'q20261011_eager_leaf' /
                        'measurements.json').read_text())
    current = next(row for row in measurements['ordinary_runs']
                   if row['degree'] == 53)
    earlier = next(row for row in prior['ordinary_runs']
                   if row['degree'] == 53 and row['branch'] == 'allpos'
                   and row['leaf_mode'] == 'eager')
    for key in ('status', 'conflicts', 'propagations', 'solver_decisions',
                'root_queries', 'early_queries', 'leaf_rationality_checks',
                'leaf_nonrational_rejections', 'external_clauses'):
        assert current['result'][key] == earlier['result'][key]
    return {'ordinary_n53_same_search_counters': True,
            'replayed_nonrational_leaf_samples': checked_samples}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    args = parser.parse_args()
    measurements = json.loads((HERE / 'measurements.json').read_text())
    assert measurements['binary_sha256'] == sha(args.binary)
    result = {'status': 'PASS', 'field_cases': validate_field(),
              'receipt_checks': validate_receipts(measurements)}
    (HERE / 'validation.json').write_text(
        json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'status': result['status'],
                      'field_cases': len(result['field_cases']),
                      'leaf_samples': result['receipt_checks'][
                          'replayed_nonrational_leaf_samples']},
                     sort_keys=True))


if __name__ == '__main__':
    main()
