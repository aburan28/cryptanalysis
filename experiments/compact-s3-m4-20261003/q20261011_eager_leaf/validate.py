#!/usr/bin/env python3
"""Validate reversed exact S3 support and replay Q1435 ordinary samples."""

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
    return ''.join(str((value >> i) & 1) for i in range(n))


def from_bits(value):
    return sum(int(bit) << i for i, bit in enumerate(value))


def fixed_reverse(binary, scratch, onb, a, target, blocked):
    n = onb.m
    cnf = scratch / 'reverse.cnf'
    mapping = scratch / 'reverse.map'
    target_file = scratch / 'reverse.targets'
    fixed = [-var for var in range(1, 4*n+1)]
    encoded_a = onb.toCoords(a)
    fixed.extend((1 if encoded_a & (1 << i) else -1) * (5*n+i+1)
                 for i in range(n))
    blockers = []
    for root in blocked:
        coordinate = onb.toCoords(root)
        blockers.append(tuple((-1 if coordinate & (1 << i) else 1) *
                              (4*n+i+1) for i in range(n)))
    cnf.write_text(f'p cnf {6*n} {len(fixed)+len(blockers)}\n' +
                   ''.join(f'{lit} 0\n' for lit in fixed) +
                   ''.join(' '.join(map(str, clause)) + ' 0\n'
                           for clause in blockers))
    mapping.write_text(f'{n}\n' + ''.join(
        ' '.join(str(var) for var in range(row*n+1, (row+1)*n+1)) + '\n'
        for row in range(6)))
    target_file.write_text(
        f'{n} 1 ALG1N11 validation\n{bits(onb.toCoords(target),n)}\n')
    command = [str(binary), str(cnf), str(mapping), str(target_file),
               str(STAGE), str(ROOT / 'ecc2k130/codegen'),
               'pair1pos', 'satpivot', 'selector', '1', 'off', '2', '1000', '10']
    completed = subprocess.run(command, capture_output=True, text=True,
                               timeout=25, check=False)
    assert completed.returncode in (10, 20), completed.stderr
    lines = completed.stdout.splitlines()
    result = json.loads(lines[0])
    assert result['early_reverse_queries'] == 1
    if result['status'] == 10:
        model = [int(value) for value in lines[1].split()[1:-1]]
        middle = from_bits(''.join('1' if lit > 0 else '0'
                                   for lit in model[4*n:5*n]))
        assert evaluate_s3(onb, a, target, onb.fromCoords(middle)) == 0
    return result


def replay_ordinary(measurements):
    checked = []
    for row in [*measurements['ordinary_runs'],
                *measurements.get('limit_sweep_runs', [])]:
        n = row['degree']
        onb = field.Onb(n)
        for sample in row['result']['leaf_rejection_samples']:
            x = onb.fromCoords(from_bits(sample['x_bits']))
            assert x and onb.trace(onb.add(x, onb.sqr(onb.inv(x)))) == 1
            checked.append({'degree': n, 'branch': row['branch'],
                            'leaf_mode': row['leaf_mode'], 'row': sample['row'],
                            'x_bits': sample['x_bits'], 'trace': 1})
    return checked


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    args = parser.parse_args()
    measurements = json.loads((HERE / 'measurements.json').read_text())
    assert measurements['binary_sha256'] == hashlib.sha256(
        args.binary.read_bytes()).hexdigest()
    assert measurements['source_sha256'] == hashlib.sha256(
        (HERE / 'insearch.cpp').read_bytes()).hexdigest()
    assert all(row['result']['status'] == 10 and
               row['verification']['status'] == 'verified_s3'
               for row in measurements['control_runs'])
    for reference in measurements['pair_references']:
        path = STAGE / reference['file']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == reference['sha256']
        row = next(row for row in measurements['ordinary_runs']
                   if row['degree'] == reference['degree'])
        for key in ('curve_id', 'workload_id', 'factor_base_actual_B',
                    'factor_base_folded_columns',
                    'factor_base_enumerated_set_sha256'):
            assert reference[key] == row[key]
    for n in (53, 83):
        pairs = [row for row in measurements['ordinary_runs']
                 if row['degree'] == n and row['branch'] == 'allpos']
        assert len(pairs) == 2
        assert all(row['result']['leaf_eager_checks'] == 0 for row in pairs)
        # Compare exact counters only if both runs reach the same conflict
        # cap. Wall-censored N83 rows stop at different search positions.
        if all(not row['result']['wall_cap_hit'] for row in pairs):
            for key in ('root_queries', 'early_queries', 'leaf_rationality_checks',
                        'leaf_nonrational_rejections', 'leaf_guard_literals',
                        'external_clauses', 'solver_decisions'):
                assert pairs[0]['result'][key] == pairs[1]['result'][key]
    onb = field.Onb(11)
    two_root = rootless = None
    for ac in range(1, 20):
        for tc in range(1, 20):
            a, target = onb.fromCoords(ac), onb.fromCoords(tc)
            roots = s3_roots(onb, a, target)
            if len(roots) == 2 and two_root is None:
                two_root = (a, target, roots)
            if not roots and rootless is None:
                rootless = (a, target)
        if two_root and rootless:
            break
    assert two_root and rootless
    cases = []
    with tempfile.TemporaryDirectory() as directory:
        scratch = Path(directory)
        a, target, roots = two_root
        positive = fixed_reverse(args.binary, scratch, onb, a, target, ())
        assert positive['status'] == 10 and positive['early_roots_total'] == 2
        blocked = fixed_reverse(args.binary, scratch, onb, a, target, roots)
        assert blocked['status'] == 20 and blocked['early_roots_total'] == 2
        cases.append({'kind': 'two_roots', 'positive': 10,
                      'blocked_both_roots': 20})
        a, target = rootless
        empty = fixed_reverse(args.binary, scratch, onb, a, target, ())
        assert empty['status'] == 20 and empty['early_zero_root'] == 1
        cases.append({'kind': 'zero_roots', 'status': 20})
        target = onb.fromCoords(1)
        degenerate = fixed_reverse(args.binary, scratch, onb, 0, target, ())
        assert degenerate['status'] == 10 and degenerate['early_roots_total'] == 1
        cases.append({'kind': 'zero_first_middle', 'status': 10})
    result = {'status': 'PASS',
              'ordinary_rejected_leaf_replay': replay_ordinary(measurements),
              'fixed_degree11_reverse_cases': cases}
    (HERE / 'validation.json').write_text(
        json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'status': 'PASS',
                      'ordinary_samples': len(result['ordinary_rejected_leaf_replay']),
                      'reverse_cases': len(cases)}, sort_keys=True))


if __name__ == '__main__':
    main()
