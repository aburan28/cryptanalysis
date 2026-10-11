"""Exact folded-column matching and eight-pair tuple count for W18 seed 212."""

from collections import defaultdict
from fractions import Fraction
from math import factorial


def edges(pair, columns):
    return {code: (columns[pair.mask_from_code(code)],
                   columns[pair.mask_from_code(code) ^ pair.SEED])
            for code in sorted(pair.valid_codes(columns))}


def greedy_disjoint(edge_map):
    used, chosen = set(), []
    for code, endpoints in edge_map.items():
        if used.isdisjoint(endpoints):
            used.update(endpoints)
            chosen.append(code)
    return chosen


def components(edge_map):
    by_column = defaultdict(list)
    for code, endpoints in edge_map.items():
        for column in endpoints:
            by_column[column].append(code)
    seen, result = set(), []
    for code in edge_map:
        if code in seen:
            continue
        stack, component = [code], []
        seen.add(code)
        while stack:
            current = stack.pop()
            component.append(current)
            for column in edge_map[current]:
                for neighbor in by_column[column]:
                    if neighbor not in seen:
                        seen.add(neighbor)
                        stack.append(neighbor)
        result.append(component)
    return result


def matching_polynomial(component, edge_map):
    """Enumerate every matching inside one column-collision component."""
    size = len(component)
    counts = [0] * (size + 1)
    for subset in range(1 << size):
        used = set()
        for index, code in enumerate(component):
            if subset >> index & 1:
                endpoints = edge_map[code]
                if not used.isdisjoint(endpoints):
                    break
                used.update(endpoints)
        else:
            counts[len(used) // 2] += 1
    return counts


def count_ordered_matchings(edge_map, slots=8):
    coefficient = [1] + [0] * slots
    component_sizes = defaultdict(int)
    for component in components(edge_map):
        component_sizes[len(component)] += 1
        local = matching_polynomial(component, edge_map)
        coefficient = [sum(coefficient[k-j] * local[j]
                           for j in range(min(k, len(local)-1)+1))
                       for k in range(slots+1)]
    return coefficient[slots] * factorial(slots), dict(component_sizes)


def emit_matching_gate(cnf, pair, columns, selectors, emit_positive_bdd):
    """Constrain all slots to a disjoint-edge code set and distinct codes."""
    if any(len(slot) != len(pair.SOURCE_BITS) for slot in selectors):
        raise ValueError("wrong selector width")
    chosen = greedy_disjoint(edges(pair, columns))
    root, nodes = pair.build_bdd(chosen)
    for slot in selectors:
        emit_positive_bdd(cnf, root, nodes, slot)
    for i in range(len(selectors)):
        for j in range(i):
            cnf.addClause([cnf.xorLit(a, b)
                           for a, b in zip(selectors[i], selectors[j])])
    return {"admissible_pair_codes": len(chosen),
            "bdd_nodes": len(nodes),
            "code_disequalities": len(selectors) * (len(selectors)-1) // 2}


def expectation(ordered_matchings, subgroup_order, signs_per_pair=4, slots=8):
    return Fraction(ordered_matchings * signs_per_pair**slots, subgroup_order)
