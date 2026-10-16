#!/usr/bin/env python3
"""Search one auxiliary vertex linking the frozen one-restart Q-seed graph."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from refine_witnesses import best_witness
from root_first_plan import direct_cost, unit
from steiner_plan import neighbors_with_witness

ROOT = (-40, 16)


def add_vertex(rows, seen, orbit, target, op):
    assert target not in seen and target != (0, 0)
    assert all(unit(target, code) not in orbit for code in range(6))
    rows.append([*target, op])
    seen.add(target)
    for code in range(6):
        orbit[unit(target, code)] = (target, code)


def close_requested(requested, rows, seen, orbit):
    while True:
        options = []
        for target in requested - seen:
            witness = best_witness(target, orbit)
            if witness is not None:
                rotations, family, bit, op = witness
                options.append((rotations, family, bit, target, op))
        if not options:
            return
        _, _, _, target, op = min(options)
        add_vertex(rows, seen, orbit, target, op)


def reverse_unit(code):
    return 2 * ((3 - code // 2) % 3) + (code & 1)


def one_aux(source):
    assert source['count'] == 1
    requested = {tuple(row[:2]) for row in source['graph']['nodes']}
    assert ROOT in requested and len(requested) == len(source['graph']['nodes'])
    rows, seen, orbit = [], set(), {}
    add_vertex(rows, seen, orbit, ROOT, ['direct'])
    close_requested(requested, rows, seen, orbit)
    base_count = len(seen)
    missing = requested - seen
    assert missing, 'one-auxiliary search is unnecessary'
    reachable = set().union(*(set(neighbors_with_witness(parent)) for parent in seen))
    touches = set().union(*(set(neighbors_with_witness(target)) for target in missing))
    for target in missing:
        for parent in seen:
            for parent_unit in range(6):
                turned = unit(parent, parent_unit)
                remainder = target[0] - turned[0], target[1] - turned[1]
                for candidate_unit in range(6):
                    touches.add(unit(remainder, reverse_unit(candidate_unit)))
    candidates = sorted(point for point in reachable & touches
                        if point not in requested and point != (0, 0)
                        and max(map(abs, point)) < 128
                        and all(unit(point, code) not in orbit for code in range(6)))
    feasible = []
    for candidate in candidates:
        witness = best_witness(candidate, orbit)
        if witness is None:
            continue
        trial_rows, trial_seen, trial_orbit = list(rows), set(seen), dict(orbit)
        add_vertex(trial_rows, trial_seen, trial_orbit, candidate, witness[3])
        close_requested(requested, trial_rows, trial_seen, trial_orbit)
        if requested <= trial_seen:
            rotations = sum(int(op[3] >= 2) + int(op[6] >= 2)
                            for _, _, op in trial_rows if op[0] != 'direct')
            full_adds = direct_cost(ROOT) - 1 + len(trial_rows) - 1
            feasible.append(((full_adds, rotations, candidate), trial_rows))
    assert feasible, 'no one-auxiliary schedule in bounded search domain'
    (full_adds, rotations, chosen), selected = min(feasible)
    assert len(selected) == len(requested) + 1
    result = dict(source)
    result['graph'] = dict(source['graph'], nodes=selected)
    receipt = {'schema': 1, 'count': 1, 'root': list(ROOT),
               'requested_seeds': len(requested), 'baseline_closed_seeds': base_count,
               'missing_before_auxiliary': [list(x) for x in sorted(missing)],
               'candidate_count': len(candidates), 'feasible_candidates': len(feasible),
               'search_domain': 'one nonrequested vertex reachable from the fixed root closure by one unit-power edge, touching a missing seed in one step or one rotated sum, coordinates below 128',
               'auxiliary_vertex': list(chosen), 'constructed_vertices': len(selected),
               'generic_full_adds': full_adds,
               'nontrivial_unit_rotations': rotations}
    return result, receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    source_bytes = args.source.read_bytes()
    result, receipt = one_aux(json.loads(source_bytes))
    output = json.dumps(result, sort_keys=True, indent=2) + '\n'
    args.output.write_text(output)
    receipt['source_plan_sha256'] = sha256(source_bytes).hexdigest()
    receipt['output_plan_sha256'] = sha256(output.encode()).hexdigest()
    args.receipt.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
