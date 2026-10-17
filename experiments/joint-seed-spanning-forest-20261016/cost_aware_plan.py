#!/usr/bin/env python3
"""Choose minimum source-formula witnesses in a fixed 128-restart graph order."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from root_first_plan import unit


def witness_cost(op, known_affine):
    rotations = int(op[3] >= 2) + int(op[6] >= 2)
    if op[0] == 'step':
        mixed = (op[1], op[2]) in known_affine or (op[4] == 0 and op[5] == 0)
    else:
        assert op[0] == 'sum'
        mixed = (op[1], op[2]) in known_affine or (op[4], op[5]) in known_affine
    return 12 - 4 * int(mixed) + rotations, 4 - int(mixed), rotations, int(mixed)


def witnesses(target, orbit):
    a, b = target
    for bit in range(8):
        for basis in range(2):
            power = ((1 << bit, 0) if basis == 0 else (0, 1 << bit))
            for step_unit in range(6):
                delta = unit(power, step_unit)
                parent = orbit.get((a - delta[0], b - delta[1]))
                if parent is not None:
                    seed, parent_unit = parent
                    yield ['step', *seed, parent_unit, basis, bit, step_unit]
    for coefficient, (left, left_unit) in orbit.items():
        right = orbit.get((a - coefficient[0], b - coefficient[1]))
        if right is not None:
            seed, right_unit = right
            yield ['sum', *left, left_unit, *seed, right_unit]


def optimize(source):
    assert source['count'] == 128
    rows = source['graph']['nodes']
    orbit, known_affine, selected = {}, set(), []
    before = [0, 0, 0, 0]
    after = [0, 0, 0, 0]
    changed = 0
    for a, b, op in rows:
        target = a, b
        if op[0] == 'direct':
            if target in ((-2, 1), (1, 0), (-1, 0)):
                known_affine.add(target)
        else:
            choices = list(witnesses(target, orbit))
            assert choices, target
            chosen = min(choices, key=lambda candidate:
                         (*witness_cost(candidate, known_affine)[:3], candidate))
            old_cost = witness_cost(op, known_affine)
            new_cost = witness_cost(chosen, known_affine)
            assert new_cost[:2] <= old_cost[:2]
            before = [x + y for x, y in zip(before, old_cost)]
            after = [x + y for x, y in zip(after, new_cost)]
            changed += chosen != op
            op = chosen
        selected.append([a, b, op])
        for code in range(6):
            coefficient = unit(target, code)
            assert coefficient not in orbit
            orbit[coefficient] = target, code
    result = dict(source)
    result['graph'] = dict(source['graph'], nodes=selected)
    receipt = {'schema': 1, 'count': 128, 'constructed_vertices': len(selected),
               'rewired_edges': changed,
               'edge_field_muls_before': before[0], 'edge_field_muls_after': after[0],
               'edge_field_squares_before': before[1], 'edge_field_squares_after': after[1],
               'edge_rotations_before': before[2], 'edge_rotations_after': after[2],
               'mixed_edges_before': before[3], 'mixed_edges_after': after[3],
               'search_domain': 'all valid one-power and two-parent witnesses for each vertex in the frozen weighted-plan order; independent minimum source-formula edge cost'}
    return result, receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    source_bytes = args.source.read_bytes()
    result, receipt = optimize(json.loads(source_bytes))
    output = json.dumps(result, sort_keys=True, indent=2) + '\n'
    args.output.write_text(output)
    receipt['source_plan_sha256'] = sha256(source_bytes).hexdigest()
    receipt['output_plan_sha256'] = sha256(output.encode()).hexdigest()
    args.receipt.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
