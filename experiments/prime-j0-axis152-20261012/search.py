#!/usr/bin/env python3
"""Exact point-entry census for the sixteen-window axis-factorized format."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import gcd, isqrt
from pathlib import Path

HERE = Path(__file__).resolve().parent
WINDOWS = 16
START = 130
STOP = 162
INITIAL_RADIUS = 1 << 128


def row(base: int) -> dict[str, int]:
    assert base >= 2
    digit_radius = sum(base**j for j in range(1, WINDOWS + 1))
    cap = (INITIAL_RADIUS + digit_radius)**2 // base**(2 * WINDOWS)
    # In the unit sector (-u,b), 12Q=9(2b-u)^2+3u^2 and
    # u <= 3b < 2u.  Zero is implicit in both axis tables.
    u_max = isqrt(4 * cap // 3)
    b_max = (2 * u_max - 1) // 3 if u_max else 0
    ordinary = (base**2 + gcd(2, base)**2 + 2*gcd(3, base) + 2) // 6
    entries = WINDOWS * ordinary + u_max + b_max
    return {
        "base": base,
        "top_cap_3norm": cap,
        "axis_a_positive_entries": u_max,
        "axis_b_positive_entries": b_max,
        "ordinary_orbits_per_window": ordinary,
        "point_entries": entries,
        "point_payload_bytes_at_64_each": 64 * entries,
    }


def audit() -> dict:
    # Directly audit Burnside's count at the selected even radix, including
    # nonzero fixed residues under the six-unit action.
    base = 152
    seen: set[tuple[int, int]] = set()
    orbit_count = 0
    for a in range(base):
        for b in range(base):
            if (a, b) in seen:
                continue
            images = {
                (a, b), (-a % base, -b % base),
                ((a+3*b) % base, (-a-2*b) % base),
                ((-a-3*b) % base, (a+2*b) % base),
                ((-2*a-3*b) % base, (a+b) % base),
                ((2*a+3*b) % base, (-a-b) % base),
            }
            seen.update(images)
            orbit_count += 1
    assert len(seen) == base**2
    assert orbit_count == row(base)["ordinary_orbits_per_window"] == 3_852

    rows = [row(base) for base in range(START, STOP + 1)]
    ranked = sorted(rows, key=lambda item: (item["point_entries"], item["base"]))
    winner = ranked[0]
    assert winner == {
        "base": 152, "top_cap_3norm": 17_574_891,
        "axis_a_positive_entries": 4_840,
        "axis_b_positive_entries": 3_226,
        "ordinary_orbits_per_window": 3_852,
        "point_entries": 69_698,
        "point_payload_bytes_at_64_each": 4_460_672,
    }
    assert ranked[1]["base"] == 153 and ranked[1]["point_entries"] == 69_711

    # For 2 <= B <= 130, the exact radius ratio
    # 2^128/B^16 + sum(B^-k for k=0..15) decreases with B.  Thus
    # cap, u_max and b_max are at least their values at B=130.
    lower_tail = row(START)
    assert lower_tail["axis_a_positive_entries"] + \
        lower_tail["axis_b_positive_entries"] == 98_416 > winner["point_entries"]
    # For B >= 162, Burnside's numerator is at least B^2, so the
    # ordinary tables alone exceed the winner.
    assert WINDOWS * STOP**2 // 6 == 69_984 > winner["point_entries"]
    return {
        "schema": 1, "status": "global_integer_radix_point_entry_minimum",
        "radix_domain": "all integers at least two",
        "exact_interval_inclusive": [START, STOP],
        "ordinary_windows": WINDOWS,
        "winner": winner,
        "runner_up": ranked[1],
        "lower_tail_axis_entry_floor": 98_416,
        "upper_tail_ordinary_entry_floor": 69_984,
        "all_rows": rows,
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = (json.dumps(audit(), sort_keys=True, indent=2) + "\n").encode()
    path = HERE / "search.json"
    if args.write:
        if path.exists():
            raise SystemExit("search receipt exists; use --check")
        path.write_bytes(payload)
    elif path.read_bytes() != payload:
        raise SystemExit("search receipt differs from frozen source")
    print("radix 152 is the unique point-entry minimum for all integer radices >= 2")


if __name__ == "__main__":
    main()
