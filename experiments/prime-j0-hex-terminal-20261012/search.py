#!/usr/bin/env python3
"""Audit the exact Voronoi terminal census and independent-slot capacity bound."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

import hex

HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def audit() -> dict:
    assert all(hex.norm(vector) == hex.ORDER for vector in hex.NEIGHBORS)
    assert hex.twice_inner(hex.W, hex.V) == -hex.ORDER
    assert hex.U[0]*hex.V[1] - hex.U[1]*hex.V[0] == hex.ORDER
    assert 3*(hex.DIGIT_SUPPORT-1)**2 < 4*hex.RADIX**2*hex.ORDER
    assert 4*hex.RADIX**2*hex.ORDER <= 3*hex.DIGIT_SUPPORT**2
    assert hex.HEX_LIMIT*hex.POWER <= hex.ORDER + hex.DIGIT_SUPPORT*hex.DIGIT_WEIGHT_SUM
    assert hex.ORDER + hex.DIGIT_SUPPORT*hex.DIGIT_WEIGHT_SUM < (hex.HEX_LIMIT+1)*hex.POWER
    domain = {(a,b) for a in range(-hex.U_MAX, hex.U_MAX+1)
              for b in range(-hex.U_MAX, hex.U_MAX+1)
              if hex.in_domain((a,b))}
    assert len(domain) == 66_133
    assert (0,0) in domain
    assert all(set(hex.images(pair)) <= domain for pair in domain)
    assert len(domain) == 1 + 6*(hex.TOP_ENTRIES-1)
    seen = {(0,0)}
    for u in range(1, hex.U_MAX+1):
        first, stop, offset = hex.TOP_ROWS[u]
        assert offset == 1 + (len(seen)-1)//6
        for b in range(first, stop):
            pair = (-u,b)
            assert hex.sector(pair) and hex.in_domain(pair)
            assert hex.top_index(pair) == (offset+b-first,0)
            for code, image in enumerate(hex.images(pair)):
                assert image not in seen
                assert hex.top_index(image) == (offset+b-first,code)
                seen.add(image)
    assert seen == domain
    entries = 15*10_924 + hex.TOP_ENTRIES
    lower = hex.capacity_lower_entries()
    assert entries == 174_883 and lower == 174_777
    assert hex.independent_slot_capacity(lower-1) < hex.ORDER
    assert hex.independent_slot_capacity(lower) >= hex.ORDER
    return {
        "schema": 1, "status": "exact_voronoi_terminal_census",
        "curve": "secp256k1", "radix": hex.RADIX, "windows": hex.WINDOWS,
        "order": str(hex.ORDER), "lattice_u": list(hex.U), "lattice_v": list(hex.V),
        "voronoi_neighbors": [list(v) for v in hex.NEIGHBORS],
        "digit_support": str(hex.DIGIT_SUPPORT), "digit_weight_sum": str(hex.DIGIT_WEIGHT_SUM),
        "power": str(hex.POWER), "hex_limit": str(hex.HEX_LIMIT),
        "disk_cap_3norm": hex.DISK_CAP, "domain_pairs": len(domain),
        "terminal_orbits": hex.TOP_ENTRIES, "terminal_nonempty_rows": sum(
            first < stop for first,stop,_ in hex.TOP_ROWS),
        "ordinary_orbits_per_window": 10_924, "table_point_entries": entries,
        "point_payload_bytes_at_64_each": 64*entries,
        "direct_terminal_point_entries": 177_174,
        "independent_16_slot_capacity_lower_entries": lower,
        "capacity_gap_entries": entries-lower,
        "hex_source_sha256": digest(HERE / "hex.py"),
        "source_sha256": digest(Path(__file__)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = (json.dumps(audit(), indent=2, sort_keys=True) + "\n").encode()
    path = HERE / "search.json"
    if args.write:
        if path.exists():
            raise SystemExit("search receipt exists; use --check")
        path.write_bytes(data)
    elif path.read_bytes() != data:
        raise SystemExit("search receipt differs from source")
    print(json.dumps({"pairs": 66_133, "orbits": hex.TOP_ENTRIES,
                      "point_entries": 174_883, "capacity_lower_entries": 174_777}))


if __name__ == "__main__":
    main()
