#!/usr/bin/env python3
"""Independently construct Q variants and replay the joint rho command."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory

from check_secp256k1_tau_generator import G, add, mul

HERE = Path(__file__).resolve().parent


def point_hex(point):
    assert point is not None
    return ':'.join(f'{coordinate:064x}' for coordinate in point)


def scalar(row, name):
    return int(row[name + '_hex'], 16)


def run(binary, fixture, count, path, mode):
    path.write_text(json.dumps(fixture, sort_keys=True, separators=(',', ':')) + '\n')
    command = ('--pilot-rho-restart-joint' if mode == 'joint'
               else '--pilot-rho-restart-joint-demand')
    result = subprocess.run([str(binary), command, str(path),
                             str(count)], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    fields = dict(word.split('=', 1) for word in result.stdout.split())
    assert fields['verified'] == '1'
    assert fields['mode'] == mode
    assert int(fields['count']) == count
    assert fields['point'] == fixture['cases'][count-1]['point_hex']
    assert result.stderr == ''
    assert float(fields['online_ms']) > 0
    if mode == 'joint_demand':
        assert int(fields['constructed_q_points']) > 0
        assert abs(float(fields['online_ms'])
                   - float(fields['target_preparation_ms'])
                   - float(fields['restart_eval_ms'])) < 0.00001
    return {'mode': mode, 'fixture_sha256': sha256(path.read_bytes()).hexdigest(),
            'count': count, 'point': fields['point'], 'stdout': result.stdout.strip()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = HERE / 'rho-restart-first128-fixture.json'
    frozen = json.loads(source.read_text())
    q = tuple(int(value, 16) for value in frozen['q_hex'].split(':'))
    for row in frozen['cases'][:128]:
        assert row['point_hex'] == point_hex(add(mul(scalar(row, 'a'), G),
                                               mul(scalar(row, 'b'), q)))
    receipt = {
        'schema': 1, 'purpose': 'correctness_replay_only',
        'platform': platform.platform(),
        'binary_sha256': sha256(args.binary.read_bytes()).hexdigest(),
        'component_sha256': {
            name: sha256((HERE / name).read_bytes()).hexdigest()
            for name in ('joint_norm4033.rs', 'rho_restart_joint.rs',
                         'native_rho_restart_joint_overlay.py')},
        'source_fixture_sha256': sha256(source.read_bytes()).hexdigest(),
        'results': [],
    }
    with TemporaryDirectory(prefix='joint-q-batch-replay-') as temporary:
        root = Path(temporary)
        for count in (1, 128):
            for mode in ('joint', 'joint_demand'):
                receipt['results'].append({'q_scalar': None,
                    **run(args.binary, frozen, count, root / 'frozen.json', mode)})
        for q_scalar in (1, 2, 3, 7):
            q = mul(q_scalar, G)
            rows = []
            for row in frozen['cases'][:8]:
                a, b = scalar(row, 'a'), scalar(row, 'b')
                rows.append({'a_hex': row['a_hex'], 'b_hex': row['b_hex'],
                             'point_hex': point_hex(add(mul(a, G), mul(b, q)))})
            fixture = {'q_hex': point_hex(q), 'cases': rows}
            for mode in ('joint', 'joint_demand'):
                receipt['results'].append({'q_scalar': q_scalar,
                    **run(args.binary, fixture, 8, root / f'q{q_scalar}.json', mode)})
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'ok': True, 'runs': len(receipt['results']),
                      'outputs': sum(item['count'] for item in receipt['results'])},
                     sort_keys=True))


if __name__ == '__main__':
    main()
