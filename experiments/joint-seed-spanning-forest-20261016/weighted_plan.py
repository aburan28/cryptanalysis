#!/usr/bin/env python3
"""Grow Q-seed components by low-rotation unit-power edges."""
import argparse
from collections import defaultdict
from hashlib import sha256
import heapq
import json
from pathlib import Path

from root_first_plan import direct_cost, unit


def arcs_for(seeds):
    arcs = {seed: {} for seed in seeds}
    for parent in sorted(seeds):
        for parent_unit in range(6):
            p = unit(parent, parent_unit)
            for bit in range(8):
                for basis in range(2):
                    power = ((1 << bit, 0) if basis == 0 else (0, 1 << bit))
                    for step_unit in range(6):
                        q = unit(power, step_unit)
                        target = p[0] + q[0], p[1] + q[1]
                        if target not in seeds or target == parent:
                            continue
                        witness = (int(parent_unit >= 2) + int(step_unit >= 2),
                                   bit, parent_unit, basis, step_unit)
                        if target not in arcs[parent] or witness < arcs[parent][target]:
                            arcs[parent][target] = witness
    assert all(parent in arcs[target] for parent, links in arcs.items()
               for target in links)
    return arcs


def components_for(seeds, arcs):
    undirected = defaultdict(set)
    for parent, targets in arcs.items():
        for target in targets:
            undirected[parent].add(target)
            undirected[target].add(parent)
    unseen, components = set(seeds), []
    while unseen:
        first = min(unseen)
        stack, component = [first], set()
        unseen.remove(first)
        while stack:
            parent = stack.pop()
            component.add(parent)
            for target in sorted(undirected[parent] & unseen):
                unseen.remove(target)
                stack.append(target)
        components.append(component)
    return components


def weighted(source):
    original = source['graph']['nodes']
    seeds = {tuple(row[:2]) for row in original}
    assert len(seeds) == len(original)
    arcs = arcs_for(seeds)
    components = components_for(seeds, arcs)
    nodes, seen, roots = [], set(), []
    for component in components:
        root = min(component, key=lambda pair: (direct_cost(pair), pair))
        roots.append(root)
        nodes.append([*root, ['direct']])
        seen.add(root)
        frontier = []

        def offer(parent):
            for target, witness in arcs[parent].items():
                if target in component and target not in seen:
                    heapq.heappush(frontier, (witness, target, parent))

        offer(root)
        while frontier:
            witness, target, parent = heapq.heappop(frontier)
            if target in seen:
                continue
            _, bit, parent_unit, basis, step_unit = witness
            p = unit(parent, parent_unit)
            q = unit(((1 << bit, 0) if basis == 0 else (0, 1 << bit)),
                     step_unit)
            assert target == (p[0] + q[0], p[1] + q[1])
            nodes.append([*target, ['step', *parent, parent_unit,
                                     basis, bit, step_unit]])
            seen.add(target)
            offer(target)
        assert component <= seen
    assert seen == seeds
    result = dict(source)
    result['graph'] = dict(source['graph'], nodes=nodes)
    rotations = sum(int(op[3] >= 2) + int(op[6] >= 2)
                    for _, _, op in nodes if op[0] == 'step')
    calls = sum(direct_cost(root) for root in roots) + len(nodes) - len(roots)
    return result, {'schema': 1, 'count': source['count'],
                    'requested_seeds': len(seeds), 'components': len(components),
                    'roots': [list(root) for root in roots],
                    'add_projective_calls': calls,
                    'nontrivial_unit_rotations': rotations}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    source_bytes = args.source.read_bytes()
    result, receipt = weighted(json.loads(source_bytes))
    output = json.dumps(result, sort_keys=True, indent=2) + '\n'
    args.output.write_text(output)
    receipt['source_plan_sha256'] = sha256(source_bytes).hexdigest()
    receipt['output_plan_sha256'] = sha256(output.encode()).hexdigest()
    args.receipt.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
