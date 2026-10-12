#!/usr/bin/env python3
"""Enumerate seed-only and orbit-complete N83 leaf domains exactly."""

import hashlib
import json
import math
import sys
from decimal import Decimal, localcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FRONTIER = ROOT / "experiments/koblitz-n83-index-design-20260929/Q20261012_N83_WIDTH_FRONTIER"
sys.path[:0] = [str(ROOT / "ecc2k130/runner/codegen"),
                str(ROOT / "experiments/koblitz-pair-claw-20260929")]

import curves  # noqa: E402
import field  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def first_moment(count, order):
    with localcontext() as context:
        context.prec = 50
        return str(Decimal(math.comb(count, 5)) / Decimal(order))


def main():
    output = HERE / "coverage.json"
    assert not output.exists()
    frontier_path = FRONTIER / "frontier.json"
    frontier = json.loads(frontier_path.read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert sha(frontier_path) == protocol["parent_frontier_sha256"]
    order = protocol["workload"]["subgroup_order"]
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    rows = []
    for dimension in (11, 12, 13):
        row = next(row for row in frontier["rows"]
                   if row["dimension"] == dimension and
                   row["offset_onb_coordinates"] == 1 << 81)
        key_path = FRONTIER / row["canonical_key_file"]
        assert sha(key_path) == row["canonical_key_sha256"]
        signed_seeds = set()
        keys = set()
        valid = 0
        for low in range(1 << dimension):
            raw = (1 << 81) | low
            point = curve.pointFromX(onb.fromCoords(raw))
            if point is None:
                continue
            valid += 1
            projected = curve.mul(point, 4)
            assert projected is not None
            signed_seeds.add(projected)
            signed_seeds.add(curve.neg(projected))
            keys.add(orbit.canonical(projected)[0])
        assert valid == row["valid_lifts"]
        assert len(keys) == row["folded_columns_K"]
        assert len(signed_seeds) == 2 * valid
        assert b"".join(key.to_bytes(21, "little")
                        for key in sorted(keys)) == key_path.read_bytes()
        full = set()
        for point in signed_seeds:
            for power in range(83):
                full.add(curve.frob(point, power))
        assert len(full) == row["actual_usable_points_B_before_folding"]
        assert first_moment(len(full), order) == row[
            "five_subset_first_moment"]
        rows.append({
            "dimension": dimension,
            "valid_rational_seed_x": valid,
            "seed_signed_projected_points": len(signed_seeds),
            "full_signed_frobenius_points": len(full),
            "folded_columns": len(keys),
            "seed_five_subset_first_moment": first_moment(
                len(signed_seeds), order),
            "full_five_subset_first_moment": first_moment(len(full), order),
            "key_file_sha256": sha(key_path),
        })
        print(json.dumps(rows[-1]), flush=True)
    record = {
        "kind": "n83_shifted_affine_seed_vs_full_frobenius_coverage",
        "status": "PASS",
        "curve_id": protocol["curve_id"],
        "source_sha256": sha(Path(__file__)),
        "protocol_sha256": sha(HERE / "protocol.json"),
        "frontier_sha256": sha(frontier_path),
        "sage_runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "rows": rows,
    }
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
