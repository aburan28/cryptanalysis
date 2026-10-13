#!/usr/bin/env python3
"""Enumerate rational, subgroup-usable affine width-11 seed coordinates."""

import json
from pathlib import Path

from m6 import DIMENSION, HERE, N, OFFSET, runner


def main():
    bitset_path = HERE / "valid_seed_bits.bin"
    receipt_path = HERE / "valid_seeds.json"
    assert not bitset_path.exists() and not receipt_path.exists()
    width = runner.ROOT / "experiments/n83-geometric-two-shift11-20261012"
    frontier_path = width / "screen.json"
    frontier = json.loads(frontier_path.read_text())
    assert frontier["best_shift_coordinates"] == [26, 38]
    assert frontier["best_K"] == 1109
    row = frontier["competitive_full_scans"][0]
    onb = runner.field.Onb(N)
    curve = runner.curves.Curve(onb)
    order = 2417851639230796216685689
    bits = bytearray((1 << DIMENSION) // 8)
    valid = 0
    projected_identity = 0
    for free in range(1 << DIMENSION):
        point = curve.pointFromX(onb.fromCoords(OFFSET | free))
        if point is None:
            continue
        projected = curve.mul(point, 4)
        if projected is None:
            projected_identity += 1
            continue
        assert curve.mul(projected, order) is None
        bits[free >> 3] |= 1 << (free & 7)
        valid += 1
    assert valid == row["valid_lifts"] == 1109
    assert projected_identity == row["identity_projections"] == 0
    assert (1 << DIMENSION) - valid == 939
    bitset_path.write_bytes(bits)
    receipt = {
        "status": "PASS", "kind": "n83_width11_valid_seed_bitset_v1",
        "curve_id": frontier["curve_id"], "dimension": DIMENSION,
        "offset_onb_coordinates": OFFSET,
        "seed_count": 1 << DIMENSION,
        "valid_seed_count": valid,
        "invalid_seed_count": (1 << DIMENSION) - valid,
        "projected_identity_count": projected_identity,
        "bitset_file": bitset_path.name,
        "bitset_sha256": runner.sha(bitset_path),
        "bitset_bytes": len(bits),
        "frontier_sha256": runner.sha(frontier_path),
        "source_sha256": runner.sha(Path(__file__)),
    }
    runner.save(receipt_path, receipt)
    print(json.dumps({"status": "PASS", "valid": valid,
                      "invalid": receipt["invalid_seed_count"]}), flush=True)


if __name__ == "__main__":
    main()
