#!/usr/bin/env python3
"""Build a root-first Q-seed graph from a frozen joint scalar plan.

The source plan fixes the requested seed set and scalar recoding. This script
changes only the order and parent edges used to construct those seeds.
"""
import argparse
from collections import defaultdict, deque
from hashlib import sha256
import json
from pathlib import Path


def unit(pair, code):
    assert 0 <= code < 6
    a, b = pair
    for _ in range(code // 2):
        a, b = a + 3*b, -a - 2*b
    if code & 1:
        a, b = -a, -b
    return a, b


def direct_cost(pair):
    return abs(pair[0]).bit_count() + abs(pair[1]).bit_count()


def witness_arcs(seeds):
    """Map every directed unit-power edge to its coefficient witness."""
    arcs = defaultdict(dict)
    for parent in sorted(seeds):
        for parent_unit in range(6):
            p = unit(parent, parent_unit)
            for bit in range(8):
                for base in range(2):
                    power = ((1 << bit, 0) if base == 0 else (0, 1 << bit))
                    for step_unit in range(6):
                        d = unit(power, step_unit)
                        target = p[0] + d[0], p[1] + d[1]
                        if target in seeds and target != parent:
                            witness = (parent_unit, base, bit, step_unit)
                            arcs[parent].setdefault(target, witness)
    return arcs


def root_first(source):
    old_nodes = source['graph']['nodes']
    seeds = {tuple(node[:2]) for node in old_nodes}
    assert len(seeds) == len(old_nodes)
    arcs = witness_arcs(seeds)
    assert all(parent in arcs.get(target, {}) for parent, targets in arcs.items()
               for target in targets), 'unit-power edge lacks reverse witness'
    undirected = defaultdict(set)
    for parent, targets in arcs.items():
        for target in targets:
            undirected[parent].add(target)
            undirected[target].add(parent)
    unseen, components = set(seeds), []
    while unseen:
        start = min(unseen)
        stack, component = [start], set()
        unseen.remove(start)
        while stack:
            parent = stack.pop()
            component.add(parent)
            for target in sorted(undirected[parent] & unseen):
                unseen.remove(target)
                stack.append(target)
        components.append(component)
    nodes, roots, seen = [], [], set()
    for component in components:
        root = min(component, key=lambda pair: (direct_cost(pair), pair))
        roots.append(root)
        queue = deque([root])
        seen.add(root)
        nodes.append([*root, ['direct']])
        while queue:
            parent = queue.popleft()
            for target in sorted(arcs[parent]):
                if target not in component or target in seen:
                    continue
                parent_unit, base, bit, step_unit = arcs[parent][target]
                nodes.append([*target, ['step', *parent, parent_unit,
                                         base, bit, step_unit]])
                seen.add(target)
                queue.append(target)
        assert component <= seen, 'component not reachable from chosen root'
    assert seen == seeds
    for a, b, op in nodes:
        if op[0] == 'direct':
            assert len(op) == 1
        else:
            _, pa, pb, pu, base, bit, su = op
            p = unit((pa, pb), pu)
            d = unit(((1 << bit, 0) if base == 0 else (0, 1 << bit)), su)
            assert (a, b) == (p[0] + d[0], p[1] + d[1])
    result = dict(source)
    result['graph'] = dict(source['graph'], nodes=nodes)
    old_calls = sum(direct_cost(tuple(node[:2])) if node[2][0] == 'direct' else 1
                    for node in old_nodes)
    new_calls = sum(direct_cost(root) for root in roots) + len(nodes) - len(roots)
    return result, {'schema': 1, 'count': source['count'],
                    'seed_count': len(seeds), 'components': len(components),
                    'roots': [list(root) for root in roots],
                    'old_add_projective_calls': old_calls,
                    'new_add_projective_calls': new_calls}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    source_bytes = args.source.read_bytes()
    result, receipt = root_first(json.loads(source_bytes))
    receipt['source_plan_sha256'] = sha256(source_bytes).hexdigest()
    output = json.dumps(result, sort_keys=True, indent=2) + '\n'
    args.output.write_text(output)
    receipt['output_plan_sha256'] = sha256(output.encode()).hexdigest()
    args.receipt.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
