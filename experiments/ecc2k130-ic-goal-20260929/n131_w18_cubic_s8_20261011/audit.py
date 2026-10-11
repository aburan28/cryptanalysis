"""Independent source-domain and constructed group-witness audit."""

import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path

import circuit

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('n131_cubic_independent_replay', HERE/'replay.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)
SUPPORT = circuit.ROOT/'n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv'
R = 680564733841876926932320129493409985129


def accepts(root, nodes, value):
    node = root
    while node >= 2:
        bit, low, high = nodes[node]
        node = high if value >> bit & 1 else low
    return node == 1


def main():
    columns = {int(a): int(b) for a, b in
               (line.split() for line in SUPPORT.read_text().splitlines())}
    root, nodes = circuit.build_bdd(columns)
    mismatches = [value for value in range(1 << 18)
                  if accepts(root, nodes, value) != (value in columns)]
    assert not mismatches
    classes = Counter(columns.values())
    collisions = sum(size*(size-1)//2 for size in classes.values())
    assert collisions == 243
    fixture = json.loads((HERE/'fixture.json').read_text())
    field = replay.Field()
    leaves = [replay.source(field, mask, rotation)
              for mask, rotation in zip(fixture['masks'], fixture['rotations'])]
    assert [list(point) for point in leaves] == fixture['raw_leaves']
    pairs = [replay.old.add(field, leaves[2*i], leaves[2*i+1]) for i in range(4)]
    middle = [replay.old.add(field, pairs[2*i], pairs[2*i+1]) for i in range(2)]
    total = replay.old.add(field, middle[0], middle[1])
    assert [list(point) for point in pairs] == fixture['pair_points']
    assert [list(point) for point in middle] == fixture['middle_points']
    assert list(total) == fixture['raw_target']
    projected = replay.scalar(field, total, 4)
    assert list(projected) == fixture['projected_target']
    subgroup = [replay.scalar(field, replay.scalar(field, point, 4), R)
                for point in leaves]
    assert all(point is None for point in subgroup)
    result = {'status': 'PASS_EXACT_SOURCE_AND_GROUP_AUDIT',
              'bdd_nodes': len(nodes), 'mask_domain_checked': 1 << 18,
              'accepted_masks': len(columns), 'membership_disagreements': 0,
              'folded_columns': len(classes),
              'nontrivial_column_collision_pairs': collisions,
              'fixture_distinct_columns': len(set(fixture['columns'])),
              'fixture_raw_target': total,
              'fixture_projected_target': projected,
              'subgroup_points_checked': len(subgroup),
              'source_sha256': {'support_w18.tsv': hashlib.sha256(SUPPORT.read_bytes()).hexdigest(),
                                'fixture.json': hashlib.sha256((HERE/'fixture.json').read_bytes()).hexdigest(),
                                'audit.py': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}
    (HERE/'audit_result.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'status': result['status'],
                      'bdd_nodes': result['bdd_nodes'],
                      'mask_domain_checked': result['mask_domain_checked']}))


if __name__ == '__main__':
    main()
