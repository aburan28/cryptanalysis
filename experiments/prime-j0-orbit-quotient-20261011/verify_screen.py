#!/usr/bin/env python3
"""Independently check every class in the expanded tau cover."""

from collections import Counter, defaultdict
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "prime-j0-power2-cache-budget-20261011/verify_screen.py"
SPEC = importlib.util.spec_from_file_location("independent_cycles", REFERENCE)
reference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reference)
RADIX_SQUARED = 1_024 * 1_024


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    raw = (HERE / "cover-plan.bin").read_bytes()
    assert raw[:4] == b"OQ64"
    cycle_count, segment_count = struct.unpack_from("<II", raw, 4)
    assert len(raw) == 12 + 5 * segment_count
    recorded = defaultdict(list)
    for cycle_index, start, span in struct.iter_unpack("<HHB", raw[12:]):
        assert cycle_index < cycle_count and 1 <= span <= 3
        recorded[cycle_index].append((start, span))

    cycles, nearest, orbit_sizes = reference.independent_cycles()
    assert cycle_count == len(cycles) == 513
    before = Counter()
    after = Counter()
    selected_pairs = selected_splits = 0
    exp2_residues = 0
    for cycle_index, cycle in enumerate(cycles):
        length = len(cycle)
        baseline = reference.minimum_plan(cycle, nearest)
        before.update(span for _, span in baseline)
        paired = []
        position = 0
        while position < len(baseline):
            if (position + 1 < len(baseline) and baseline[position][1] == 3
                    and baseline[position + 1][1] == 3):
                start = baseline[position][0]
                assert baseline[position + 1][0] == (start + 3) % length
                paired.extend(((start + 2 * offset) % length, 2)
                              for offset in range(3))
                selected_pairs += 1
                position += 2
            else:
                paired.append(baseline[position])
                position += 1

        expected = []
        for start, span in paired:
            if span == 3 and selected_splits < 2_048:
                expected.extend(((start, 2), ((start + 2) % length, 1)))
                selected_splits += 1
            else:
                expected.append((start, span))
        assert recorded[cycle_index] == expected
        covered = [((start + offset) % length)
                   for start, span in expected for offset in range(span)]
        assert len(covered) == length and set(covered) == set(range(length))
        for start, span in expected:
            assert start < length
            assert (3 ** (span - 1)) * reference.reference.norm(
                nearest[cycle[start]]) <= RADIX_SQUARED
        after.update(span for _, span in expected)
        exp2_residues += sum(orbit_sizes[cycle[(start + 2) % length]]
                             for start, span in expected if span == 3)

    assert before == {1: 69, 2: 45_349, 3: 27_999}
    assert after == {1: 2_117, 2: 70_155, 3: 10_779}
    assert (selected_pairs, selected_splits) == (7_586, 2_048)
    assert segment_count == sum(after.values()) == 83_051
    assert exp2_residues == 64_674
    screen = json.loads((HERE / "screen.json").read_bytes())
    assert screen["cover_plan_sha256"] == digest(raw)
    assert screen["expanded_exponent_two_residues"] == exp2_residues
    receipt = {"schema": 1, "status": "passed",
               "verifier_sha256": digest(Path(__file__).read_bytes()),
               "reference_verifier_sha256": digest(REFERENCE.read_bytes()),
               "cover_plan_sha256": digest(raw),
               "cycles": len(cycles), "unit_classes": 174_764,
               "selected_pairs": selected_pairs,
               "selected_single_splits": selected_splits,
               "full_seeds": segment_count,
               "exponent_two_residues": exp2_residues}
    output = HERE / "independent-check.json"
    if output.exists():
        assert json.loads(output.read_text()) == receipt
    else:
        output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
