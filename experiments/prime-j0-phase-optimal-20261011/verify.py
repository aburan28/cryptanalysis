#!/usr/bin/env python3
"""Independent forward-DP optimum and exhaustive class/residue check."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "prime-j0-dual-orbit-20261011/verify_cover.py"
SPEC = importlib.util.spec_from_file_location("phase_optimal_independent", SOURCE)
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
    """Exact cyclic Boolean cover, minimizing seeds then forced map-two cells."""
    size = len(capacities)

    def covered(index, current, previous, before_previous):
        direct = bool(current)
        one = bool(previous and capacities[(index - 1) % size] >= 2)
        two = bool(before_previous and capacities[(index - 2) % size] >= 3)
        return direct or one or two, int(not direct and not one and two)

    if size <= 2:
        options = []
        for mask in range(1 << size):
            selected = [(mask >> i) & 1 for i in range(size)]
            checks = [covered(i, selected[i], selected[(i - 1) % size],
                              selected[(i - 2) % size]) for i in range(size)]
            if all(check[0] for check in checks):
                options.append((sum(selected), sum(check[1] for check in checks)))
        return min(options)

    answer = (size + 1, size + 1)
    for first in (0, 1):
        for second in (0, 1):
            states = {(first, second): (first + second, 0)}
            for index in range(2, size):
                next_states = {}
                for (prev2, prev1), cost in states.items():
                    for current in (0, 1):
                        valid, map_two = covered(index, current, prev1, prev2)
                        if not valid:
                            continue
                        state = (prev1, current)
                        proposed = (cost[0] + current, cost[1] + map_two)
                        old = next_states.get(state)
                        if old is None or proposed < old:
                            next_states[state] = proposed
                states = next_states
            for (before_last, last), cost in states.items():
                valid0, map_two0 = covered(0, first, last, before_last)
                valid1, map_two1 = covered(1, second, first, last)
                if valid0 and valid1:
                    answer = min(answer, (cost[0], cost[1] + map_two0 + map_two1))
    assert answer[0] <= size
    return answer


def main():
    raw = (HERE / "cover-phase-optimal.bin").read_bytes()
    screen = json.loads((HERE / "screen.json").read_bytes())
    assert screen["source_sha256"] == digest((HERE / "construct.py").read_bytes())
    assert screen["cover_sha256"] == digest(raw)
    magic, radix, classes, seed_count, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, seed_count, mask) == \
        (b"LP21", independent.RADIX, 174_764, 73_417, 7)
    offset = 20 + 4 * classes
    assert len(raw) == offset + 4 * seed_count
    seeds = list(struct.iter_unpack("<hh", raw[offset:]))
    assert seeds[0] == (0, 0) and len(set(seeds)) == seed_count

    canonical, nodes = independent.orbit_partition()
    assert len(nodes) == classes
    node_index = {node: i for i, node in enumerate(nodes)}
    successor = {}
    for node in nodes:
        successor[node] = canonical[independent.residue(
            independent.tau(divmod(node, radix)))]
    assert len(set(successor.values())) == classes
    minima = {node: minimum_norm(node) for node in nodes}
    capacities = {node: (3 if 9 * value <= independent.SIZE else
                         2 if 3 * value <= independent.SIZE else 1)
                  for node, value in minima.items()}
    seen = set()
    scores = []
    for node in nodes:
        if node in seen:
            continue
        cycle = []
        here = node
        while here not in seen:
            seen.add(here)
            cycle.append(here)
            here = successor[here]
        assert here == node
        scores.append(cycle_optimum([capacities[item] for item in cycle]))
    assert len(seen) == classes and len(scores) == 513
    optimum = tuple(sum(score[j] for score in scores) for j in range(2))
    assert optimum == (seed_count, 27_932)
    assert digest(b"".join(struct.pack("<II", *score) for score in scores)) == \
        screen["cycle_scores_sha256"]

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
    assert map_counts[2] == 27_932
    assert map_counts[2] == optimum[1]
    minimum_singletons = map_counts[2] - classes + 2 * seed_count
    assert minimum_singletons == 2
    result = {"schema": 1, "status": "passed", "classes": classes,
              "residues": checked_residues, "cycles": len(scores),
              "seed_count": seed_count, "minimum_singletons": minimum_singletons,
              "minimum_tau_squared_classes": map_counts[2],
              "map_class_counts": dict(sorted(map_counts.items())),
              "cover_sha256": digest(raw),
              "verifier_sha256": digest(Path(__file__).read_bytes()),
              "independent_actions_sha256": digest(SOURCE.read_bytes())}
    (HERE / "check.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "seed_count", "minimum_singletons",
                       "minimum_tau_squared_classes", "residues")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
