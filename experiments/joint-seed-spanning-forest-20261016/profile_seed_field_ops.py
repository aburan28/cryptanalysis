#!/usr/bin/env python3
"""Count source-level generic-path field operations in frozen Q-seed plans."""
from hashlib import sha256
import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'prime-j0-eisenstein-residue-20261015'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def profile(path, requested=None):
    nodes = json.loads(path.read_bytes())['graph']['nodes']
    normalized = len(nodes) if requested is None else sum(
        (a, b) in requested for a, b, _ in nodes)
    direct_calls = full_adds = mixed_adds = rotations = direct_roots = special_unit_roots = 0
    known_affine = set()
    for a, b, op in nodes:
        if op[0] == 'direct':
            direct_roots += 1
            if (a, b) == (-2, 1):
                # The planned native graph uses omega^2 of prepared Q.
                special_unit_roots += 1
                rotations += 1
                known_affine.add((a, b))
                continue
            calls = abs(a).bit_count() + abs(b).bit_count()
            assert calls > 0
            direct_calls += calls
            full_adds += calls - 1  # first add returns from identity
            if (a, b) in ((1, 0), (-1, 0)):
                known_affine.add((a, b))
        elif op[0] == 'step':
            full_adds += 1
            mixed_adds += int((op[1], op[2]) in known_affine or
                              (op[4] == 0 and op[5] == 0))
            rotations += int(op[3] >= 2) + int(op[6] >= 2)
        elif op[0] == 'sum':
            full_adds += 1
            mixed_adds += int((op[1], op[2]) in known_affine or
                              (op[4], op[5]) in known_affine)
            rotations += int(op[3] >= 2) + int(op[6] >= 2)
        else:
            raise AssertionError(op)
    graph_edges = len(nodes) - direct_roots
    return {
        'plan_sha256': digest(path), 'constructed_vertices': len(nodes),
        'normalized_vertices': normalized,
        'direct_roots': direct_roots, 'direct_add_projective_calls': direct_calls,
        'special_unit_roots': special_unit_roots,
        'graph_edge_calls': graph_edges,
        'total_add_calls': direct_calls + graph_edges,
        'total_add_projective_calls': direct_calls + graph_edges - mixed_adds,
        'identity_return_calls': direct_roots - special_unit_roots,
        'full_adds': full_adds,
        'generic_full_adds': full_adds - mixed_adds,
        'mixed_adds': mixed_adds,
        'nontrivial_unit_rotations': rotations,
        'modeled_field_muls': 12*(full_adds-mixed_adds) + 8*mixed_adds
                              + rotations + 6*normalized,
        'modeled_field_squares': 4*(full_adds-mixed_adds) + 3*mixed_adds
                                 + normalized,
        'shared_field_inversions': 1,
    }


def main():
    archive = BASE / 'rho-restart-hybrid-native-provenance.tar.gz'
    member = ('workspace/bench-sources/prime-j0-rho-restart-hybrid/'
              'src/bin/eisenstein_fixed/unit_orbit_windows.rs')
    with tarfile.open(archive) as source:
        windows = source.extractfile(member).read()
    from sys import path as syspath
    syspath.insert(0, str(BASE))
    from native_rho_restart_joint_overlay import WINDOWS_SHA256
    assert sha256(windows).hexdigest() == WINDOWS_SHA256
    rows = {}
    for count in (1, 128):
        requested = {tuple(row[:2]) for row in json.loads(
            (BASE / f'rho-joint-graph-plan-{count}.json').read_bytes()
        )['graph']['nodes']}
        plans = {
            'lexicographic': BASE / f'rho-joint-graph-plan-{count}.json',
            'root_first': HERE / f'root-first-plan-{count}.json',
            'two_parent': HERE / f'two-parent-plan-{count}.json',
            'auxiliary': HERE / f'steiner-plan-{count}.json',
            'weighted': HERE / f'weighted-plan-{count}.json',
        }
        if count == 1:
            plans['refined_auxiliary'] = HERE / 'refined-steiner-plan-1.json'
            plans['one_auxiliary'] = HERE / 'one-aux-plan-1.json'
            plans['unit_root'] = HERE / 'unit-root-plan-1.json'
        else:
            plans['refined_weighted'] = HERE / 'refined-weighted-plan-128.json'
        rows[str(count)] = {name: profile(path, requested) for name, path in plans.items()}
        assert len({row['shared_field_inversions'] for row in rows[str(count)].values()}) == 1
    receipt = {
        'schema': 1,
        'purpose': 'source_formula_model_not_wall_measurement',
        'source_archive_sha256': digest(archive),
        'base_windows_sha256': sha256(windows).hexdigest(),
        'joint_windows_sha256': digest(BASE / 'joint_norm4033.rs'),
        'formula': {
            'generic_full_add': '12 field multiplications + 4 field squares',
            'mixed_add': '8 field multiplications + 3 field squares when one nonidentity operand has Z=1',
            'nontrivial_projective_unit_rotation': '1 field multiplication',
            'batch_normalization_per_point': '6 field multiplications + 1 field square',
            'batch_normalization_shared': '1 field inversion',
        },
        'boundary': ('Q-seed graph construction and batch affine normalization; '
                     'shared binary-power doubling and inversion, scalar recoding, '
                     'plan loading, Q parsing, and restart evaluation are excluded'),
        'condition': ('generic add_projective path; source-level model does not '
                      'measure exceptional additions or wall time'),
        'rows': rows,
    }
    output = HERE / 'seed-field-op-model.json'
    output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    for count in (1,128):
        selected = 'auxiliary' if count == 1 else 'weighted'
        a, b = rows[str(count)]['lexicographic'], rows[str(count)][selected]
        print(count, selected, a['full_adds'], b['full_adds'],
              a['modeled_field_muls'] - b['modeled_field_muls'],
              a['modeled_field_squares'] - b['modeled_field_squares'])


if __name__ == '__main__':
    main()
