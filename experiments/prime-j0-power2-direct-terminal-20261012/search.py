#!/usr/bin/env python3
"""Count exact direct-terminal orbits for the power-of-two positional format."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import gcd, isqrt
from pathlib import Path

import axis

HERE = Path(__file__).resolve().parent


def parity_count(low: int, high: int, parity: int) -> int:
    first = low + ((parity - low) & 1)
    return 0 if first > high else (high - first)//2 + 1


def disk_pairs(cap: int) -> int:
    """Count pairs with 3(a²+3ab+3b²) <= cap by exact square rows."""
    total = 0
    limit = isqrt(4*cap//9)
    for b in range(-limit, limit + 1):
        t_limit = isqrt((4*cap - 9*b*b)//3)
        total += parity_count(-t_limit, t_limit, b & 1)
    return total


def row(base: int) -> dict[str, int]:
    windows = axis.WINDOWS
    cap = (axis.RADIUS + sum(base**j for j in range(1, windows + 1)))**2 // base**(2*windows)
    pairs = disk_pairs(cap)
    assert pairs % 6 == 1  # all nonzero integer unit orbits have six points
    top_orbits = (pairs - 1)//6 + 1
    ordinary = (base*base + gcd(2, base)**2 + 2*gcd(3, base) + 2)//6
    return {"base": base, "windows": windows, "top_cap_3norm": cap,
            "top_pairs": pairs, "top_orbits": top_orbits,
            "ordinary_orbits_per_window": ordinary,
            "table_point_entries": windows*ordinary + top_orbits}


def audit() -> dict:
    selected = row(axis.BASE)
    assert selected == {"base": 256, "windows": 15, "top_cap_3norm": 66_051,
                        "top_pairs": 79_879, "top_orbits": 13_314,
                        "ordinary_orbits_per_window": 10_924,
                        "table_point_entries": 177_174}
    assert disk_pairs(0) == 1
    for cap in range(1, 40):
        direct = sum(3*axis.norm((a, b)) <= cap
                     for a in range(-10, 11) for b in range(-10, 11))
        assert direct == disk_pairs(cap)
    assert selected["top_orbits"] == axis.TOP_ENTRIES
    ranked_images = 1  # zero has one image
    for u in range(1, axis.U_MAX + 1):
        first, stop, offset = axis.TOP_ROWS[u]
        for b in range(first, stop):
            pair = (-u, b)
            assert axis.top_index(pair) == (offset + b - first, 0)
            for code, image in enumerate(axis.images(pair)):
                assert axis.top_index(image) == (offset + b - first, code)
                ranked_images += 1
    assert ranked_images == selected["top_pairs"]
    neighbors = [row(base) for base in range(250, 265)]
    return {"schema": 1, "status": "exact_direct_terminal_census",
            "selected": selected, "nearby_integer_radices": neighbors,
            "point_payload_bytes_at_64_each": 64*selected["table_point_entries"],
            "axis286_point_entries": 217_609, "u16_point_entries": 207_552,
            "axis_source_sha256": sha256((HERE / "axis.py").read_bytes()).hexdigest(),
            "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = (json.dumps(audit(), indent=2, sort_keys=True) + "\n").encode()
    target = HERE / "search.json"
    if args.write:
        if target.exists():
            raise SystemExit("search receipt exists; use --check")
        target.write_bytes(payload)
    elif target.read_bytes() != payload:
        raise SystemExit("search receipt differs from source")
    print(json.dumps(audit()["selected"], sort_keys=True))


if __name__ == "__main__":
    main()
