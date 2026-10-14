#!/usr/bin/env python3
"""Independent Boolean-DP optimum and complete-residue cover verifier."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "prime-j0-dual-orbit-20261011/verify_cover.py"
SPEC = importlib.util.spec_from_file_location("tau_bound_independent", SOURCE)
independent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(independent)


def digest(raw):
    return sha256(raw).hexdigest()


def minimum_norm(node):
    a, b = divmod(node, independent.RADIX)
    return min(independent.norm((a + i * independent.RADIX,
                                 b + j * independent.RADIX))
               for i in range(-2, 2) for j in range(-2, 2))


def cycle_optimum(capacities):
    """Minimize selected Boolean positions with every cyclic class covered."""
    size = len(capacities)

    def covered(index, current, previous, before_previous):
        return (current or
                (previous and capacities[(index - 1) % size] >= 2) or
                (before_previous and capacities[(index - 2) % size] >= 3))

    if size <= 2:
        return min(sum((mask >> i) & 1 for i in range(size))
                   for mask in range(1 << size)
                   if all(covered(i, (mask >> i) & 1,
                                  (mask >> ((i - 1) % size)) & 1,
                                  (mask >> ((i - 2) % size)) & 1)
                          for i in range(size)))

    answer = size + 1
    for first in (0, 1):
        for second in (0, 1):
            states = {(first, second): first + second}
            for index in range(2, size):
                next_states = {}
                for (prev2, prev1), cost in states.items():
                    for current in (0, 1):
                        if not covered(index, current, prev1, prev2):
                            continue
                        state = (prev1, current)
                        next_states[state] = min(next_states.get(state, size + 1),
                                                 cost + current)
                states = next_states
            for (before_last, last), cost in states.items():
                if covered(0, first, last, before_last) and \
                        covered(1, second, first, last):
                    answer = min(answer, cost)
    assert answer <= size
    return answer


def main():
    raw = (HERE / "cover-tau-exact.bin").read_bytes()
    screen = json.loads((HERE / "screen.json").read_bytes())
    assert screen["source_sha256"] == digest((HERE / "construct.py").read_bytes())
    assert screen["cover_sha256"] == digest(raw)
    magic, radix, classes, seed_count, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, mask) == \
        (b"LP21", independent.RADIX, 174_764, 7)
    offset = 20 + 4 * classes
    assert len(raw) == offset + 4 * seed_count
    seeds = list(struct.iter_unpack("<hh", raw[offset:]))
    assert seeds[0] == (0, 0) and len(set(seeds)) == seed_count

    canonical, nodes = independent.orbit_partition()
    assert len(nodes) == classes
    node_index = {node: i for i, node in enumerate(nodes)}
    next_node = {}
    for node in nodes:
        image = independent.tau(divmod(node, radix))
        next_node[node] = canonical[independent.residue(image)]
    assert len(set(next_node.values())) == classes

    minima = {node: minimum_norm(node) for node in nodes}
    capacities = {node: (3 if 9 * value <= independent.SIZE else
                         2 if 3 * value <= independent.SIZE else 1)
                  for node, value in minima.items()}
    seen = set()
    costs = []
    lengths = Counter()
    for node in nodes:
        if node in seen:
            continue
        cycle = []
        here = node
        while here not in seen:
            seen.add(here)
            cycle.append(here)
            here = next_node[here]
        assert here == node
        cap = [capacities[item] for item in cycle]
        costs.append(cycle_optimum(cap))
        lengths[len(cycle)] += 1
    assert len(seen) == classes and len(costs) == 513
    exact = sum(costs)
    assert exact == seed_count == screen["seed_count"]
    assert digest(struct.pack(f"<{len(costs)}I", *costs)) == \
        screen["cycle_costs_sha256"]

    best = [None] * classes
    for seed_id, pair in enumerate(seeds):
        node = canonical[independent.residue(pair)]
        assert independent.norm(pair) == minima[node]
        for map_id in range(3):
            image = independent.action(pair, map_id)
            value = independent.norm(image)
            if value > independent.SIZE:
                continue
            target = node_index[canonical[independent.residue(image)]]
            candidate = ((value, map_id, seed_id), seed_id, map_id)
            if best[target] is None or candidate < best[target]:
                best[target] = candidate
    assert all(best)
    used = set()
    map_counts = Counter()
    checked_residues = 0
    for index, node in enumerate(nodes):
        code = struct.unpack_from("<I", raw, 20 + 4 * index)[0]
        seed_id, map_id = code >> 4, code & 15
        assert (seed_id, map_id) == best[index][1:]
        image = independent.action(seeds[seed_id], map_id)
        assert independent.norm(image) <= independent.SIZE
        actual = {independent.residue(value)
                  for value in independent.unit_images(image)}
        expected = {independent.residue(value)
                    for value in independent.unit_images(divmod(node, radix))}
        assert actual == expected
        assert all(canonical[value] == node for value in actual)
        checked_residues += len(actual)
        used.add(seed_id)
        map_counts[map_id] += 1
    assert len(used) == seed_count and checked_residues == independent.SIZE
    assert dict(sorted(map_counts.items())) == \
        {int(key): value for key, value in screen["map_class_counts"].items()}
    result = {"schema": 1, "status": "passed",
              "classes": classes, "residues": checked_residues,
              "cycles": len(costs), "seed_count": seed_count,
              "minimum_tau_only_seeds": exact,
              "rho_cover_seed_budget": 67_338,
              "additional_seeds_required": exact - 67_338,
              "rho_only_class_lower_bound_at_budget": exact - 67_338,
              "cycle_lengths": dict(sorted(lengths.items())),
              "cover_sha256": digest(raw),
              "verifier_sha256": digest(Path(__file__).read_bytes()),
              "independent_actions_sha256": digest(SOURCE.read_bytes())}
    (HERE / "exact-check.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "minimum_tau_only_seeds", "cycles",
                       "residues", "additional_seeds_required")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
