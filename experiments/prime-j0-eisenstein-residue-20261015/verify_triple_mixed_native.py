#!/usr/bin/env python3
"""Replay the 78-tripling mixed radix against independent secp256k1 points."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory

import cryptography
from verify_triple243_native import (
    derived_fixture, edge_fixture, encoded, seeded_fixture,
)

HERE = Path(__file__).resolve().parent
SOURCES = (
    'joint_norm4033.rs', 'joint_norm58807.rs', 'joint_mixed78.rs',
    'rho_restart_joint_mixed78.rs', 'native_rho_restart_joint_overlay.py',
    'native_rho_restart_joint243_overlay.py',
    'native_rho_restart_mixed78_overlay.py',
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--build-environment', required=True,
                        choices=('complete_archived_inputs',
                                 'diagnostic_empty_atlas_shims'))
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
    with TemporaryDirectory(prefix='mixed78-replay-') as temp:
        for label, fixture, counts in fixtures:
            data = base_path.read_bytes() if label == 'frozen' else encoded(fixture)
            path = Path(temp) / (label + '.json')
            path.write_bytes(data)
            for count in counts:
                command = [str(binary), '--pilot-rho-restart-joint-mixed78',
                           str(path), str(count)]
                run = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, check=False)
                assert run.returncode == 0 and not run.stderr, (label, count, run.stderr)
                fields = dict(word.split('=', 1) for word in run.stdout.split()
                              if '=' in word)
                assert fields['verified'] == '1' and fields['count'] == str(count)
                assert fields['mode'] == 'joint_mixed78'
                assert fields['point'] == fixture['cases'][count-1]['point_hex']
                assert int(fields['steps']) == 16 and int(fields['triplings']) == 78
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
                          for name in SOURCES},
        'platform': platform.platform(),
        'cryptography_version': cryptography.__version__,
        'results': results,
        'build_environment': args.build_environment,
        'timing_status': 'correctness_diagnostic_only',
    }
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'ok': True, 'exact_outputs': receipt['exact_outputs'],
                      'binary_sha256': receipt['binary_sha256']}))


if __name__ == '__main__':
    main()
