#!/usr/bin/env python3
"""Replay rootless ordinary states and exercise early S3 support clauses."""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = STAGE.parents[1]
sys.path.insert(0, str(STAGE))
from chain_s3 import evaluate_s3, field  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402


def bits(value, n):
    return ''.join(str((value >> bit) & 1) for bit in range(n))


def as_int(bitstring):
    return sum(int(bit) << index for index, bit in enumerate(bitstring))


def root_possible(onb, a, t):
    """Use the S3 quadratic discriminant, separate from the C++ callback."""
    if not a and not t:
        return False
    if not a or not t or a == t:
        return True
    product = onb.mul(a, t)
    total = onb.add(a, t)
    constant = onb.add(onb.sqr(product), onb.one())
    right = onb.mul(onb.mul(onb.sqr(total), constant),
                    onb.sqr(onb.inv(product)))
    return onb.trace(right) == 0


def validate_ordinary(measurements):
    replay = []
    for row in measurements['ordinary_runs']:
        result = row['result']
        samples = result['early_zero_samples']
        if not samples:
            continue
        n = row['degree']
        onb = field.Onb(n)
        target_file = STAGE / 'q20261010_final_link' / f'n{n}_ordinary.targets'
        assert hashlib.sha256(target_file.read_bytes()).hexdigest() == row[
            'target_file_sha256']
        target_bits = target_file.read_text().splitlines()[1:]
        targets = [onb.fromCoords(as_int(value)) for value in target_bits]
        assert all(t and onb.trace(onb.add(t, onb.sqr(onb.inv(t)))) == 0
                   for t in targets)
        for bitstring in samples:
            assert len(bitstring) == n
            a = onb.fromCoords(as_int(bitstring))
            assert all(not root_possible(onb, a, t) for t in targets)
            curve_trace = (onb.trace(onb.add(a, onb.sqr(onb.inv(a))))
                           if a else None)
            replay.append({'degree': n, 'branch': row['branch'],
                           'early_mode': row['early_mode'],
                           'first_middle_x_bits': bitstring,
                           'target_coordinates_checked': len(targets),
                           'all_target_discriminants_rootless': True,
                           'curve_rationality_trace': curve_trace})
    return replay


def synthetic_case(binary, scratch, a_bits, b_bits, target_bits, expected):
    n = len(a_bits)
    cnf = scratch / 'fixed.cnf'
    mapping = scratch / 'fixed.map'
    target = scratch / 'fixed.targets'
    rows = ['0' * n] * 4 + [a_bits, b_bits]
    assignments = [((row[bit] == '1') * 2 - 1) * (index * n + bit + 1)
                   for index, row in enumerate(rows) for bit in range(n)]
    cnf.write_text(f'p cnf {6*n} {6*n}\n' +
                   ''.join(f'{lit} 0\n' for lit in assignments))
    mapping.write_text(f'{n}\n' + ''.join(
        ' '.join(str(var) for var in range(row*n+1, (row+1)*n+1)) + '\n'
        for row in range(6)))
    target.write_text(f'{n} 1 ALG1N11 validation\n{target_bits}\n')
    command = [str(binary), str(cnf), str(mapping), str(target),
               str(STAGE), str(ROOT / 'ecc2k130/codegen'),
               'allpos', 'satpivot', 'selector', '1', '2', '1000', '10']
    completed = subprocess.run(command, capture_output=True, text=True,
                               timeout=25, check=False)
    assert completed.returncode == expected, completed.stderr
    result = json.loads(completed.stdout.splitlines()[0])
    assert result['status'] == expected and result['early_queries'] == 1
    return result


def validate_fixed(binary):
    n = 11
    onb = field.Onb(n)
    one = onb.fromCoords(1)
    two = onb.fromCoords(2)
    cases = [(0, 0), (0, one), (one, one)]
    pair_zero = pair_two = None
    for a_coord in range(1, 20):
        for t_coord in range(1, 20):
            a, t = onb.fromCoords(a_coord), onb.fromCoords(t_coord)
            roots = s3_roots(onb, a, t)
            if not roots and pair_zero is None:
                pair_zero = (a, t)
            if len(roots) == 2 and pair_two is None:
                pair_two = (a, t)
            if pair_zero and pair_two:
                break
        if pair_zero and pair_two:
            break
    assert pair_zero and pair_two
    cases.extend([pair_zero, pair_two, (one, two)])
    outcomes = []
    with tempfile.TemporaryDirectory() as directory:
        scratch = Path(directory)
        for a, t in cases:
            roots = (() if not a and not t else
                     (onb.inv(t or a),) if not a or not t else
                     s3_roots(onb, a, t))
            assert all(evaluate_s3(onb, a, t, root) == 0 for root in roots)
            chosen = roots[0] if roots else 0
            expected = 10 if roots else 20
            result = synthetic_case(binary, scratch, bits(onb.toCoords(a), n),
                                    bits(onb.toCoords(chosen), n),
                                    bits(onb.toCoords(t), n), expected)
            assert result['early_roots_total'] == len(roots)
            assert result['early_zero_root'] == int(not roots)
            if roots:
                incompatible = next(value for value in range(1 << n)
                                    if evaluate_s3(onb, a, t,
                                                   onb.fromCoords(value)) != 0)
                negative = synthetic_case(
                    binary, scratch, bits(onb.toCoords(a), n),
                    bits(incompatible, n), bits(onb.toCoords(t), n), 20)
                assert negative['early_roots_total'] == len(roots)
            outcomes.append({'a': onb.toCoords(a), 'target': onb.toCoords(t),
                             'root_count': len(roots), 'positive_status': expected})
    return outcomes


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
              'ordinary_zero_root_replay': validate_ordinary(measurements),
              'fixed_degree11_cases': validate_fixed(args.binary)}
    output = HERE / 'validation.json'
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'status': result['status'],
                      'ordinary_zero_samples': len(result['ordinary_zero_root_replay']),
                      'fixed_cases': len(result['fixed_degree11_cases'])},
                     sort_keys=True))


if __name__ == '__main__':
    main()
