"""Independent N131 group lift of an unpinned Boolean model."""

import hashlib
import importlib.util
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path('/Volumes/SSD990/cryptanalysis/experiments/ecc2k130-ic-goal-20260929')
OLD = ROOT / 'n41_basis_aware_quartic_20261011/replay.py'
spec = importlib.util.spec_from_file_location('independent_field_replay', OLD)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)


class Field(old.Field):
    n = 131
    modulus = (1 << 131) | (1 << 13) | (1 << 2) | (1 << 1) | 1


def scalar(field, point, k):
    result = None
    while k:
        if k & 1:
            result = old.add(field, result, point)
        point = old.add(field, point, point)
        k >>= 1
    return result


def source(field, mask, rotation):
    w = mask << 1
    x = field.inv(w)
    v = field.halftrace(x ^ field.square(w))
    point = x, field.mul(x, v)
    assert old.on_curve(field, point)
    for _ in range(rotation):
        point = field.square(point[0]), field.square(point[1])
    return point


def main():
    model_path = HERE/'model_decoded.json'
    model = json.loads(model_path.read_text())
    protocol = json.loads((HERE/'protocol.json').read_text())
    public = json.loads((ROOT/'n131_fixed_seed_eight_pair_circuit_20261010/target_preimages.json').read_text())
    assert model['target'] == protocol['public_target'] == public['public_target']
    field = Field()
    columns = {int(a): int(b) for a, b in
               (line.split() for line in
                (ROOT/'n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv')
                .read_text().splitlines())}
    masks = model['masks']
    assert len(masks) == 8 and all(mask in columns for mask in masks)
    folded = [columns[mask] for mask in masks]
    assert len(set(folded)) == 8
    plus = [source(field, mask, rotation)
            for mask, rotation in zip(masks, protocol['rotations'])]
    choices = [(point, (point[0], point[1] ^ point[0])) for point in plus]
    pair_options = []
    for i in range(4):
        wanted = model['pair_reciprocals'][i]
        found = []
        for signs in itertools.product((0, 1), repeat=2):
            a, b = choices[2*i][signs[0]], choices[2*i+1][signs[1]]
            total = old.add(field, a, b)
            if total is not None and total[0] and field.inv(total[0]) == wanted:
                found.append((total, signs, (a, b)))
        pair_options.append(found)
    flag_code = model['raw_preimage_index']
    assert 0 <= flag_code < 4
    raw_index = 2 * (flag_code & 1) + (flag_code >> 1)
    raw_target = tuple(public['preimages'][raw_index]['point'])
    target = tuple(public['public_target'])
    verified = []
    for selected in itertools.product(*pair_options):
        middle = [old.add(field, selected[2*i][0], selected[2*i+1][0])
                  for i in range(2)]
        if any(point is None or point[0] == 0 for point in middle):
            continue
        if [field.inv(point[0]) for point in middle] != model['middle_reciprocals']:
            continue
        raw_sum = old.add(field, middle[0], middle[1])
        if raw_sum != raw_target:
            continue
        assert scalar(field, raw_sum, 4) == target
        leaves = [point for item in selected for point in item[2]]
        assert scalar(field, sum_points(field, leaves), 4) == target
        verified.append({'raw_sum': raw_sum, 'raw_leaves': leaves,
                         'signs': [sign for item in selected for sign in item[1]]})
    result = {'status': 'PASS_VERIFIED_N131_PUBLIC_RELATION' if verified else 'NO_GROUP_LIFT',
              'target': target, 'masks': masks, 'folded_columns': folded,
              'raw_preimage_index': raw_index,
              'pair_option_counts': [len(items) for items in pair_options],
              'verified_relations': verified,
              'source_sha256': {'replay.py': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                'model_decoded.json': hashlib.sha256(model_path.read_bytes()).hexdigest()}}
    (HERE/'replay_result.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'status': result['status'],
                      'pair_option_counts': result['pair_option_counts'],
                      'verified_relation_count': len(verified)}))


def sum_points(field, points):
    total = None
    for point in points:
        total = old.add(field, total, point)
    return total


if __name__ == '__main__':
    main()
