#!/usr/bin/env python3
"""Freeze same-binary OpenSSL versus target-charged joint-rho panels."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import tarfile
from tempfile import TemporaryDirectory

from native_rho_restart_joint_overlay import main as apply_overlay

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / 'rho-restart-hybrid-native-provenance.tar.gz'
SOURCE = Path('/workspace/bench-sources/prime-j0-rho-restart-joint')
BINARY = Path('/workspace/bench-target-rho-restart-joint/release/eisenstein_fixed')
PANELS = Path('/workspace/isolated-bench/panels')
LIBCRYPTO = Path('/usr/lib/x86_64-linux-gnu/libcrypto.so.3')


def digest(data):
    return sha256(data).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def archived_bytes(member):
    with tarfile.open(ARCHIVE) as archive:
        return archive.extractfile(member).read()


def expected_hashes(binary_hash, libcrypto_hash):
    stem = 'workspace/bench-sources/prime-j0-rho-restart-hybrid/'
    with TemporaryDirectory(prefix='rho-joint-plan-source-') as temp:
        root = Path(temp)
        names = ('Cargo.toml', 'Cargo.lock', 'src/bin/eisenstein_fixed.rs',
                 'src/bin/eisenstein_fixed/unit_orbit_windows.rs',
                 'src/bin/rho_restart_hybrid.rs')
        for name in names:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archived_bytes(stem + name))
        apply_overlay(root)
        hashes = {
            'cargo_toml': digest((root / 'Cargo.toml').read_bytes()),
            'cargo_lock': digest((root / 'Cargo.lock').read_bytes()),
            'front': digest((root / 'src/bin/eisenstein_fixed.rs').read_bytes()),
            'windows': digest((root / 'src/bin/eisenstein_fixed/unit_orbit_windows.rs').read_bytes()),
            'hybrid': digest((root / 'src/bin/rho_restart_hybrid.rs').read_bytes()),
            'joint': digest((root / 'src/bin/rho_restart_joint.rs').read_bytes()),
            'joint_windows': digest((root / 'src/bin/eisenstein_fixed/joint_norm4033.rs').read_bytes()),
        }
    hashes.update({
        'binary': binary_hash,
        'libcrypto': libcrypto_hash,
        'fixture': digest((HERE / 'rho-restart-first128-fixture.json').read_bytes()),
        'overlay': digest((HERE / 'native_rho_restart_joint_overlay.py').read_bytes()),
        'ct_bignum': digest(archived_bytes('workspace/bench-sources/public-inputs/suite/src/ct_bignum.rs')),
    })
    return hashes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary-sha256', required=True)
    parser.add_argument('--libcrypto-sha256', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    for value in (args.binary_sha256, args.libcrypto_sha256):
        assert re.fullmatch('[0-9a-f]{64}', value), 'SHA-256 must be lowercase hex'
    args.output_dir.mkdir(parents=True, exist_ok=True)
    hashes = expected_hashes(args.binary_sha256, args.libcrypto_sha256)
    paths = {
        'binary': str(BINARY), 'libcrypto': str(LIBCRYPTO),
        'fixture': str(PANELS / 'rho-restart-first128-fixture.json'),
        'overlay': str(PANELS / 'native_rho_restart_joint_overlay.py'),
        'ct_bignum': '/workspace/bench-sources/public-inputs/suite/src/ct_bignum.rs',
        'cargo_toml': str(SOURCE / 'Cargo.toml'),
        'cargo_lock': str(SOURCE / 'Cargo.lock'),
        'front': str(SOURCE / 'src/bin/eisenstein_fixed.rs'),
        'windows': str(SOURCE / 'src/bin/eisenstein_fixed/unit_orbit_windows.rs'),
        'hybrid': str(SOURCE / 'src/bin/rho_restart_hybrid.rs'),
        'joint': str(SOURCE / 'src/bin/rho_restart_joint.rs'),
        'joint_windows': str(SOURCE / 'src/bin/eisenstein_fixed/joint_norm4033.rs'),
    }
    fixture = json.loads((HERE / 'rho-restart-first128-fixture.json').read_text())
    assert len(fixture['cases']) >= 128
    boundary = ('OpenSSL nowarm times its first EC_POINT_mul(aG+bQ) and affine output; '
                'its Q parsing and group setup are outside. Joint demand/fused exclude '
                'globally reusable G and canonical-seed preparation but include b recoding, '
                'Q parsing/table construction, all a recoding, pair fusion where selected, '
                'Horner evaluation, and affine output. Fixture parsing and process launch are outside.')
    for count in (1, 128):
        stem = f'tier1-rho-joint-{count}-cpu40'
        expected = fixture['cases'][count - 1]['point_hex']
        ref = [str(BINARY), '--pilot-rho-restart', 'openssl_nowarm', paths['fixture'], str(count)]
        demand = [str(BINARY), '--pilot-rho-restart-joint-demand', paths['fixture'], str(count)]
        fused = [str(BINARY), '--pilot-rho-restart-joint-fused', paths['fixture'], str(count)]
        cases = []
        for name, candidate in (
            ('cal_before', ref), ('compare_demand', demand), ('cal_mid', ref),
            ('compare_fused', fused), ('cal_after', ref),
        ):
            cases.append({'id': name, 'reference': ref, 'candidate': candidate,
                          'expected_fields': {'count': str(count)},
                          'expected_result': expected})
        rules = {
            'schema': 1, 'purpose': f'rho-joint-target-charged-{count}',
            'tier': 'tier1_instance', 'service_cpu': 2, 'execution_cpu': 40,
            'expected_count': count, 'expected_point_hex': expected,
            'q_hex': fixture['q_hex'], 'fixture_sha256': hashes['fixture'],
            'repetitions': 16, 'aa_acceptance': [0.90, 1.11],
            'case_order': [case['id'] for case in cases],
            'comparison_acceptance': ('all 16 pairs per comparison valid; three adjacent '
                                      'OpenSSL A/A controls within [0.90,1.11]; paired '
                                      'bootstrap 95% log-ratio interval excludes one'),
            'timing_boundary': boundary, 'paths': paths, 'hashes': hashes,
        }
        rule_name = stem + '-rules.json'
        manifest = {
            'schema': 1, 'measurement_tier': 'tier1_instance',
            'allocation': {'provider': 'runpod', 'instance_id': 'thyvmdqmzsz5ik',
                           'receipt': str(PANELS / 'allocation.json')},
            'isolation': {'cpus': '40', 'execution_cpu': 40},
            'workdir': '/workspace/bench-sources', 'repetitions': 16,
            'outer_repeats': 1, 'timeout_s': 30,
            'measurement_boundary': boundary, 'pair_fields': ['count', 'point'],
            'comparison_variant': f'rho-joint-target-charged-{count}',
            'cases': cases,
            'artifacts': [str(PANELS / 'allocation.json'), str(PANELS / 'host-probe.json'),
                          *paths.values(), str(PANELS / rule_name)],
        }
        write(args.output_dir / rule_name, rules)
        write(args.output_dir / (stem + '-manifest.json'), manifest)
    print(json.dumps({'ok': True, 'panels': [1, 128], 'source_hashes': hashes}, sort_keys=True))


if __name__ == '__main__':
    main()
