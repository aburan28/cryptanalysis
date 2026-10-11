"""Exact list-free completion of a supplied N41 left pair output."""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))
import run as base  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True)+'\n')


def sources():
    return {'linear_oracle.py': HERE/'linear_oracle.py',
            'cut_protocol.json': HERE/'protocol.json',
            'parent_protocol.json': PARENT/'protocol.json',
            'native_panel': base.PANEL,
            'native_sage_replay': base.circuit.ROOT/'n41_direct_relaxed_pair_join_20261011/sage_replay.json',
            'field': base.circuit.ROOT/'n41_single_branch_horner_20261011/circuit.py'}


def trace(field, value):
    out = 0
    for _ in range(41):
        out ^= value
        value = field.square(value)
    assert out in (0, 1)
    return out


def halftrace(field, value):
    out = 0
    for _ in range(21):
        out ^= value
        value = field.square(field.square(value))
    return out


def on_curve(field, point):
    if point is None:
        return True
    x, y = point
    return field.square(y) ^ field.mul(x, y) == field.mul(field.square(x), x) ^ 1


def neg(point):
    return None if point is None else (point[0], point[0] ^ point[1])


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
    result = (x3, y3)
    assert on_curve(field, result)
    return result


def lift(field, reciprocal):
    assert reciprocal
    x = field.inv(reciprocal)
    rhs = x ^ field.square(reciprocal)
    assert trace(field, rhs) == 0
    u = halftrace(field, rhs)
    assert field.square(u) ^ u == rhs
    point = (x, field.mul(x, u))
    assert on_curve(field, point)
    return point


def linear_solve(columns, rhs):
    pivots = {}
    kernel = []
    for index, column in enumerate(columns):
        value, representation = column, 1 << index
        while value:
            bit = value.bit_length()-1
            if bit in pivots:
                pivot, mask = pivots[bit]
                value ^= pivot
                representation ^= mask
            else:
                pivots[bit] = (value, representation)
                break
        if not value:
            kernel.append(representation)
    solution = 0
    while rhs:
        bit = rhs.bit_length()-1
        if bit not in pivots:
            return None, len(pivots), kernel
        value, representation = pivots[bit]
        rhs ^= value
        solution ^= representation
    return solution, len(pivots), kernel


def pair_inverse(field, z, rotation=30):
    if not z or trace(field, z):
        return {'status': 'NO_MEMBER', 'rank': None, 'kernel_dimension': None}
    seed_basis = [field.frob(1 << (i+1), rotation) for i in range(6)]
    product_basis = [field.frob(1 << (i+2), rotation) for i in range(11)]
    columns = [halftrace(field, field.square(value)) for value in seed_basis]
    columns += [field.mul(value, z) for value in product_basis]
    columns += [1]
    particular, rank, kernel = linear_solve(columns, halftrace(field, field.square(z)))
    if particular is None:
        return {'status': 'NO_MEMBER', 'rank': rank, 'kernel_dimension': len(kernel)}
    # Exclude the zero seed sum without enumerating the affine solution space.
    chosen = particular
    if chosen & 63 == 0:
        chosen = next((particular ^ vector for vector in kernel if vector & 63), None)
    if chosen is None:
        return {'status': 'NO_MEMBER', 'rank': rank, 'kernel_dimension': len(kernel)}
    seed = chosen & 63
    product = (chosen >> 6) & 2047
    branch = (chosen >> 17) & 1
    s = 0
    p = 0
    for i, value in enumerate(seed_basis):
        if seed >> i & 1:
            s ^= value
    for i, value in enumerate(product_basis):
        if product >> i & 1:
            p ^= value
    assert seed and field.mul(p, z) ^ halftrace(field, field.square(s ^ z)) ^ branch == 0
    return {'status': 'RELAXED_PAIR_MEMBER', 'rank': rank,
            'kernel_dimension': len(kernel), 'seed_sum': seed,
            'product_mask': product, 'branch': branch, 'reciprocal_z': z}


def freeze():
    cut = json.loads((HERE/'protocol.json').read_text())
    assert cut['status'] == 'FROZEN_BEFORE_OUTPUT_CUT_CONTROL_AND_QUERIES'
    protocol = {'status': 'FROZEN_BEFORE_LINEAR_COMPLETION_PANEL',
                'candidate_id': None, 'first_pair_reciprocal_z': cut['first_pair_reciprocal_z'],
                'targets': cut['targets'], 'right_rotation': 30,
                'input_law': 'one fixed known-positive left reciprocal; two frozen target residuals',
                'source_sha256': {name: sha(path) for name, path in sources().items()}}
    save(HERE/'linear_protocol.json', protocol)
    print(json.dumps({'status': protocol['status']}))


def run():
    protocol = json.loads((HERE/'linear_protocol.json').read_text())
    assert protocol['source_sha256'] == {name: sha(path) for name, path in sources().items()}
    field = base.circuit.old.Field()
    left = lift(field, protocol['first_pair_reciprocal_z'])
    panel = base.panel()
    results = []
    for label in ('positive', 'control_0'):
        target = tuple(protocol['targets'][label])
        assert on_curve(field, target)
        began = time.perf_counter_ns()
        signs = []
        for left_point in (left, neg(left)):
            right = add(field, target, neg(left_point))
            if right is None or not right[0]:
                signs.append({'status': 'EXCEPTIONAL_OUTPUT', 'left_point': left_point})
                continue
            z = field.inv(right[0])
            inverse = pair_inverse(field, z)
            if inverse['status'] == 'RELAXED_PAIR_MEMBER':
                assert add(field, left_point, right) == target
            signs.append({'left_point': left_point, 'right_point': right,
                          'inverse': inverse})
        elapsed = time.perf_counter_ns()-began
        hits = sum(x.get('inverse', {}).get('status') == 'RELAXED_PAIR_MEMBER'
                   for x in signs)
        exact = next(x for x in panel['queries'] if x['label'] == label)
        assert (hits > 0) == (exact['status'] == 'RELAXED_SUM_HIT')
        results.append({'label': label, 'target': target, 'status':
                        'RELAXED_SUM_HIT' if hits else 'COMPLETE_RELAXED_NO_SUM',
                        'signs': signs, 'hit_signs': hits,
                        'target_dependent_ns_exploratory': elapsed,
                        'exact_panel_status': exact['status']})
    record = {'status': 'PASS_SUPPLIED_OUTPUT_COMPLETION_PANEL',
              'candidate_id': None, 'left_point': left,
              'left_reciprocal_z': protocol['first_pair_reciprocal_z'],
              'queries': results,
              'source_sha256': {'linear_protocol.json': sha(HERE/'linear_protocol.json')}}
    save(HERE/'linear_result.json', record)
    print(json.dumps({'status': record['status'],
                      'queries': [(x['label'], x['status'], x['target_dependent_ns_exploratory'])
                                  for x in results]}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('freeze', 'run'))
    {'freeze': freeze, 'run': run}[parser.parse_args().mode]()
