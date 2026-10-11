#!/usr/bin/env python3
"""Freeze a panel-independent expanded tau cover for a succinct orbit atlas."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-power2-tau2-20261011/build_atlas.py"
SPEC = importlib.util.spec_from_file_location("minimum_tau_cover", PARENT)
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)

SPLIT_BUDGET = 2_048
RADIX = 1_024
WINDOWS = 12
TERMINAL_SEEDS = 9_288


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    canonical, nodes, direct, cycles = parent.parent.full_classes()
    orbit_sizes = Counter(canonical)
    before = Counter()
    after = Counter()
    available_pairs = 0
    selected_pairs = 0
    selected_splits = 0
    records = []
    before_exp2 = after_exp2 = 0

    for cycle_index, cycle in enumerate(cycles):
        length = len(cycle)
        baseline = parent.minimum_cycle_segments(cycle, direct)
        before.update(span for _, span in baseline)
        before_exp2 += sum(orbit_sizes[cycle[(start + 2) % length]]
                           for start, span in baseline if span == 3)
        paired = []
        index = 0
        while index < len(baseline):
            if (index + 1 < len(baseline) and baseline[index][1] == 3
                    and baseline[index + 1][1] == 3):
                start = baseline[index][0]
                assert baseline[index + 1][0] == (start + 3) % length
                available_pairs += 1
                paired.extend((((start + 2 * offset) % length, 2)
                               for offset in range(3)))
                selected_pairs += 1
                index += 2
            else:
                paired.append(baseline[index])
                index += 1

        current = []
        for start, span in paired:
            if span == 3 and selected_splits < SPLIT_BUDGET:
                current.extend(((start, 2), ((start + 2) % length, 1)))
                selected_splits += 1
            else:
                current.append((start, span))
        covered = [((start + offset) % length)
                   for start, span in current for offset in range(span)]
        assert len(covered) == length and set(covered) == set(range(length))
        for start, span in current:
            assert (3 ** (span - 1)) * parent.screen.norm(direct[cycle[start]]) \
                <= RADIX ** 2
            assert cycle_index < 1 << 16 and start < 1 << 16
            records.append(struct.pack("<HHB", cycle_index, start, span))
        after.update(span for _, span in current)
        after_exp2 += sum(orbit_sizes[cycle[(start + 2) % length]]
                          for start, span in current if span == 3)

    assert len(nodes) == 174_764 and len(cycles) == 513
    assert before == {1: 69, 2: 45_349, 3: 27_999}
    assert available_pairs == selected_pairs == 7_586
    assert selected_splits == SPLIT_BUDGET
    assert after == {1: 2_117, 2: 70_155, 3: 10_779}
    seeds = sum(after.values())
    assert seeds == 83_051
    lower_bound = len(nodes) - 2 * seeds
    assert after[3] - lower_bound == after[1]

    binary = b"OQ64" + struct.pack("<II", len(cycles), len(records)) + b"".join(records)
    (HERE / "cover-plan.bin").write_bytes(binary)
    receipt = {"schema": 1, "status": "constructed",
               "generator_sha256": digest(Path(__file__).read_bytes()),
               "parent_generator_sha256": digest(PARENT.read_bytes()),
               "parent_atlas_receipt_sha256": digest(
                   (PARENT.parent / "atlas-receipt.json").read_bytes()),
               "cycles": len(cycles), "unit_classes": len(nodes),
               "original_segment_lengths": dict(before),
               "expanded_segment_lengths": dict(after),
               "original_exponent_two_residues": before_exp2,
               "expanded_exponent_two_residues": after_exp2,
               "available_disjoint_pairs": available_pairs,
               "selected_pairs": selected_pairs,
               "selected_single_splits": selected_splits,
               "full_seeds": seeds,
               "terminal_seeds": TERMINAL_SEEDS,
               "affine_slots": WINDOWS * seeds + TERMINAL_SEEDS,
               "universal_exponent_two_lower_bound": lower_bound,
               "gap_to_lower_bound": after[3] - lower_bound,
               "cover_plan_bytes": len(binary),
               "cover_plan_sha256": digest(binary)}
    (HERE / "screen.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
