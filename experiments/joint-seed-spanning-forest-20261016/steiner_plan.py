#!/usr/bin/env python3
"""Replace isolated direct Q-seed roots with shared auxiliary vertices."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from root_first_plan import direct_cost, unit


def neighbors_with_witness(parent):
    result = {}
    for parent_unit in range(6):
        p = unit(parent, parent_unit)
        for bit in range(8):
            for base in range(2):
                power = ((1 << bit, 0) if base == 0 else (0, 1 << bit))
                for step_unit in range(6):
                    q = unit(power, step_unit)
                    target = p[0] + q[0], p[1] + q[1]
                    result.setdefault(target, (parent_unit, base, bit, step_unit))
    return result


def source_calls(nodes):
    return sum(direct_cost(tuple(row[:2])) if row[2][0] == 'direct' else 1
               for row in nodes)


def steiner(source):
    nodes = source['graph']['nodes']
    direct = [tuple(row[:2]) for row in nodes if row[2][0] == 'direct']
    assert direct
    removable = set(direct[1:])
    base = [row for row in nodes if tuple(row[:2]) not in removable]
    base_seeds = {tuple(row[:2]) for row in base}
    assert len(base_seeds) == len(base)
    for row in base:
        op = row[2]
        if op[0] == 'step':
            assert tuple(op[1:3]) in base_seeds
        elif op[0] == 'sum':
            assert tuple(op[1:3]) in base_seeds and tuple(op[4:6]) in base_seeds
    if not removable:
        return source, {'auxiliary_vertices': [], 'replaced_direct_roots': []}
    targets = sorted(removable)
    assert len(targets) <= 12, 'bounded exact set-cover search'
    reachable = {}
    for parent in sorted(base_seeds):
        for point, witness in neighbors_with_witness(parent).items():
            reachable.setdefault(point, (parent, witness))
    reverse = [set(neighbors_with_witness(target)) for target in targets]
    candidates = set(reachable).intersection(set.union(*reverse))
    candidates = sorted(point for point in candidates
                        if point != (0, 0) and point not in base_seeds
                        and point not in removable
                        and max(abs(point[0]), abs(point[1])) < 128)
    best_by_mask = {}
    for point in candidates:
        mask = sum(1 << index for index, neighbors in enumerate(reverse)
                   if point in neighbors)
        if not mask:
            continue
        key = (abs(point[0]) + abs(point[1]), point)
        if mask not in best_by_mask or key < best_by_mask[mask][0]:
            best_by_mask[mask] = (key, point)
    states = {0: (0, 0, ())}
    for mask, (_, point) in sorted(best_by_mask.items()):
        for covered, (_, _, selected) in list(states.items()):
            union = covered | mask
            chosen = tuple(sorted((*selected, point)))
            candidate = (len(chosen), sum(abs(a)+abs(b) for a,b in chosen), chosen)
            if union not in states or candidate < states[union]:
                states[union] = candidate
    full = (1 << len(targets)) - 1
    assert full in states, 'auxiliary cover unavailable'
    chosen = states[full][2]
    output_nodes = list(base)
    for point in chosen:
        parent, (pu, basis, bit, su) = reachable[point]
        output_nodes.append([*point, ['step', *parent, pu, basis, bit, su]])
    for target in targets:
        options = [(point, neighbors_with_witness(point).get(target))
                   for point in chosen]
        point, witness = next((point, witness) for point, witness in options
                              if witness is not None)
        pu, basis, bit, su = witness
        output_nodes.append([*target, ['step', *point, pu, basis, bit, su]])
    seen = set()
    for a, b, op in output_nodes:
        assert (a,b) not in seen and (a,b) != (0,0)
        if op[0] == 'step':
            parent = tuple(op[1:3])
            pu, basis, bit, su = op[3:7]
            assert parent in seen
            p = unit(parent, pu)
            q = unit(((1 << bit, 0) if basis == 0 else (0, 1 << bit)), su)
            assert (a,b) == (p[0]+q[0],p[1]+q[1])
        elif op[0] == 'sum':
            left, lu, right, ru = tuple(op[1:3]), op[3], tuple(op[4:6]), op[6]
            assert left in seen and right in seen
            p, q = unit(left, lu), unit(right, ru)
            assert (a,b) == (p[0]+q[0],p[1]+q[1])
        else:
            assert op == ['direct']
        seen.add((a,b))
    requested = {tuple(row[:2]) for row in nodes}
    assert requested <= seen and seen-requested == set(chosen)
    result = dict(source)
    result['graph'] = dict(source['graph'], nodes=output_nodes)
    return result, {'auxiliary_vertices': [list(point) for point in chosen],
                    'replaced_direct_roots': [list(target) for target in targets]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    source_bytes = args.source.read_bytes()
    source = json.loads(source_bytes)
    result, receipt = steiner(source)
    output = json.dumps(result, sort_keys=True, indent=2) + '\n'
    args.output.write_text(output)
    receipt.update({'schema': 1, 'count': source['count'],
                    'source_plan_sha256': sha256(source_bytes).hexdigest(),
                    'output_plan_sha256': sha256(output.encode()).hexdigest(),
                    'source_add_projective_calls': source_calls(source['graph']['nodes']),
                    'new_add_projective_calls': source_calls(result['graph']['nodes']),
                    'requested_seeds': len(source['graph']['nodes']),
                    'constructed_vertices': len(result['graph']['nodes'])})
    args.receipt.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
