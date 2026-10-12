#!/usr/bin/env python3
"""Check positive and negative final-link propagation on locked controls."""

import argparse
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
from verify_model import verify  # noqa: E402


def run(binary, n, targets, output):
    prefix = Path('/private/tmp/q1430_n53_control' if n == 53 else
                  '/private/tmp/q1430_control')
    command = [str(binary), str(prefix.with_suffix('.cnf')),
               str(prefix.with_suffix('.map')), str(targets), str(STAGE),
               str(ROOT / 'ecc2k130/codegen'), 'allpos', 'satpivot',
               str(3 if n == 53 else 5), '1000', '10']
    completed = subprocess.run(command, capture_output=True, text=True,
                               timeout=25, check=False)
    output.write_text(completed.stdout)
    assert not completed.stderr, completed.stderr
    return completed.returncode, json.loads(completed.stdout.splitlines()[0]), prefix


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    args = parser.parse_args()
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        scratch = Path(directory)
        for n in (53, 83):
            positive = HERE / f'n{n}_control.targets'
            positive_log = scratch / f'n{n}_positive.log'
            code, row, prefix = run(args.binary, n, positive, positive_log)
            assert code == 10 and row['status'] == 10
            assert row['final_link_matches'] == 1
            verified = verify(prefix.with_suffix('.json'), positive_log)
            mids = verified['middle_x_coordinates']
            onb = field.Onb(n)
            a, b = (onb.fromCoords(value) for value in mids)
            incompatible = next(value for value in range(1, 100)
                                if evaluate_s3(onb, a, b,
                                               onb.fromCoords(value)) != 0)
            negative = scratch / f'n{n}_incompatible.targets'
            negative.write_text(
                f'{n} 1 {"EC1N53Ckb1hf77aab617904" if n == 53 else "EC1N83Ckb1h876c2921cb64"} control\n'
                + ''.join(str((incompatible >> bit) & 1) for bit in range(n))
                + '\n')
            negative_log = scratch / f'n{n}_negative.log'
            code, row, _ = run(args.binary, n, negative, negative_log)
            assert code == 20 and row['status'] == 20
            assert row['final_link_rejections'] >= 1
            rows.append({'degree': n, 'positive': 'verified_s3',
                         'negative': 'UNSAT_locked_control_with_incompatible_target',
                         'negative_rejections': row['final_link_rejections']})
        # Exercise the explicit zero-middle branch, where s3_roots is undefined.
        n = 11
        onb = field.Onb(n)
        b = onb.fromCoords(1)
        compatible = onb.toCoords(onb.inv(b))
        assert evaluate_s3(onb, 0, b, onb.fromCoords(compatible)) == 0
        cnf = scratch / 'zero_middle.cnf'
        mapping = scratch / 'zero_middle.map'
        assignments = [-var for var in range(1, 6 * n + 1)]
        assignments[5 * n] = 5 * n + 1
        cnf.write_text(f'p cnf {6*n} {6*n}\n' +
                       ''.join(f'{lit} 0\n' for lit in assignments))
        mapping.write_text(f'{n}\n' + ''.join(
            ' '.join(str(var) for var in range(row*n+1, (row+1)*n+1)) + '\n'
            for row in range(6)))
        for label, value, expected in [('compatible', compatible, 10),
                                       ('incompatible', 0, 20)]:
            target = scratch / f'zero_middle_{label}.targets'
            target.write_text(f'{n} 1 EC1N11Ckb1h000000000000 control\n' +
                              ''.join(str((value >> bit) & 1)
                                      for bit in range(n)) + '\n')
            command = [str(args.binary), str(cnf), str(mapping), str(target),
                       str(STAGE), str(ROOT / 'ecc2k130/codegen'),
                       'allpos', 'satpivot', '2', '1000', '10']
            completed = subprocess.run(command, capture_output=True, text=True,
                                       timeout=25, check=False)
            assert completed.returncode == expected, completed.stderr
            result = json.loads(completed.stdout.splitlines()[0])
            assert result['status'] == expected
            assert result['final_link_checks'] == 1
            assert result['final_link_matches'] == (1 if expected == 10 else 0)
            assert result['final_link_rejections'] == (1 if expected == 20 else 0)
        rows.append({'degree': 11, 'case': 'zero_middle_exact_s3',
                     'positive': 'SAT', 'negative': 'UNSAT'})
    print(json.dumps({'validation': 'PASS', 'rows': rows}, sort_keys=True))


if __name__ == '__main__':
    main()
