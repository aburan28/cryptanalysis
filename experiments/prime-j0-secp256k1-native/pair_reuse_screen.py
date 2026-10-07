#!/usr/bin/env python3
"""Screen one-use reuse of adjacent nonzero tau-digit pair contributions."""

import hashlib
import json
from collections import Counter
from pathlib import Path

from seed_chain_bound import SEEDS, orbit, tau


HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixture.json"


def canonical(value):
    return min(orbit(value))


def from_signed_hex(value):
    return int(value, 16)


def reconstruct(digits):
    coefficient = (0, 0)
    for raw in reversed(digits):
        coefficient = tau(coefficient)
        if raw is not None:
            coefficient = coefficient[0] + raw[0], coefficient[1] + raw[1]
    return coefficient


def pair_row(case, offset, known_orbits):
    nonzero = [
        (i, (raw[0], raw[1]))
        for i, raw in enumerate(case["digits"])
        if raw is not None
    ][::-1]
    keys = []
    gaps = Counter()
    for (high_index, high), (low_index, low) in zip(
        nonzero[offset::2], nonzero[offset + 1::2]
    ):
        gap = high_index - low_index
        assert gap >= 4  # Frozen width-four nonadjacent digit stream.
        shifted = high
        for _ in range(gap):
            shifted = tau(shifted)
        keys.append(canonical((shifted[0] + low[0], shifted[1] + low[1])))
        gaps[gap] += 1
    frequencies = Counter(keys)
    return {
        "offset": offset,
        "pairs": len(keys),
        "distinct_pair_orbits": len(frequencies),
        "reuse_extras": sum(count - 1 for count in frequencies.values()),
        "max_repetitions_of_one_pair": max(frequencies.values(), default=0),
        "prepared_seed_hits": sum(key in known_orbits for key in keys),
        "gaps": dict(sorted(gaps.items())),
    }


def main():
    fixture_bytes = FIXTURE.read_bytes()
    fixture = json.loads(fixture_bytes)
    known_orbits = {canonical(seed) for seed in SEEDS.values()}
    assert len(known_orbits) == 9
    assert len(fixture["cases"]) == 64
    assert len({
        (case["base_x_hex"], case["base_y_hex"])
        for case in fixture["cases"]
    }) == 64
    cases = []
    for case in fixture["cases"]:
        assert reconstruct(case["digits"]) == (
            from_signed_hex(case["short_a_hex"]),
            from_signed_hex(case["short_b_hex"]),
        )
        arms = [pair_row(case, offset, known_orbits) for offset in (0, 1)]
        cases.append({"index": case["index"], "arms": arms})
    totals = []
    for offset in (0, 1):
        rows = [case["arms"][offset] for case in cases]
        totals.append({
            "offset": offset,
            "pairs": sum(row["pairs"] for row in rows),
            "distinct_within_base": sum(row["distinct_pair_orbits"] for row in rows),
            "reuse_extras": sum(row["reuse_extras"] for row in rows),
            "cases_with_reuse": sum(row["reuse_extras"] > 0 for row in rows),
            "prepared_seed_hits": sum(row["prepared_seed_hits"] for row in rows),
        })
    best_reuse = sum(max(arm["reuse_extras"] for arm in case["arms"])
                     for case in cases)
    assert [row["reuse_extras"] for row in totals] == [5, 10]
    assert best_reuse == 15
    assert all(row["prepared_seed_hits"] == 0 for row in totals)
    result = {
        "schema": 1,
        "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_dependency_sha256": hashlib.sha256(
            (HERE / "seed_chain_bound.py").read_bytes()
        ).hexdigest(),
        "cases": cases,
        "totals": totals,
        "per_case_best_reuse_extras": best_reuse,
        "optimistic_saved_M_plus_S_ceiling_at_14_per_reuse": 14 * best_reuse,
        "model": "disjoint adjacent nonzero pair points, two parity offsets per scalar, six-unit orbit folding, same-cost preparation and online addition; ignores tau-shift preparation and table overhead",
        "cpu_speedup_claim": None,
        "academic_novelty_claim": None,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
