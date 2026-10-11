#!/usr/bin/env python3
"""Minimum-seed tau cover, then minimum number of tau-squared classes."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "prime-j0-dual-orbit-20261011/screen.py"
SPEC = importlib.util.spec_from_file_location("phase_optimal_source", SOURCE)
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
    """Lexicographic optimum: seeds, singleton segments, seed norms."""
    size = len(cycle)
    capacities = [capacity(direct[node]) for node in cycle]
    plans = []
    for cut in sorted({0, (size - 1) % size, (size - 2) % size}):
        costs = [(size + 1, size + 1, 1 << 62)] * (size + 1)
        steps = [0] * size
        costs[size] = (0, 0, 0)
        for pos in range(size - 1, -1, -1):
            start = (cut + pos) % size
            options = []
            for length in range(1, min(capacities[start], size - pos) + 1):
                tail = costs[pos + length]
                score = (1 + tail[0], int(length == 1) + tail[1],
                         source.screen.norm(direct[cycle[start]]) + tail[2])
                options.append((score, -length, length))
            costs[pos], _, steps[pos] = min(options)
        plans.append((costs[0], cut, steps))
    score, cut, steps = min(plans, key=lambda item: (item[0], item[1]))
    segments = []
    pos = 0
    while pos < size:
        start = (cut + pos) % size
        length = steps[pos]
        assert 1 <= length <= capacities[start]
        segments.append((cycle[start], length))
        pos += length
    assert pos == size and len(segments) == score[0]
    return segments, (score[0], sum(length == 3 for _, length in segments))


def main():
    canonical, nodes, direct, cycles = source.parent.full_classes()
    plans = [cycle_plan(cycle, direct) for cycle in cycles]
    segments = [segment for plan, _ in plans for segment in plan]
    seeds = [direct[node] for node, _ in segments]
    assert seeds[0] == (0, 0) and len(set(seeds)) == len(seeds)
    assert len(seeds) == 73_417
    lengths = Counter(length for _, length in segments)
    assert lengths[1] == 2 and lengths[2] == 45_483 and lengths[3] == 27_932

    node_index = {node: index for index, node in enumerate(nodes)}
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
    assert Counter(map_id for _, map_id in assigned) == Counter({0: 73_417,
                                                                  1: 73_415,
                                                                  2: 27_932})

    binary = bytearray(struct.pack("<4sIIII", b"LP21", source.RADIX,
                                   len(nodes), len(seeds), 7))
    for seed_id, map_id in assigned:
        binary.extend(struct.pack("<I", seed_id << 4 | map_id))
    for a, b in seeds:
        binary.extend(struct.pack("<hh", a, b))
    output = HERE / "cover-phase-optimal.bin"
    output.write_bytes(binary)
    costs = [score for _, score in plans]
    receipt = {"schema": 1, "status": "constructed",
               "source_sha256": digest(Path(__file__).read_bytes()),
               "parent_sha256": digest(SOURCE.read_bytes()),
               "cover_sha256": digest(binary), "seed_count": len(seeds),
               "class_count": len(nodes), "cycle_count": len(cycles),
               "segment_lengths": dict(sorted(lengths.items())),
               "cycle_scores_sha256": digest(b"".join(
                   struct.pack("<II", *score) for score in costs)),
               "map_class_counts": dict(sorted(Counter(map_id for _, map_id
                                                       in assigned).items()))}
    (HERE / "screen.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"seed_count": len(seeds), "singletons": lengths[1],
                      "tau_squared_classes": lengths[3],
                      "cover_sha256": receipt["cover_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
