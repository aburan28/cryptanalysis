#!/usr/bin/env python3
"""Freeze a 64 MiB budgeted cover by replacing adjacent tau triples."""

from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "prime-j0-power2-tau2-20261011/build_atlas.py"
SPEC = importlib.util.spec_from_file_location("three_image_atlas", PARENT)
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)

PAIR_BUDGET = 4_096
L3_BYTES = 64 * 1024 * 1024
FULL_ROWS = 12
TERMINAL_SEEDS = 9_288
MINIMUM_RETAINED_BYTES = 61_829_108


def digest(raw):
    return sha256(raw).hexdigest()


def covered_indices(segments, length):
    return [((start + exponent) % length)
            for start, span in segments for exponent in range(span)]


def main():
    canonical, nodes, direct, cycles = parent.parent.full_classes()
    orbit_sizes = Counter(canonical)
    original = Counter()
    modified = Counter()
    old_exp2_residues = 0
    new_exp2_residues = 0
    available_pairs = 0
    selected_pairs = 0
    records = []

    for cycle_index, cycle in enumerate(cycles):
        length = len(cycle)
        prior = parent.minimum_cycle_segments(cycle, direct)
        assert set(covered_indices(prior, length)) == set(range(length))
        assert len(covered_indices(prior, length)) == length
        original.update(span for _, span in prior)
        old_exp2_residues += sum(orbit_sizes[cycle[(start + 2) % length]]
                                 for start, span in prior if span == 3)

        current = []
        index = 0
        while index < len(prior):
            if (index + 1 < len(prior) and prior[index][1] == 3
                    and prior[index + 1][1] == 3):
                start = prior[index][0]
                assert prior[index + 1][0] == (start + 3) % length
                available_pairs += 1
                if selected_pairs < PAIR_BUDGET:
                    current.extend((((start + 2 * offset) % length, 2)
                                    for offset in range(3)))
                    selected_pairs += 1
                else:
                    current.extend(prior[index:index + 2])
                index += 2
            else:
                current.append(prior[index])
                index += 1

        assert len(covered_indices(current, length)) == length
        assert set(covered_indices(current, length)) == set(range(length))
        for start, span in current:
            if span >= 2:
                assert 3 * parent.screen.norm(direct[cycle[start]]) <= 1024 ** 2
            if span == 3:
                assert 9 * parent.screen.norm(direct[cycle[start]]) <= 1024 ** 2
            assert start < 1 << 16 and cycle_index < 1 << 16
            records.append(struct.pack("<HHB", cycle_index, start, span))
        modified.update(span for _, span in current)
        new_exp2_residues += sum(orbit_sizes[cycle[(start + 2) % length]]
                                 for start, span in current if span == 3)

    assert len(nodes) == 174_764 and len(cycles) == 513
    assert available_pairs == 7_586 and selected_pairs == PAIR_BUDGET
    assert original == {1: 69, 2: 45_349, 3: 27_999}
    assert modified == {1: 69, 2: 57_637, 3: 19_807}
    old_seeds = sum(original.values())
    new_seeds = sum(modified.values())
    assert (old_seeds, new_seeds) == (73_417, 77_513)
    lower_bound = len(nodes) - 2 * new_seeds
    assert modified[3] - lower_bound == modified[1] == 69
    retained_bytes = MINIMUM_RETAINED_BYTES + selected_pairs * (FULL_ROWS * 64 + 4)
    assert retained_bytes == 64_991_220 and retained_bytes < L3_BYTES
    slots = FULL_ROWS * new_seeds + TERMINAL_SEEDS
    assert slots == 939_444

    binary = b"CB64" + struct.pack("<II", len(cycles), len(records)) + b"".join(records)
    plan = HERE / "cover-plan.bin"
    plan.write_bytes(binary)
    receipt = {
        "schema": 1, "status": "constructed",
        "generator_sha256": digest(Path(__file__).read_bytes()),
        "parent_generator_sha256": digest(PARENT.read_bytes()),
        "parent_atlas_receipt_sha256": digest(
            (PARENT.parent / "atlas-receipt.json").read_bytes()),
        "pair_budget": PAIR_BUDGET,
        "available_disjoint_pairs": available_pairs,
        "selected_pairs": selected_pairs,
        "unit_classes": len(nodes),
        "cycles": len(cycles),
        "original_segment_lengths": dict(original),
        "budgeted_segment_lengths": dict(modified),
        "original_full_seeds": old_seeds,
        "budgeted_full_seeds": new_seeds,
        "original_exponent_two_classes": original[3],
        "budgeted_exponent_two_classes": modified[3],
        "original_exponent_two_residues": old_exp2_residues,
        "budgeted_exponent_two_residues": new_exp2_residues,
        "universal_exponent_two_lower_bound": lower_bound,
        "gap_to_lower_bound": modified[3] - lower_bound,
        "affine_slots": slots,
        "projected_retained_bytes": retained_bytes,
        "reported_cache_bytes": L3_BYTES,
        "nominal_cache_headroom_bytes": L3_BYTES - retained_bytes,
        "cover_plan_bytes": len(binary),
        "cover_plan_sha256": digest(binary),
    }
    output = HERE / "screen.json"
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
