#!/usr/bin/env python3
"""Replay root-first plans on the native curve code and independent points."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'prime-j0-eisenstein-residue-20261015'
sys.path.insert(0, str(BASE))
from check_secp256k1_tau_generator import G, add, mul  # noqa: E402


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def encode(point):
    if point is None:
        return 'identity'
    return ':'.join(f'{coordinate:064x}' for coordinate in point)


def run(binary, fixture, count, plan, mode, path):
    path.write_text(json.dumps(fixture, sort_keys=True, separators=(',', ':')) + '\n')
    command = [str(binary), '--pilot-rho-restart-joint-' + mode,
               str(path), str(count), str(plan)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0 and not result.stderr, result.stderr
    fields = dict(word.split('=', 1) for word in result.stdout.split())
    assert fields['verified'] == '1' and fields['count'] == str(count)
    assert fields['point'] == fixture['cases'][count-1]['point_hex']
    assert fields['graph_plan_ms'] == '0.000000'
    assert int(fields['graph_edges']) + int(fields['direct_seeds']) == \
        int(fields['constructed_q_points'])
    return {'count': count, 'mode': mode, 'fixture_sha256': digest(path),
            'plan_sha256': digest(plan), 'point': fields['point'],
            'verified': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--plan-stem', choices=('root-first', 'two-parent'),
                        default='root-first')
    args = parser.parse_args()
    frozen_path = BASE / 'rho-restart-first128-fixture.json'
    frozen = json.loads(frozen_path.read_bytes())
    results = []
    with TemporaryDirectory(prefix='root-first-replay-') as temp:
        root = Path(temp)
        for count in (1, 128):
            plan = HERE / f'{args.plan_stem}-plan-{count}.json'
            for mode in ('graph-planned', 'fused-graph-planned'):
                results.append(run(args.binary, frozen, count, plan, mode,
                                   root / f'frozen-{count}.json'))
        one_plan = HERE / f'{args.plan_stem}-plan-1.json'
        row = frozen['cases'][0]
        a, b = int(row['a_hex'], 16), int(row['b_hex'], 16)
        for q_scalar in (1, 2, 3, 7):
            q = mul(q_scalar, G)
            fixture = {'q_hex': encode(q), 'cases': [{
                'a_hex': row['a_hex'], 'b_hex': row['b_hex'],
                'point_hex': encode(add(mul(a, G), mul(b, q))),
            }]}
            for mode in ('graph-planned', 'fused-graph-planned'):
                result = run(args.binary, fixture, 1, one_plan, mode,
                             root / f'q{q_scalar}.json')
                result['q_scalar'] = q_scalar
                results.append(result)
    receipt = {'schema': 1, 'purpose': 'correctness_and_operation_count_only',
               'plan_stem': args.plan_stem,
               'binary_sha256': digest(args.binary),
               'frozen_fixture_sha256': digest(frozen_path),
               'planner_sha256': digest(HERE / ('root_first_plan.py'
                   if args.plan_stem == 'root-first' else 'two_parent_plan.py')),
               'root_first_planner_sha256': digest(HERE / 'root_first_plan.py'),
               'results': results}
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'ok': True, 'commands': len(results),
                      'exact_outputs': sum(row['count'] for row in results)},
                     sort_keys=True))


if __name__ == '__main__':
    main()
