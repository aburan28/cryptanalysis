#!/usr/bin/env python3
"""Independently check the 64 MiB tau cover and its class-count lower bound."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-phase-optimal-20261011/verify.py"
SPEC = importlib.util.spec_from_file_location("phase_cover_independent", PARENT)
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
independent = parent.independent


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    raw = (HERE / "cover-budget-optimal.bin").read_bytes()
    screen = json.loads((HERE / "screen.json").read_bytes())
    assert screen["source_sha256"] == digest((HERE / "construct.py").read_bytes())
    assert screen["cover_sha256"] == digest(raw)
    magic, radix, classes, count, mask = struct.unpack_from("<4sIIII", raw)
    assert (magic, radix, classes, count, mask) == \
        (b"LP21", independent.RADIX, 174_764, 83_878, 7)
    offset = 20 + 4 * classes
    assert len(raw) == offset + 4 * count
    seeds = list(struct.iter_unpack("<hh", raw[offset:]))
    assert seeds[0] == (0, 0) and len(set(seeds)) == count

    canonical, nodes = independent.orbit_partition()
    assert len(nodes) == classes
    node_index = {node: i for i, node in enumerate(nodes)}
    successor = {node: canonical[independent.residue(
        independent.tau(divmod(node, radix)))] for node in nodes}
    assert len(set(successor.values())) == classes
    seen = set()
    singleton_cycles = []
    phase_optima = []
    minima = {node: parent.minimum_norm(node) for node in nodes}
    capacities = {node: (3 if 9 * value <= independent.SIZE else
                         2 if 3 * value <= independent.SIZE else 1)
                  for node, value in minima.items()}
    for node in nodes:
        if node in seen:
            continue
        cycle = []
        current = node
        while current not in seen:
            seen.add(current)
            cycle.append(current)
            current = successor[current]
        assert current == node
        if len(cycle) == 1:
            singleton_cycles.append(node)
        phase_optima.append(parent.cycle_optimum(
            [capacities[item] for item in cycle]))
    assert len(seen) == classes and len(phase_optima) == 513
    assert singleton_cycles == [0, 512]
    assert tuple(sum(score[j] for score in phase_optima)
                 for j in range(2)) == (73_417, 27_932)

    seed_nodes = [canonical[independent.residue(pair)] for pair in seeds]
    assert len(set(seed_nodes)) == count
    for pair, node in zip(seeds, seed_nodes):
        assert independent.norm(pair) == minima[node]
    used = set()
    map_counts = Counter()
    checked_residues = 0
    for slot, node in enumerate(nodes):
        code = struct.unpack_from("<I", raw, 20 + 4 * slot)[0]
        seed_id, exponent = code >> 4, code & 15
        assert seed_id < count and exponent < 3
        image = independent.action(seeds[seed_id], exponent)
        assert independent.norm(image) <= independent.SIZE
        actual = {independent.residue(value)
                  for value in independent.unit_images(image)}
        expected = {independent.residue(value)
                    for value in independent.unit_images(divmod(node, radix))}
        assert actual == expected
        assert all(canonical[value] == node for value in actual)
        assert node_index[canonical[independent.residue(image)]] == slot
        checked_residues += len(actual)
        used.add(seed_id)
        map_counts[exponent] += 1
    assert len(used) == count and checked_residues == independent.SIZE
    assert dict(sorted(map_counts.items())) == {0: 83_878, 1: 83_876, 2: 7_010}
    assert {int(key): value for key, value in
            screen["map_class_counts"].items()} == dict(map_counts)

    # Each seed supplies at most its own and the next non-tau-squared class.
    # Each of the two one-class cycles consumes a seed but adds only one.
    lower_bound = classes - 2 * count + len(singleton_cycles)
    assert lower_bound == map_counts[2] == 7_010
    base_bytes = 59_032_928
    extra = count - 73_417
    retained_bytes = base_bytes + extra * (12 * 64 + 4)
    assert extra == 10_461 and retained_bytes == 64 * 1024 * 1024 - 44
    assert retained_bytes == screen["retained_bytes"]
    result = {"schema": 1, "status": "passed", "classes": classes,
              "residues": checked_residues, "cycles": len(phase_optima),
              "singleton_cycles": singleton_cycles,
              "minimum_seed_phase_optimum": [73_417, 27_932],
              "seed_count": count, "tau_squared_lower_bound": lower_bound,
              "tau_squared_classes": map_counts[2],
              "map_class_counts": dict(sorted(map_counts.items())),
              "retained_bytes": retained_bytes,
              "budget_headroom_bytes": 64 * 1024 * 1024 - retained_bytes,
              "cover_sha256": digest(raw),
              "verifier_sha256": digest(Path(__file__).read_bytes()),
              "independent_actions_sha256": digest(Path(
                  independent.__file__).read_bytes())}
    (HERE / "check.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "seed_count", "tau_squared_lower_bound",
                       "tau_squared_classes", "retained_bytes", "residues")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
