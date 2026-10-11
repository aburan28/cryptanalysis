"""Construct an eight-slot exact group witness for circuit validation."""

import json
from pathlib import Path

import circuit

HERE = Path(__file__).resolve().parent
MASKS = (3, 4, 17, 18, 19, 22, 24, 25)


def add(field, left, right):
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2:
        if y1 ^ y2 == x1:
            return None
        assert left == right and x1
        slope = x1 ^ field.mul(y1, field.inv(x1))
        x3 = field.square(slope) ^ slope
        y3 = field.square(x1) ^ field.mul(slope ^ 1, x3)
    else:
        slope = field.mul(y1 ^ y2, field.inv(x1 ^ x2))
        x3 = field.square(slope) ^ slope ^ x1 ^ x2
        y3 = field.mul(slope, x1 ^ x3) ^ x3 ^ y1
    return x3, y3


def on_curve(field, point):
    x, y = point
    return field.square(y) ^ field.mul(x, y) == field.mul(field.square(x), x) ^ 1


def source(field, mask, rotation):
    w = mask << 1
    x = field.inv(w)
    rhs = x ^ field.square(w)
    assert circuit.old.trace(field, rhs) == 0
    v = circuit.old.halftrace(field, rhs)
    assert field.square(v) ^ v == rhs
    point = x, field.mul(x, v)
    assert on_curve(field, point)
    for _ in range(rotation):
        point = field.square(point[0]), field.square(point[1])
    assert on_curve(field, point)
    return point


def branch(field, a, b, c):
    rhs = field.square(a ^ b ^ c)
    assert circuit.old.trace(field, rhs) == 0
    bit = field.mul(field.mul(a, b), c) ^ circuit.old.halftrace(field, rhs)
    assert bit in (0, 1)
    return bit


def main():
    field = circuit.Field()
    columns = {int(a): int(b) for a, b in
               (line.split() for line in
                (circuit.ROOT / 'n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv')
                .read_text().splitlines())}
    assert all(mask in columns for mask in MASKS)
    assert len({columns[mask] for mask in MASKS}) == 8
    leaves = [source(field, mask, rotation)
              for mask, rotation in zip(MASKS, circuit.ROTATIONS)]
    pairs = [add(field, leaves[2*i], leaves[2*i+1]) for i in range(4)]
    middle = [add(field, pairs[2*i], pairs[2*i+1]) for i in range(2)]
    total = add(field, middle[0], middle[1])
    assert all(point is not None and point[0] for point in [*pairs, *middle, total])
    target = add(field, total, total)
    target = add(field, target, target)
    assert target is not None and on_curve(field, target)
    pair_z = [field.inv(point[0]) for point in pairs]
    middle_z = [field.inv(point[0]) for point in middle]
    total_z = field.inv(total[0])
    leaf_z = [field.inv(point[0]) for point in leaves]
    branches = [branch(field, leaf_z[2*i], leaf_z[2*i+1], pair_z[i])
                for i in range(4)]
    branches += [branch(field, pair_z[2*i], pair_z[2*i+1], middle_z[i])
                 for i in range(2)]
    branches += [branch(field, middle_z[0], middle_z[1], total_z)]
    record = {'status': 'PASS_CONSTRUCTED_EIGHT_SLOT_GROUP_WITNESS',
              'curve_id': 'EC1N131Ckb1heb5f1998f20b',
              'masks': MASKS, 'columns': [columns[mask] for mask in MASKS],
              'rotations': circuit.ROTATIONS, 'raw_leaves': leaves,
              'pair_points': pairs, 'middle_points': middle,
              'raw_target': total, 'projected_target': target,
              'leaf_reciprocals': leaf_z, 'pair_reciprocals': pair_z,
              'middle_reciprocals': middle_z, 'raw_target_reciprocal': total_z,
              'branch_bits': branches}
    (HERE / 'fixture.json').write_text(json.dumps(record, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'status': record['status'], 'target': target,
                      'raw_target_reciprocal': total_z}))


if __name__ == '__main__':
    main()
