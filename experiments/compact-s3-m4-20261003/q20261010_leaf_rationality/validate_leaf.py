#!/usr/bin/env python3
"""Replay rejected leaf traces and validate exact leaf guard behavior."""

import argparse
import hashlib
import itertools
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = STAGE.parents[1]
sys.path.insert(0, str(STAGE))
from chain_s3 import field  # noqa: E402


def bits(value, n):
    return ''.join(str((value >> bit) & 1) for bit in range(n))


def as_int(bitstring):
    return sum(int(bit) << index for index, bit in enumerate(bitstring))


def rational(onb, coordinates):
    x = onb.fromCoords(coordinates)
    return not x or onb.trace(onb.add(x, onb.sqr(onb.inv(x)))) == 0


def replay_ordinary(measurements):
    rows = []
    for run in [*measurements['ordinary_runs'],
                *measurements.get('long_runs', [])]:
        if run['leaf_mode'] == 'off':
            continue
        n = run['degree']
        onb = field.Onb(n)
        for sample in run['result']['leaf_rejection_samples']:
            x = sample['x_bits']
            weight = x.count('1')
            assert len(x) == n and sample['row'] in range(4)
            assert weight <= (3 if n == 53 else 5)
            assert not rational(onb, as_int(x))
            rows.append({'degree': n, 'leaf_mode': run['leaf_mode'],
                         'branch': run['branch'], 'row': sample['row'],
                         'x_bits': x, 'weight': weight,
                         'curve_rationality_trace': 1})
    return rows


def fixed_case(binary, scratch, x_bits, leaf_mode, expected):
    n = len(x_bits)
    rows = [x_bits] + ['0' * n] * 5
    unit_clauses = [(((row[bit] == '1') * 2 - 1) *
                     (index * n + bit + 1),)
                    for index, row in enumerate(rows) for bit in range(n)]
    weight_clauses = [tuple(-var for var in chosen)
                      for chosen in itertools.combinations(range(1, n + 1), 3)]
    clauses = unit_clauses + weight_clauses
    cnf = scratch / 'fixed.cnf'
    mapping = scratch / 'fixed.map'
    cnf.write_text(f'p cnf {6*n} {len(clauses)}\n' + ''.join(
        ' '.join(map(str, clause)) + ' 0\n' for clause in clauses))
    mapping.write_text(f'{n}\n' + ''.join(
        ' '.join(str(var) for var in range(row*n+1, (row+1)*n+1)) + '\n'
        for row in range(6)))
    command = [str(binary), str(cnf), str(mapping), '-', str(STAGE),
               str(ROOT / 'ecc2k130/codegen'), 'allpos', 'satpivot',
               'off', '0', leaf_mode, '2', '1000', '10']
    completed = subprocess.run(command, capture_output=True, text=True,
                               timeout=25, check=False)
    assert completed.returncode == expected, completed.stderr
    result = json.loads(completed.stdout.splitlines()[0])
    assert result['status'] == expected
    return result


def validate_fixed(binary):
    n = 11
    onb = field.Onb(n)
    rational_weight2 = nonrational_weight2 = nonrational_weight1 = None
    for weight in (1, 2):
        for selected in itertools.combinations(range(n), weight):
            coordinate = sum(1 << bit for bit in selected)
            if rational(onb, coordinate):
                if weight == 2 and rational_weight2 is None:
                    rational_weight2 = coordinate
            elif weight == 2 and nonrational_weight2 is None:
                nonrational_weight2 = coordinate
            elif weight == 1 and nonrational_weight1 is None:
                nonrational_weight1 = coordinate
    assert rational_weight2 is not None and nonrational_weight2 is not None
    cases = [(0, 'sat', 10), (rational_weight2, 'sat', 10),
             (nonrational_weight2, 'full', 20),
             (nonrational_weight2, 'sat', 20)]
    if nonrational_weight1 is not None:
        cases.append((nonrational_weight1, 'sat', 20))
    results = []
    with tempfile.TemporaryDirectory() as directory:
        scratch = Path(directory)
        for x, mode, expected in cases:
            result = fixed_case(binary, scratch, bits(x, n), mode, expected)
            if expected == 20:
                assert result['leaf_nonrational_rejections'] == 1
                assert result['leaf_guard_literals'] == (
                    2 if mode == 'sat' and x.bit_count() == 2 else n)
            else:
                assert result['leaf_nonrational_rejections'] == 0
            results.append({'x_coordinates': x, 'weight': x.bit_count(),
                            'leaf_mode': mode, 'status': expected,
                            'guard_literals': result['leaf_guard_literals']})
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    args = parser.parse_args()
    measurements = json.loads((HERE / 'measurements.json').read_text())
    assert hashlib.sha256(args.binary.read_bytes()).hexdigest() == measurements[
        'binary_sha256']
    assert all(row['result']['status'] == 10 and
               row['verification']['status'] == 'verified_s3'
               for row in measurements['control_runs'])
    result = {'status': 'PASS',
              'ordinary_rejected_leaf_replay': replay_ordinary(measurements),
              'fixed_degree11_cases': validate_fixed(args.binary)}
    (HERE / 'validation.json').write_text(
        json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'status': result['status'],
                      'ordinary_samples': len(result['ordinary_rejected_leaf_replay']),
                      'fixed_cases': len(result['fixed_degree11_cases'])},
                     sort_keys=True))


if __name__ == '__main__':
    main()
