#!/usr/bin/env python3
"""Replay the norm-6481 joint path against independent secp256k1 points."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import random
import subprocess
from tempfile import TemporaryDirectory

import cryptography
from cryptography.hazmat.primitives.asymmetric import ec

HERE = Path(__file__).resolve().parent
ORDER = int('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141', 16)
RANDOM_SEED = 0x648120261016


def point(scalar):
    scalar %= ORDER
    if scalar == 0:
        return 'identity'
    public = ec.derive_private_key(scalar, ec.SECP256K1()).public_key().public_numbers()
    return f'{public.x:064x}:{public.y:064x}'


def encoded(fixture):
    return json.dumps(fixture, sort_keys=True, separators=(',', ':')).encode()


def derived_fixture(base, q_scalar):
    fixture = dict(base)
    fixture['q_hex'] = point(q_scalar)
    fixture['q_source_index'] = f'alternate-q-{q_scalar}'
    fixture['cases'] = [dict(row, point_hex=point(
        int(row['a_hex'], 16) + q_scalar*int(row['b_hex'], 16)))
        for row in base['cases']]
    return fixture


def seeded_fixture():
    rng = random.Random(RANDOM_SEED)
    rows = []
    for _ in range(128):
        a, b = rng.randrange(1, ORDER), rng.randrange(1, ORDER)
        rows.append({'a_hex': f'{a:x}', 'b_hex': f'{b:x}',
                     'point_hex': point(a+2*b)})
    return {'schema': 1, 'curve': 'secp256k1',
            'input_law': 'seeded uniform nonzero a,b; q=2G',
            'q_hex': point(2), 'cases': rows}


def edge_fixture():
    pairs = [(0, 0), (1, 0), (0, 1), (ORDER-2, 1), (ORDER-1, ORDER-1)]
    return {'schema': 1, 'curve': 'secp256k1',
            'input_law': 'edge scalar controls', 'q_hex': point(2),
            'cases': [{'a_hex': f'{a:x}', 'b_hex': f'{b:x}',
                       'point_hex': point(a+2*b)} for a, b in pairs]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve()
    base_path = HERE / 'rho-restart-first128-fixture.json'
    base = json.loads(base_path.read_bytes())
    fixtures = [('frozen', base, (1, 128))]
    fixtures += [(f'alternate_q_{q}', derived_fixture(base, q),
                  (1, 128) if q == 2 else (1,)) for q in (1, 2, 5)]
    fixtures += [('seeded_q_2', seeded_fixture(), (128,)),
                 ('edge_q_2', edge_fixture(), (5,))]
    results = []
    with TemporaryDirectory(prefix='triple81-replay-') as temp:
        for label, fixture, counts in fixtures:
            data = base_path.read_bytes() if label == 'frozen' else encoded(fixture)
            path = Path(temp) / (label + '.json')
            path.write_bytes(data)
            for count in counts:
                command = [str(binary), '--pilot-rho-restart-joint-triple81',
                           str(path), str(count)]
                run = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, check=False)
                assert run.returncode == 0 and not run.stderr, (label, count, run.stderr)
                fields = dict(word.split('=', 1) for word in run.stdout.split()
                              if '=' in word)
                assert fields['verified'] == '1' and fields['count'] == str(count)
                assert fields['mode'] == 'joint_triple81'
                assert fields['point'] == fixture['cases'][count-1]['point_hex']
                assert int(fields['steps']) == 20
                assert int(fields['triplings_per_step']) == 4
                assert int(fields['graph_edges']) + int(fields['direct_seeds']) == \
                    int(fields['constructed_q_points'])
                results.append({'fixture': label, 'fixture_sha256': sha256(data).hexdigest(),
                                'count': count, 'final_point': fields['point'],
                                'constructed_q_points': int(fields['constructed_q_points']),
                                'graph_edges': int(fields['graph_edges']),
                                'direct_seeds': int(fields['direct_seeds']),
                                'stdout': run.stdout.strip()})
    receipt = {
        'schema': 1, 'status': 'exact_outputs_verified',
        'exact_outputs': sum(row['count'] for row in results),
        'binary_sha256': sha256(binary.read_bytes()).hexdigest(),
        'source_sha256': {name: sha256((HERE / name).read_bytes()).hexdigest()
                          for name in ('joint_norm4033.rs', 'rho_restart_joint.rs',
                                       'native_rho_restart_joint_overlay.py')},
        'platform': platform.platform(), 'cryptography_version': cryptography.__version__,
        'random_seed': RANDOM_SEED, 'results': results,
        'timing_status': 'correctness_diagnostic_only',
    }
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'ok': True, 'exact_outputs': receipt['exact_outputs'],
                      'binary_sha256': receipt['binary_sha256']}))


if __name__ == '__main__':
    main()
