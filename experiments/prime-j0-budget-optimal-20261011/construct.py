#!/usr/bin/env python3
"""Construct the minimum tau-squared cover fitting a 64 MiB retained table."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-phase-optimal-20261011/construct.py"
SPEC = importlib.util.spec_from_file_location("phase_optimal_cover", PARENT)
phase = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(phase)

CLASSES = 174_764
MINIMUM_SEEDS = 73_417
MINIMUM_RETAINED_BYTES = 59_032_928
BYTES_PER_EXTRA_SEED = 12 * 64 + 4
BUDGET_BYTES = 64 * 1024 * 1024
EXTRA_SEEDS = (BUDGET_BYTES - MINIMUM_RETAINED_BYTES) // BYTES_PER_EXTRA_SEED
SEEDS = MINIMUM_SEEDS + EXTRA_SEEDS


def digest(raw):
    return sha256(raw).hexdigest()


def pair_count(plan):
    """Maximum disjoint adjacent triple pairs on a cyclic tiling."""
    flags = [span == 3 for _, span in plan]
    if all(flags):
        return len(flags) // 2
    pivot = flags.index(False)
    run = count = 0
    for offset in range(1, len(flags) + 1):
        if flags[(pivot + offset) % len(flags)]:
            run += 1
        else:
            count += run // 2
            run = 0
    return count


def cycle_plan(cycle, direct):
    """Retile one cycle at minimum seeds/singletons with many triple pairs."""
    size = len(cycle)
    capacities = [phase.capacity(direct[node]) for node in cycle]
    best = None
    # A segment containing position zero begins at one of these three cuts.
    for cut in sorted({0, (size - 1) % size, (size - 2) % size}):
        # The second initial state permits a triple pair across the cut.
        for initial in (0, 1):
            states = {(0, initial): (0, 0, 0, 0)}
            previous = {}
            for pos in range(size):
                for pending in (0, 1):
                    cost = states.get((pos, pending))
                    if cost is None:
                        continue
                    start = (cut + pos) % size
                    norm = phase.source.screen.norm(direct[cycle[start]])
                    for span in range(1, min(capacities[start], size - pos) + 1):
                        next_pending = int(span == 3 and not pending)
                        next_key = (pos + span, next_pending)
                        next_cost = (cost[0] + 1, cost[1] + int(span == 1),
                                     cost[2] - int(span == 3 and pending),
                                     cost[3] + norm)
                        if next_key not in states or next_cost < states[next_key]:
                            states[next_key] = next_cost
                            previous[next_key] = (pos, pending, span)
            for final in (0, 1):
                if initial == 1 and final != 1:
                    continue
                key = (size, final)
                if key not in states:
                    continue
                plan = []
                while key != (0, initial):
                    pos, pending, span = previous[key]
                    plan.append(((cut + pos) % size, span))
                    key = (pos, pending)
                plan.reverse()
                cost = states[(size, final)]
                score = (cost[0], cost[1], -pair_count(plan), cost[3], cut,
                         initial)
                if best is None or score < best[0]:
                    best = (score, plan)
    assert best is not None
    return best[1]


def split_pairs(plan, cycle_size, remaining):
    """Replace 3+3 by 2+2+2, using at most remaining extra seeds."""
    modified = []
    available = selected = 0
    index = 0
    while index < len(plan):
        start, span = plan[index]
        if (index + 1 < len(plan) and span == 3
                and plan[index + 1] == ((start + 3) % cycle_size, 3)):
            available += 1
            if selected < remaining:
                modified.extend((((start + 2 * offset) % cycle_size, 2)
                                 for offset in range(3)))
                selected += 1
            else:
                modified.extend(plan[index:index + 2])
            index += 2
        else:
            modified.append(plan[index])
            index += 1
    return modified, available, selected


def main():
    canonical, nodes, direct, cycles = phase.source.parent.full_classes()
    assert len(nodes) == CLASSES and len(cycles) == 513
    index = {node: slot for slot, node in enumerate(nodes)}
    seeds = []
    assignments = [None] * len(nodes)
    original_lengths = Counter()
    final_lengths = Counter()
    available = selected = 0
    cyclic_pairs = 0
    for cycle in cycles:
        plan = cycle_plan(cycle, direct)
        baseline, _ = phase.cycle_plan(cycle, direct)
        assert len(plan) == len(baseline)
        assert sum(span == 1 for _, span in plan) == \
            sum(span == 1 for _, span in baseline)
        assert sum(span for _, span in plan) == len(cycle)
        cyclic_pairs += pair_count(plan)
        original_lengths.update(span for _, span in plan)
        current, count, used = split_pairs(plan, len(cycle), EXTRA_SEEDS - selected)
        available += count
        selected += used
        covered = set()
        for start, span in current:
            node = cycle[start]
            pair = direct[node]
            assert phase.capacity(pair) >= span
            seed_id = len(seeds)
            seeds.append(pair)
            final_lengths[span] += 1
            for exponent in range(span):
                position = (start + exponent) % len(cycle)
                assert position not in covered
                covered.add(position)
                target = cycle[position]
                image = phase.source.mapped(pair, exponent)
                assert canonical[phase.source.screen.index(
                    image, phase.source.RADIX)] == target
                slot = index[target]
                assert assignments[slot] is None
                assignments[slot] = (seed_id, exponent)
        assert len(covered) == len(cycle)

    assert original_lengths == {1: 2, 2: 45_483, 3: 27_932}
    assert selected == EXTRA_SEEDS and available >= EXTRA_SEEDS
    assert len(seeds) == SEEDS and len(set(seeds)) == SEEDS
    assert seeds[0] == (0, 0) and all(row is not None for row in assignments)
    assert final_lengths == {1: 2, 2: 45_483 + 3 * EXTRA_SEEDS,
                             3: 27_932 - 2 * EXTRA_SEEDS}
    assert final_lengths[3] == CLASSES - 2 * SEEDS + 2 == 7_010
    retained_bytes = MINIMUM_RETAINED_BYTES + EXTRA_SEEDS * BYTES_PER_EXTRA_SEED
    assert retained_bytes == BUDGET_BYTES - 44

    binary = bytearray(struct.pack("<4sIIII", b"LP21", phase.source.RADIX,
                                   len(nodes), len(seeds), 7))
    for seed_id, exponent in assignments:
        binary.extend(struct.pack("<I", seed_id << 4 | exponent))
    for a, b in seeds:
        binary.extend(struct.pack("<hh", a, b))
    output = HERE / "cover-budget-optimal.bin"
    output.write_bytes(binary)
    receipt = {"schema": 1, "status": "constructed",
               "source_sha256": digest(Path(__file__).read_bytes()),
               "parent_sha256": digest(PARENT.read_bytes()),
               "parent_cover_sha256": digest(
                   (PARENT.parent / "cover-phase-optimal.bin").read_bytes()),
               "cover_sha256": digest(binary), "class_count": len(nodes),
               "cycle_count": len(cycles), "seed_count": len(seeds),
               "extra_seeds": EXTRA_SEEDS,
               "available_linear_pairs": available,
               "available_cyclic_pairs": cyclic_pairs,
               "selected_pairs": selected,
               "original_segment_lengths": dict(sorted(original_lengths.items())),
               "segment_lengths": dict(sorted(final_lengths.items())),
               "map_class_counts": {"0": final_lengths[1] + final_lengths[2] + final_lengths[3],
                                    "1": final_lengths[2] + final_lengths[3],
                                    "2": final_lengths[3]},
               "retained_bytes": retained_bytes,
               "budget_bytes": BUDGET_BYTES,
               "budget_headroom_bytes": BUDGET_BYTES - retained_bytes}
    (HERE / "screen.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("seed_count", "selected_pairs", "available_linear_pairs",
                       "available_cyclic_pairs", "segment_lengths",
                       "retained_bytes", "budget_headroom_bytes",
                       "cover_sha256")}, sort_keys=True))


if __name__ == "__main__":
    main()
