#!/usr/bin/env python3
"""Minimize unit rotations without changing a certified graph's vertex order."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from root_first_plan import unit


def best_witness(target, orbit):
    options = []
    for bit in range(8):
        for basis in range(2):
            power = ((1 << bit, 0) if basis == 0 else (0, 1 << bit))
            for step_unit in range(6):
                delta = unit(power, step_unit)
                parent = orbit.get((target[0] - delta[0], target[1] - delta[1]))
                if parent is not None:
                    seed, parent_unit = parent
                    op = ['step', *seed, parent_unit, basis, bit, step_unit]
                    options.append((int(parent_unit >= 2) + int(step_unit >= 2),
                                    0, bit, op))
    for coefficient, (left, left_unit) in orbit.items():
        right = orbit.get((target[0] - coefficient[0],
                           target[1] - coefficient[1]))
        if right is not None:
            right_seed, right_unit = right
            op = ['sum', *left, left_unit, *right_seed, right_unit]
            options.append((int(left_unit >= 2) + int(right_unit >= 2),
                            1, 0, op))
    return min(options, default=None)


def refine(source):
    rows = source['graph']['nodes']
    orbit, nodes = {}, []
    before = after = changed = 0
    for a, b, op in rows:
        target = (a, b)
        if op[0] != 'direct':
            original_rotations = int(op[3] >= 2) + int(op[6] >= 2)
            before += original_rotations
            candidate = best_witness(target, orbit)
            if candidate is not None and candidate[0] < original_rotations:
                op = candidate[3]
                changed += 1
            after += int(op[3] >= 2) + int(op[6] >= 2)
        nodes.append([a, b, op])
        for code in range(6):
            coefficient = unit(target, code)
            assert coefficient not in orbit, 'duplicate unit orbit'
            orbit[coefficient] = (target, code)
    result = dict(source)
    result['graph'] = dict(source['graph'], nodes=nodes)
    return result, {'count': source['count'], 'constructed_vertices': len(nodes),
                    'rewired_edges': changed, 'rotations_before': before,
                    'rotations_after': after}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    source_bytes = args.source.read_bytes()
    result, receipt = refine(json.loads(source_bytes))
    output = json.dumps(result, sort_keys=True, indent=2) + '\n'
    args.output.write_text(output)
    receipt.update(schema=1, source_plan_sha256=sha256(source_bytes).hexdigest(),
                   output_plan_sha256=sha256(output.encode()).hexdigest())
    args.receipt.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
