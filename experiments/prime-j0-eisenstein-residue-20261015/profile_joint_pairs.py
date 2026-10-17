#!/usr/bin/env python3
"""Record exact norm-4033 joint-digit reuse on the frozen rho scalar stream."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    fixture = HERE / 'rho-restart-first128-fixture.json'
    receipt = {
        'schema': 1, 'purpose': 'combinatorial_digit_pair_profile',
        'fixture_sha256': digest(fixture),
        'binary_sha256': digest(args.binary),
        'component_sha256': {name: digest(HERE / name) for name in
                             ('rho_restart_joint.rs', 'joint_norm4033.rs',
                              'native_rho_restart_joint_overlay.py')},
        'runs': [],
    }
    for count in (1, 128):
        command = [str(args.binary), '--pilot-rho-restart-joint-profile',
                   str(fixture), str(count)]
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == 0 and result.stderr == '', result.stderr
        data = json.loads(result.stdout)
        assert data['schema'] == 1 and data['count'] == count
        assert (data['g_only'] + data['q_only'] + data['neither']
                + data['both_digit'] + data['both_terminal'] == 23*count)
        assert data['digit_unique_common_unit_orbit'] <= data['digit_unique_raw']
        assert data['digit_unique_raw'] <= data['both_digit']
        assert data['terminal_unique_common_unit_orbit'] <= data['terminal_unique_raw']
        assert data['terminal_unique_raw'] <= data['both_terminal']
        assert (data['digit_precompute_addition_savings_upper_bound'] ==
                data['both_digit'] - data['digit_unique_common_unit_orbit'])
        data.pop('q_digit_seeds')
        data.pop('q_terminal_seeds')
        receipt['runs'].append(data)
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'ok': True, 'counts': [run['count'] for run in receipt['runs']]},
                     sort_keys=True))


if __name__ == '__main__':
    main()
