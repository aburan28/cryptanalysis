#!/usr/bin/env python3
"""Exact minimum-cardinality tau-only cover of the radix-1024 unit classes."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "prime-j0-dual-orbit-20261011/screen.py"
SPEC = importlib.util.spec_from_file_location("tau_bound_source", SOURCE)
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)


def digest(raw):
    return sha256(raw).hexdigest()


def capacity(pair):
    value = source.screen.norm(pair)
    if 9 * value <= source.NORM_LIMIT:
        return 3
    if 3 * value <= source.NORM_LIMIT:
        return 2
    return 1


def cycle_plan(cycle, direct):
    """Partition a directed tau cycle into eligible lengths 1, 2, and 3."""
    size = len(cycle)
    capacities = [capacity(direct[node]) for node in cycle]
    choices = []
    for cut in sorted({0, (size - 1) % size, (size - 2) % size}):
        dp = [(size + 1, 1 << 62)] * (size + 1)
        step = [0] * size
        dp[size] = (0, 0)
        for pos in range(size - 1, -1, -1):
            start = (cut + pos) % size
            options = []
            for length in range(1, min(capacities[start], size - pos) + 1):
                next_cost = dp[pos + length]
                options.append(((1 + next_cost[0],
                                 source.screen.norm(direct[cycle[start]]) + next_cost[1]),
                                -length, length))
            cost, _, step[pos] = min(options)
            dp[pos] = cost
        choices.append((dp[0], cut, step))
    cost, cut, steps = min(choices, key=lambda item: (item[0], item[1]))
    segments = []
    pos = 0
    while pos < size:
        start = (cut + pos) % size
        length = steps[pos]
        assert 1 <= length <= capacities[start]
        segments.append((start, length))
        pos += length
    assert pos == size and len(segments) == cost[0]
    return segments


def main():
    canonical, nodes, direct, cycles = source.parent.full_classes()
    selected_nodes = []
    length_counts = Counter()
    cycle_costs = []
    for cycle in cycles:
        plan = cycle_plan(cycle, direct)
        cycle_costs.append(len(plan))
        for start, length in plan:
            selected_nodes.append(cycle[start])
            length_counts[length] += 1
    assert selected_nodes[0] == 0 and len(set(selected_nodes)) == len(selected_nodes)
    node_index = {node: index for index, node in enumerate(nodes)}
    seeds = [direct[node] for node in selected_nodes]
    best = [None] * len(nodes)
    for seed_id, pair in enumerate(seeds):
        for map_id in range(3):
            image = source.mapped(pair, map_id)
            value = source.screen.norm(image)
            if value > source.NORM_LIMIT:
                continue
            target = node_index[canonical[source.screen.index(image, source.RADIX)]]
            candidate = ((value, map_id, seed_id), seed_id, map_id)
            if best[target] is None or candidate < best[target]:
                best[target] = candidate
    assert all(row is not None for row in best)
    assigned = [row[1:] for row in best]
    assert len({seed_id for seed_id, _ in assigned}) == len(seeds)
    binary = bytearray(struct.pack("<4sIIII", b"LP21", source.RADIX,
                                   len(nodes), len(seeds), 7))
    for seed_id, map_id in assigned:
        binary.extend(struct.pack("<I", seed_id << 4 | map_id))
    for a, b in seeds:
        binary.extend(struct.pack("<hh", a, b))
    output = HERE / "cover-tau-exact.bin"
    output.write_bytes(binary)
    panel = source.replay_panel(assigned, seeds, nodes, canonical)
    receipt = {"schema": 1, "status": "constructed",
               "source_sha256": digest(Path(__file__).read_bytes()),
               "parent_sha256": digest(SOURCE.read_bytes()),
               "cover_sha256": digest(binary), "seed_count": len(seeds),
               "class_count": len(nodes), "cycle_count": len(cycles),
               "segment_lengths": dict(sorted(length_counts.items())),
               "cycle_costs_sha256": digest(struct.pack(
                   f"<{len(cycle_costs)}I", *cycle_costs)),
               "map_class_counts": dict(sorted(Counter(map_id for _, map_id
                                                       in assigned).items())),
               "design_panel": panel}
    (HERE / "screen.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"seed_count": len(seeds), "cycles": len(cycles),
                      "design_panel": panel}, sort_keys=True))


if __name__ == "__main__":
    main()
