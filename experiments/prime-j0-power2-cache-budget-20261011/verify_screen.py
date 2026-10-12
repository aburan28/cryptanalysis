#!/usr/bin/env python3
"""Independently check the cache-budgeted cover on every full unit class."""

from array import array
from collections import Counter, defaultdict
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct


HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "prime-j0-power2-tau2-20261011/verify_atlas.py"
SPEC = importlib.util.spec_from_file_location("independent_three_image", REFERENCE)
reference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reference)
SIZE = 1024 * 1024
EMPTY = 0xFFFFFFFF


def digest(raw):
    return sha256(raw).hexdigest()


def independent_cycles():
    canonical = array("I", [EMPTY]) * SIZE
    nodes = []
    for slot in range(SIZE):
        if canonical[slot] != EMPTY:
            continue
        orbit = [reference.residue(image)
                 for image in reference.units(divmod(slot, 1024))]
        assert min(orbit) == slot
        for member in orbit:
            assert canonical[member] in (EMPTY, slot)
            canonical[member] = slot
        nodes.append(slot)
    assert EMPTY not in canonical and len(nodes) == 174_764
    orbit_sizes = Counter(canonical)
    nearest = {node: reference.nearest_wide_search(node) for node in nodes}
    successor = {node: canonical[reference.residue(reference.tau(nearest[node]))]
                 for node in nodes}
    assert set(successor.values()) == set(nodes)
    seen = set()
    cycles = []
    for origin in nodes:
        if origin in seen:
            continue
        cycle = []
        node = origin
        while node not in seen:
            seen.add(node)
            cycle.append(node)
            node = successor[node]
        assert node == origin
        cycles.append(cycle)
    assert len(cycles) == 513 and len(seen) == len(nodes)
    return cycles, nearest, orbit_sizes


def minimum_plan(cycle, nearest):
    length = len(cycle)
    best = None
    for backward in range(min(3, length)):
        first = (-backward) % length
        cost = [length + 1] * (length + 1)
        previous = [None] * (length + 1)
        cost[0] = 0
        for position in range(length):
            node = cycle[(first + position) % length]
            max_span = (3 if 9 * reference.norm(nearest[node]) <= SIZE else 2)
            for span in (3, 2, 1):
                endpoint = position + span
                if span > max_span or endpoint > length:
                    continue
                if cost[position] + 1 < cost[endpoint]:
                    cost[endpoint] = cost[position] + 1
                    previous[endpoint] = position, span
        segments = []
        endpoint = length
        while endpoint:
            position, span = previous[endpoint]
            segments.append(((first + position) % length, span))
            endpoint = position
        candidate = cost[length], backward, list(reversed(segments))
        if best is None or candidate[:2] < best[:2]:
            best = candidate
    return best[2]


def main():
    raw = (HERE / "cover-plan.bin").read_bytes()
    assert raw[:4] == b"CB64"
    cycle_count, segment_count = struct.unpack_from("<II", raw, 4)
    assert len(raw) == 12 + 5 * segment_count
    recorded = defaultdict(list)
    for cycle_index, start, span in struct.iter_unpack("<HHB", raw[12:]):
        assert cycle_index < cycle_count and 1 <= span <= 3
        recorded[cycle_index].append((start, span))

    cycles, nearest, orbit_sizes = independent_cycles()
    assert cycle_count == len(cycles)
    original = Counter()
    actual = Counter()
    available_pairs = selected_pairs = 0
    original_exp2_residues = actual_exp2_residues = 0
    for cycle_index, cycle in enumerate(cycles):
        length = len(cycle)
        baseline = minimum_plan(cycle, nearest)
        original.update(span for _, span in baseline)
        original_exp2_residues += sum(orbit_sizes[cycle[(start + 2) % length]]
                                      for start, span in baseline if span == 3)
        expected = []
        position = 0
        while position < len(baseline):
            if (position + 1 < len(baseline) and baseline[position][1] == 3
                    and baseline[position + 1][1] == 3):
                start = baseline[position][0]
                assert baseline[position + 1][0] == (start + 3) % length
                available_pairs += 1
                if selected_pairs < 4_096:
                    expected.extend(((start + 2 * shift) % length, 2)
                                    for shift in range(3))
                    selected_pairs += 1
                else:
                    expected.extend(baseline[position:position + 2])
                position += 2
            else:
                expected.append(baseline[position])
                position += 1
        assert recorded[cycle_index] == expected
        covered = [((start + shift) % length)
                   for start, span in expected for shift in range(span)]
        assert len(covered) == length and set(covered) == set(range(length))
        for start, span in expected:
            assert start < length
            assert (3 ** (span - 1)) * reference.norm(nearest[cycle[start]]) <= SIZE
        actual.update(span for _, span in expected)
        actual_exp2_residues += sum(orbit_sizes[cycle[(start + 2) % length]]
                                    for start, span in expected if span == 3)

    assert (available_pairs, selected_pairs) == (7_586, 4_096)
    assert original == {1: 69, 2: 45_349, 3: 27_999}
    assert actual == {1: 69, 2: 57_637, 3: 19_807}
    assert (original_exp2_residues, actual_exp2_residues) == (167_994, 118_842)
    assert segment_count == sum(actual.values()) == 77_513
    assert 174_764 - 2 * segment_count == 19_738
    parent_native = json.loads((HERE.parent / "prime-j0-power2-tau2-20261011"
                                / "native-targeted.json").read_bytes())
    retained = parent_native["retained_bytes"] + 4_096 * (12 * 64 + 4)
    assert retained == 64_991_220 < 64 * 1024 * 1024

    constructed = json.loads((HERE / "screen.json").read_bytes())
    assert constructed["cover_plan_sha256"] == digest(raw)
    assert constructed["budgeted_exponent_two_residues"] == actual_exp2_residues
    assert constructed["projected_retained_bytes"] == retained
    receipt = {"schema": 1, "status": "passed",
               "verifier_sha256": digest(Path(__file__).read_bytes()),
               "reference_verifier_sha256": digest(REFERENCE.read_bytes()),
               "cover_plan_sha256": digest(raw),
               "cycles": len(cycles), "unit_classes": 174_764,
               "available_disjoint_pairs": available_pairs,
               "selected_pairs": selected_pairs,
               "full_seeds": segment_count,
               "exponent_two_classes": actual[3],
               "exponent_two_residues": actual_exp2_residues,
               "projected_retained_bytes": retained}
    receipt = json.loads(json.dumps(receipt, sort_keys=True))
    output = HERE / "independent-check.json"
    if output.exists():
        assert json.loads(output.read_text()) == receipt
    else:
        output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
