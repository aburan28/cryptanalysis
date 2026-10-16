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
FOREST = HERE.parent / 'joint-seed-spanning-forest-20261016'
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
        'plan_1': digest((HERE / 'rho-joint-graph-plan-1.json').read_bytes()),
        'plan_128': digest((HERE / 'rho-joint-graph-plan-128.json').read_bytes()),
        'root_first_1': digest((FOREST / 'root-first-plan-1.json').read_bytes()),
        'root_first_128': digest((FOREST / 'root-first-plan-128.json').read_bytes()),
        'two_parent_1': digest((FOREST / 'two-parent-plan-1.json').read_bytes()),
        'two_parent_128': digest((FOREST / 'two-parent-plan-128.json').read_bytes()),
        'steiner_1': digest((FOREST / 'steiner-plan-1.json').read_bytes()),
        'steiner_128': digest((FOREST / 'steiner-plan-128.json').read_bytes()),
        'weighted_1': digest((FOREST / 'weighted-plan-1.json').read_bytes()),
        'weighted_128': digest((FOREST / 'weighted-plan-128.json').read_bytes()),
        'refined_1': digest((FOREST / 'refined-steiner-plan-1.json').read_bytes()),
        'refined_128': digest((FOREST / 'refined-weighted-plan-128.json').read_bytes()),
        'one_aux_1': digest((FOREST / 'one-aux-plan-1.json').read_bytes()),
        'unit_root_1': digest((FOREST / 'unit-root-plan-1.json').read_bytes()),
        'mixed_cost_128': digest((FOREST / 'mixed-cost-plan-128.json').read_bytes()),
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
        'plan_1': str(PANELS / 'rho-joint-graph-plan-1.json'),
        'plan_128': str(PANELS / 'rho-joint-graph-plan-128.json'),
        'root_first_1': str(PANELS / 'root-first-plan-1.json'),
        'root_first_128': str(PANELS / 'root-first-plan-128.json'),
        'two_parent_1': str(PANELS / 'two-parent-plan-1.json'),
        'two_parent_128': str(PANELS / 'two-parent-plan-128.json'),
        'steiner_1': str(PANELS / 'steiner-plan-1.json'),
        'steiner_128': str(PANELS / 'steiner-plan-128.json'),
        'weighted_1': str(PANELS / 'weighted-plan-1.json'),
        'weighted_128': str(PANELS / 'weighted-plan-128.json'),
        'refined_1': str(PANELS / 'refined-steiner-plan-1.json'),
        'refined_128': str(PANELS / 'refined-weighted-plan-128.json'),
        'one_aux_1': str(PANELS / 'one-aux-plan-1.json'),
        'unit_root_1': str(PANELS / 'unit-root-plan-1.json'),
        'mixed_cost_128': str(PANELS / 'mixed-cost-plan-128.json'),
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
                'its Q parsing and group setup are outside. Joint arms exclude globally '
                'reusable G and canonical-seed preparation, include Q parsing/table '
                'construction, a recoding, pair fusion where selected, Horner evaluation, '
                'and affine output. Direct and online graph arms include b recoding. '
                'Planned graph arms load a frozen Q-independent graph artifact '
                'before Q-dependent timing; plan_load_ms and plan_bytes are reported separately. '
                'Fixture parsing and process launch are outside.')
    for count in (1, 128):
        stem = f'tier1-rho-joint-{count}-cpu40'
        expected = fixture['cases'][count - 1]['point_hex']
        ref = [str(BINARY), '--pilot-rho-restart', 'openssl_nowarm', paths['fixture'], str(count)]
        demand = [str(BINARY), '--pilot-rho-restart-joint-demand', paths['fixture'], str(count)]
        graph = [str(BINARY), '--pilot-rho-restart-joint-graph', paths['fixture'], str(count)]
        graph_planned = [str(BINARY), '--pilot-rho-restart-joint-graph-planned',
                         paths['fixture'], str(count), paths[f'plan_{count}']]
        root_first = [str(BINARY), '--pilot-rho-restart-joint-graph-planned',
                      paths['fixture'], str(count), paths[f'root_first_{count}']]
        two_parent = [str(BINARY), '--pilot-rho-restart-joint-graph-planned',
                      paths['fixture'], str(count), paths[f'two_parent_{count}']]
        steiner = [str(BINARY), '--pilot-rho-restart-joint-graph-planned',
                   paths['fixture'], str(count), paths[f'steiner_{count}']]
        weighted = [str(BINARY), '--pilot-rho-restart-joint-graph-planned',
                    paths['fixture'], str(count), paths[f'weighted_{count}']]
        refined = [str(BINARY), '--pilot-rho-restart-joint-graph-planned',
                   paths['fixture'], str(count), paths[f'refined_{count}']]
        one_aux = ([str(BINARY), '--pilot-rho-restart-joint-graph-planned',
                    paths['fixture'], '1', paths['one_aux_1']] if count == 1 else None)
        unit_root = ([str(BINARY), '--pilot-rho-restart-joint-graph-planned',
                      paths['fixture'], '1', paths['unit_root_1']] if count == 1 else None)
        mixed_cost = ([str(BINARY), '--pilot-rho-restart-joint-graph-planned',
                       paths['fixture'], '128', paths['mixed_cost_128']] if count == 128 else None)
        prior = steiner if count == 1 else weighted
        fused = [str(BINARY), '--pilot-rho-restart-joint-fused', paths['fixture'], str(count)]
        fused_graph = [str(BINARY), '--pilot-rho-restart-joint-fused-graph',
                       paths['fixture'], str(count)]
        fused_graph_planned = [str(BINARY), '--pilot-rho-restart-joint-fused-graph-planned',
                               paths['fixture'], str(count), paths[f'plan_{count}']]
        cases = []
        for name, candidate in (
            ('cal_before', ref), ('compare_demand', demand),
            ('compare_graph', graph), ('compare_graph_planned', graph_planned),
            ('compare_root_first', root_first), ('compare_weighted', weighted),
            ('compare_weighted_vs_root_first', weighted),
            ('compare_two_parent', two_parent),
            ('compare_two_parent_vs_root_first', two_parent),
            ('compare_steiner', steiner),
            ('compare_steiner_vs_two_parent', steiner),
            ('compare_refined', refined),
            ('compare_refined_vs_prior', refined),
            *([('compare_one_aux', one_aux),
               ('compare_one_aux_vs_refined', one_aux),
               ('compare_unit_root', unit_root),
               ('compare_unit_root_vs_one_aux', unit_root)] if count == 1 else []),
            *([('compare_mixed_cost', mixed_cost),
               ('compare_mixed_cost_vs_weighted', mixed_cost)] if count == 128 else []),
            ('cal_mid', ref),
            ('compare_fused', fused), ('compare_fused_graph', fused_graph),
            ('compare_fused_graph_planned', fused_graph_planned),
            ('cal_after', ref),
        ):
            paired_ref = (root_first if name in
                          ('compare_two_parent_vs_root_first',
                           'compare_weighted_vs_root_first')
                          else two_parent if name == 'compare_steiner_vs_two_parent'
                          else prior if name == 'compare_refined_vs_prior'
                          else refined if name == 'compare_one_aux_vs_refined'
                          else one_aux if name == 'compare_unit_root_vs_one_aux'
                          else weighted if name == 'compare_mixed_cost_vs_weighted'
                          else ref)
            cases.append({'id': name, 'reference': paired_ref, 'candidate': candidate,
                          'expected_fields': {'count': str(count)},
                          'expected_result': expected})
        rules = {
            'schema': 1, 'purpose': f'rho-joint-target-charged-{count}',
            'tier': 'tier1_instance', 'service_cpu': 2, 'execution_cpu': 40,
            'expected_count': count, 'expected_point_hex': expected,
            'q_hex': fixture['q_hex'], 'fixture_sha256': hashes['fixture'],
            'repetitions': 16, 'aa_acceptance': [0.90, 1.11],
            'case_order': [case['id'] for case in cases],
            'comparison_acceptance': ('all 16 pairs per comparison valid; three bracketing '
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
