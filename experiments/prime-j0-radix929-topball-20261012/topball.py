#!/usr/bin/env python3
"""Exhaustively audit the bounded top-state table and its arithmetic rank."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import isqrt
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
CAP = 679_762
MAX_ROW = 952


def norm(pair: tuple[int, int]) -> int:
    a, b = pair
    return a * a + 3 * a * b + 3 * b * b


def images(pair: tuple[int, int]) -> tuple[tuple[int, int], ...]:
    a, b = pair
    return ((a, b), (-a, -b), (a + 3*b, -a - 2*b),
            (-a - 3*b, a + 2*b), (-2*a - 3*b, a + b),
            (2*a + 3*b, -a - b))


def sector(pair: tuple[int, int]) -> bool:
    a, b = pair
    return a < 0 and -a <= 3*b < -2*a


def ceildiv(a: int, b: int) -> int:
    return -((-a) // b)


def row_bounds(u: int) -> tuple[int, int]:
    disc = 4 * CAP - 3 * u * u
    if disc < 0:
        return (1, 0)
    h = isqrt(disc // 9)
    lo = max(ceildiv(u, 3), ceildiv(u - h, 2))
    hi = min((2*u - 1) // 3, (u + h) // 2)
    return lo, hi


def audit() -> dict:
    prefix = [0]
    digest = sha256()
    seen: set[tuple[int, int]] = {(0, 0)}
    orbit_count = 1
    for u in range(1, MAX_ROW + 1):
        lo, hi = row_bounds(u)
        prefix.append(prefix[-1] + max(0, hi - lo + 1))
        for b in range(lo, hi + 1):
            canonical = (-u, b)
            assert sector(canonical) and 3 * norm(canonical) <= CAP
            assert 12 * norm(canonical) == 9 * (2*b-u)**2 + 3*u*u
            rank = 1 + prefix[u - 1] + b - lo
            assert rank == orbit_count
            digest.update(struct.pack("<hh", *canonical))
            all_images = images(canonical)
            assert len(set(all_images)) == 6
            assert sum(sector(pair) for pair in all_images) == 1
            for pair in all_images:
                assert pair not in seen and norm(pair) == norm(canonical)
                seen.add(pair)
                selected = [candidate for candidate in images(pair) if sector(candidate)]
                assert selected == [canonical]
                v = -selected[0][0]
                low, high = row_bounds(v)
                assert low <= selected[0][1] <= high
                assert 1 + prefix[v - 1] + selected[0][1] - low == rank
            orbit_count += 1
    assert orbit_count == 136_993
    assert len(seen) == 821_953
    for a in range(-MAX_ROW, MAX_ROW + 1):
        for b in range(-MAX_ROW, MAX_ROW + 1):
            if 3 * norm((a, b)) <= CAP:
                assert (a, b) in seen
    assert prefix[-1] == orbit_count - 1
    prefix_bytes = b"".join(struct.pack("<I", count) for count in prefix)
    return {
        "schema": 1,
        "status": "exact_exhaustive_top_table_audit",
        "radix": 929,
        "top_bound_3norm": CAP,
        "top_states": len(seen),
        "top_unit_orbits": orbit_count,
        "top_max_row": MAX_ROW,
        "prefix_rows": len(prefix),
        "prefix_bytes_at_4_each": len(prefix_bytes),
        "prefix_sha256": sha256(prefix_bytes).hexdigest(),
        "canonical_top_pairs_sha256": digest.hexdigest(),
        "ordinary_orbits_per_window": (929 * 929 + 5) // 6,
        "table_point_entries": 12 * ((929 * 929 + 5) // 6) + orbit_count,
        "table_point_bytes_at_64_each": (12 * ((929 * 929 + 5) // 6) + orbit_count) * 64,
        "reference_radix943_point_entries": 13 * 148_209,
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    receipt = audit()
    payload = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    output = HERE / "topball.json"
    if args.write:
        if output.exists():
            raise SystemExit("topball receipt exists; use --check")
        output.write_bytes(payload)
        print(json.dumps(receipt, sort_keys=True))
    elif output.read_bytes() != payload:
        raise SystemExit("topball audit differs from frozen receipt")
    else:
        print("exact top-state table and arithmetic rank verified")


if __name__ == "__main__":
    main()
