#!/usr/bin/env python3
"""Grow one-restart Q seeds from a free unit rotation of Q and two links."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from one_aux_plan import add_vertex, close_requested, reverse_unit
from refine_witnesses import best_witness
from root_first_plan import unit
from steiner_plan import neighbors_with_witness

ROOT = (-2, 1)


def candidate_vertices(requested, seen, orbit):
    missing = requested - seen
    reachable = set().union(*(set(neighbors_with_witness(parent)) for parent in seen))
    touches = set().union(*(set(neighbors_with_witness(target)) for target in missing))
    for target in missing:
        for parent in seen:
            for parent_unit in range(6):
                turned = unit(parent, parent_unit)
                remainder = target[0] - turned[0], target[1] - turned[1]
                for candidate_unit in range(6):
                    touches.add(unit(remainder, reverse_unit(candidate_unit)))
    return sorted(point for point in reachable & touches
                  if point not in requested and point != (0, 0)
                  and max(map(abs, point)) < 128
                  and all(unit(point, code) not in orbit for code in range(6)))


def trial_add(requested, state, candidate):
    rows, seen, orbit = state
    witness = best_witness(candidate, orbit)
    if witness is None:
        return None
    result = list(rows), set(seen), dict(orbit)
    add_vertex(*result, candidate, witness[3])
    close_requested(requested, *result)
    return result


def rotations(rows):
    # The specialized native direct root applies omega^2 to the prepared Q.
    return 1 + sum(int(op[3] >= 2) + int(op[6] >= 2)
                   for _, _, op in rows if op[0] != 'direct')


def unit_root(source):
    assert source['count'] == 1
    requested = {tuple(row[:2]) for row in source['graph']['nodes']}
    assert ROOT in requested and len(requested) == len(source['graph']['nodes'])
    assert unit((1, 0), 4) == ROOT
    state = [], set(), {}
    add_vertex(*state, ROOT, ['direct'])
    close_requested(requested, *state)
    baseline_closed = len(state[1] & requested)
    first_candidates = candidate_vertices(requested, state[1], state[2])
    first_trials = []
    for candidate in first_candidates:
        trial = trial_add(requested, state, candidate)
        if trial is not None:
            first_trials.append((len(trial[1] & requested), candidate, trial))
    assert first_trials
    maximum = max(item[0] for item in first_trials)
    first_coverage, first, state = min(
        (item for item in first_trials if item[0] == maximum),
        key=lambda item: item[1])
    assert first_coverage < len(requested), 'second link unnecessary'
    second_candidates = candidate_vertices(requested, state[1], state[2])
    feasible = []
    for candidate in second_candidates:
        result = trial_add(requested, state, candidate)
        if result is not None and requested <= result[1]:
            feasible.append((rotations(result[0]), candidate, result[0]))
    assert feasible, 'no second auxiliary link in bounded search domain'
    total_rotations, second, nodes = min(feasible)
    assert len(nodes) == len(requested) + 2
    result = dict(source)
    result['graph'] = dict(source['graph'], nodes=nodes)
    receipt = {'schema': 1, 'count': 1, 'root': list(ROOT),
               'root_identity': '(-2,1) = omega^2*(1,0); direct root uses one projective unit rotation of Q',
               'requested_seeds': len(requested),
               'baseline_closed_seeds': baseline_closed,
               'first_candidates': len(first_candidates),
               'first_maximum_coverage': maximum,
               'first_auxiliary': list(first),
               'second_candidates': len(second_candidates),
               'second_feasible': len(feasible),
               'second_auxiliary': list(second),
               'constructed_vertices': len(nodes),
               'generic_full_adds': len(nodes) - 1,
               'nontrivial_unit_rotations': total_rotations,
               'search_domain': 'fixed free unit root; at each stage one bounded nonrequested vertex reachable by a unit-power edge and touching a missing seed; greedy maximum first-stage coverage then minimum second-stage rotations'}
    return result, receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    source_bytes = args.source.read_bytes()
    result, receipt = unit_root(json.loads(source_bytes))
    output = json.dumps(result, sort_keys=True, indent=2) + '\n'
    args.output.write_text(output)
    receipt['source_plan_sha256'] = sha256(source_bytes).hexdigest()
    receipt['output_plan_sha256'] = sha256(output.encode()).hexdigest()
    args.receipt.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
