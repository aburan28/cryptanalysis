#!/usr/bin/env python3
"""Exact bound-based table census for thirteen ordinary radix windows."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import gcd, isqrt
from pathlib import Path

HERE = Path(__file__).resolve().parent
START = 500
STOP = 700
WINDOWS = 13


def top_state_count(cap: int) -> int:
    # 4*(3Q(a,b)) = 3a^2 + 9(a+2b)^2. For fixed a, t=a+2b
    # runs over integers with the parity of a.
    limit = isqrt(4 * cap // 3)
    total = 0
    for a in range(-limit, limit + 1):
        tmax = isqrt((4 * cap - 3 * a * a) // 9)
        total += 2 * (tmax // 2) + 1 if a % 2 == 0 else 2 * ((tmax + 1) // 2)
    assert (total + 5) % 6 == 0
    return total


def ordinary_orbits(base: int) -> int:
    # Burnside for the six-unit action on (Z/base Z)^2.
    numerator = base * base + gcd(2, base) ** 2 + 2 * gcd(3, base) + 2
    assert numerator % 6 == 0
    return numerator // 6


def row(base: int) -> dict[str, int]:
    radius = sum(base ** j for j in range(1, WINDOWS + 1))
    numerator = ((1 << 128) + radius) ** 2
    denominator = base ** (2 * WINDOWS)
    cap = numerator // denominator
    states = top_state_count(cap)
    ordinary = ordinary_orbits(base)
    top = (states + 5) // 6
    return {
        "base": base, "ordinary_orbits_per_window": ordinary,
        "top_cap_3norm": cap, "top_states": states, "top_orbits": top,
        "point_entries": WINDOWS * ordinary + top,
        "point_payload_bytes_at_64_each": 64 * (WINDOWS * ordinary + top),
    }


def audit() -> dict:
    # Small direct enumeration checks the parity-count formula independently.
    for cap in range(30):
        limit = isqrt(4 * cap // 3)
        direct = sum(
            3 * (a * a + 3 * a * b + 3 * b * b) <= cap
            for a in range(-limit, limit + 1)
            for b in range(-limit, limit + 1)
        )
        assert top_state_count(cap) == direct
    rows = [row(base) for base in range(START, STOP + 1)]
    winner = min(rows, key=lambda item: (item["point_entries"], item["base"]))
    assert winner == {
        "base": 569, "ordinary_orbits_per_window": 53_961,
        "top_cap_3norm": 270_666, "top_states": 327_235,
        "top_orbits": 54_540, "point_entries": 756_033,
        "point_payload_bytes_at_64_each": 48_386_112,
    }
    return {
        "schema": 1, "status": "exact_bound_based_radix_census",
        "radix_interval_inclusive": [START, STOP], "ordinary_windows": WINDOWS,
        "ranked": sorted(rows, key=lambda item: (item["point_entries"], item["base"])),
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = (json.dumps(audit(), indent=2, sort_keys=True) + "\n").encode()
    path = HERE / "radix-search.json"
    if args.write:
        if path.exists():
            raise SystemExit("radix census already exists; use --check")
        path.write_bytes(payload)
    elif path.read_bytes() != payload:
        raise SystemExit("radix census differs from frozen source")
    print("exact radix census verified: 569 is the point-entry minimum on 500..700")


if __name__ == "__main__":
    main()
