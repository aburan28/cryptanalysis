#!/usr/bin/env python3
"""Replace expensive direct Q-seed roots with two-parent component links."""
import argparse
from collections import defaultdict, deque
from hashlib import sha256
import json
from pathlib import Path

from root_first_plan import direct_cost, unit, witness_arcs


def unary_components(seeds, arcs):
    adjacent = defaultdict(set)
    for parent, targets in arcs.items():
        for target in targets:
            assert parent in arcs.get(target, {}), 'missing reverse unary edge'
            adjacent[parent].add(target)
            adjacent[target].add(parent)
    unseen, components = set(seeds), []
    while unseen:
        start = min(unseen)
        pending, component = [start], set()
        unseen.remove(start)
        while pending:
            parent = pending.pop()
            component.add(parent)
            for target in sorted(adjacent[parent] & unseen):
                unseen.remove(target)
                pending.append(target)
        components.append(component)
    return components


def sum_links(seeds, component_of):
    """One deterministic two-parent witness per component transition."""
    links = {}
    orbit = {seed: [unit(seed, code) for code in range(6)] for seed in seeds}
    for left in sorted(seeds):
        for right in sorted(seeds):
            for left_unit, l in enumerate(orbit[left]):
                for right_unit, r in enumerate(orbit[right]):
                    target = l[0] + r[0], l[1] + r[1]
                    if target not in seeds:
                        continue
                    lc, rc, tc = (component_of[left], component_of[right],
                                  component_of[target])
                    if tc in (lc, rc):
                        continue
                    key = (min(lc, rc), max(lc, rc), tc)
                    witness = (left, left_unit, right, right_unit, target)
                    if key not in links or witness < links[key]:
                        links[key] = witness
    return links


def root_subset(components, links):
    roots = [min(component, key=lambda pair: (direct_cost(pair), pair))
             for component in components]
    full = (1 << len(components)) - 1
    best = None
    for initial in range(1, full + 1):
        opened = initial
        while True:
            updated = opened
            for (left, right, target) in links:
                if opened & (1 << left) and opened & (1 << right):
                    updated |= 1 << target
            if updated == opened:
                break
            opened = updated
        if opened != full:
            continue
        selected = tuple(index for index in range(len(roots)) if initial & (1 << index))
        overhead = sum(direct_cost(roots[index]) - 1 for index in selected)
        candidate = (overhead, len(selected), selected)
        if best is None or candidate < best:
            best = candidate
    assert best is not None
    return roots, best[2]


def two_parent(source):
    old_nodes = source['graph']['nodes']
    seeds = {tuple(node[:2]) for node in old_nodes}
    assert len(seeds) == len(old_nodes)
    arcs = witness_arcs(seeds)
    components = unary_components(seeds, arcs)
    component_of = {seed: index for index, component in enumerate(components)
                    for seed in component}
    # A single unary component has no cross-component work to search.
    links = sum_links(seeds, component_of) if len(components) > 1 else {}
    roots, selected = root_subset(components, links)
    nodes, seen, opened = [], set(), set()

    def expand(index, seed, op):
        assert seed not in seen and seed in components[index]
        seen.add(seed)
        opened.add(index)
        nodes.append([*seed, op])
        pending = deque([seed])
        while pending:
            parent = pending.popleft()
            for target in sorted(arcs[parent]):
                if target in seen or target not in components[index]:
                    continue
                parent_unit, base, bit, step_unit = arcs[parent][target]
                seen.add(target)
                nodes.append([*target, ['step', *parent, parent_unit,
                                         base, bit, step_unit]])
                pending.append(target)
        assert components[index] <= seen

    for index in selected:
        expand(index, roots[index], ['direct'])
    while len(opened) < len(components):
        choices = [(key, witness) for key, witness in links.items()
                   if key[2] not in opened and key[0] in opened and key[1] in opened]
        assert choices, 'component closure cannot cover requested seeds'
        (left_comp, right_comp, target_comp), witness = min(choices)
        left, left_unit, right, right_unit, target = witness
        assert left in seen and right in seen
        assert {component_of[left], component_of[right]} == {left_comp, right_comp}
        l, r = unit(left, left_unit), unit(right, right_unit)
        assert target == (l[0] + r[0], l[1] + r[1])
        expand(target_comp, target, ['sum', *left, left_unit,
                                      *right, right_unit])
    assert seen == seeds
    result = dict(source)
    result['graph'] = dict(source['graph'], nodes=nodes)
    old_calls = sum(direct_cost(tuple(node[:2])) if node[2][0] == 'direct' else 1
                    for node in old_nodes)
    new_calls = sum(direct_cost(roots[index]) for index in selected)
    new_calls += len(nodes) - len(selected)
    return result, {'schema': 1, 'count': source['count'],
                    'seed_count': len(seeds), 'unary_components': len(components),
                    'selected_direct_roots': [list(roots[index]) for index in selected],
                    'two_parent_component_links': len(components) - len(selected),
                    'old_add_projective_calls': old_calls,
                    'new_add_projective_calls': new_calls}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    source_bytes = args.source.read_bytes()
    result, receipt = two_parent(json.loads(source_bytes))
    receipt['source_plan_sha256'] = sha256(source_bytes).hexdigest()
    output = json.dumps(result, sort_keys=True, indent=2) + '\n'
    args.output.write_text(output)
    receipt['output_plan_sha256'] = sha256(output.encode()).hexdigest()
    args.receipt.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
