#!/usr/bin/env python3
"""Materialize the exact Q1438 W<=4 N53 subgroup point base once."""

import argparse
import hashlib
import json
import resource
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
REPO = HERE.parents[2]
sys.path.insert(0, str(PARENT))
from enumerate_n83_weight5_full import necklaces  # noqa: E402
from enumerate_q1413_projected_x import canonical_rotation  # noqa: E402
from q1438_dense_base.enumerate_base import digest_keys  # noqa: E402
from run_probe import curves, field  # noqa: E402

sys.path.insert(0, str(REPO / "experiments/koblitz-pair-claw-20260929"))
from orbit_key import OrbitKey  # noqa: E402


BASE_RECEIPT = PARENT / "q1438_dense_base/n53_w4_base.json"
POINTS = HERE / "n53_w4_points.bin"
RECEIPT = HERE / "n53_w4_points_receipt.json"
WIDTH = 7


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cycle_to_coords(cycle_mask, coordinate_cycle):
    coords = 0
    while cycle_mask:
        bit = cycle_mask & -cycle_mask
        coords |= 1 << coordinate_cycle[bit.bit_length() - 1]
        cycle_mask ^= bit
    return coords


def build():
    assert not POINTS.exists() and not RECEIPT.exists(), "refuse overwrite"
    frozen = json.loads(BASE_RECEIPT.read_text())
    assert frozen["curve_id"] == "EC1N53Ckb1hf77aab617904"
    assert frozen["normal_basis_weight_bound"] == 4
    assert frozen["cofactor"] == 428
    n = 53
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    started = time.perf_counter()
    reps = {}
    raw_orbits = rational_orbits = 0
    for cycle_mask in necklaces(n, 4):
        raw_orbits += 1
        mask = cycle_to_coords(cycle_mask, orbit.coordinate_cycle)
        raw = curve.pointFromX(onb.fromCoords(mask))
        if raw is None:
            continue
        rational_orbits += 1
        projected = curve.mul(raw, frozen["cofactor"])
        if projected is None:
            continue
        key = canonical_rotation(orbit.cycle_bits(projected[0]), n)
        assert key not in reps, "Q1438 reported no projected orbit collision"
        reps[key] = projected
    assert len(reps) == frozen["signed_frobenius_columns_K"] == 3057
    assert digest_keys(set(reps), n) == frozen["enumerated_set_sha256"]
    assert raw_orbits == sum(row["raw_x_orbits"] for row in frozen["strata"])
    assert rational_orbits == sum(row["rational_x_orbits"]
                                  for row in frozen["strata"])
    points = []
    for key in sorted(reps):
        representative = reps[key]
        for shift in range(n):
            point = curve.frob(representative, shift)
            points.extend((point, curve.neg(point)))
    assert len(points) == frozen["actual_usable_points_B_before_folding"]
    assert len(set(points)) == len(points)
    encoded = sorted((onb.toCoords(x), onb.toCoords(y)) for x, y in points)
    assert len(set(encoded)) == len(encoded)
    temporary = POINTS.with_suffix(".bin.partial")
    assert not temporary.exists()
    with temporary.open("wb") as output:
        for x, y in encoded:
            output.write(x.to_bytes(WIDTH, "little"))
            output.write(y.to_bytes(WIDTH, "little"))
    temporary.replace(POINTS)
    elapsed = time.perf_counter() - started
    receipt = {
        "proposal_id": "Q1445",
        "candidate_id": None,
        "isogeny": "none",
        "curve_id": frozen["curve_id"],
        "normal_basis_weight_bound": 4,
        "factor_base_actual_B": len(points),
        "folded_columns_K": len(reps),
        "factor_base_enumerated_set_sha256": frozen[
            "enumerated_set_sha256"],
        "raw_x_orbits_tested": raw_orbits,
        "rational_x_orbits": rational_orbits,
        "point_encoding": (
            "sorted affine x,y normal-basis coordinate masks; "
            "each mask 7-byte little-endian"),
        "point_bytes": POINTS.stat().st_size,
        "point_file_sha256": sha(POINTS),
        "q1438_base_receipt_sha256": sha(BASE_RECEIPT),
        "source_sha256": sha(Path(__file__)),
        "base_construction_wall_seconds_exploratory": elapsed,
        "peak_parent_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "target_independent": True,
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def read_points():
    receipt = json.loads(RECEIPT.read_text())
    assert sha(POINTS) == receipt["point_file_sha256"]
    data = POINTS.read_bytes()
    assert len(data) == 2 * WIDTH * receipt["factor_base_actual_B"]
    encoded = []
    for pos in range(0, len(data), 2 * WIDTH):
        encoded.append((int.from_bytes(data[pos:pos + WIDTH], "little"),
                        int.from_bytes(data[pos + WIDTH:pos + 2 * WIDTH],
                                       "little")))
    assert encoded == sorted(set(encoded))
    onb = field.Onb(53)
    return [(onb.fromCoords(x), onb.fromCoords(y)) for x, y in encoded]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        receipt = json.loads(RECEIPT.read_text())
        assert len(read_points()) == receipt["factor_base_actual_B"]
        assert receipt["source_sha256"] == sha(Path(__file__))
        assert receipt["q1438_base_receipt_sha256"] == sha(BASE_RECEIPT)
        print("Q1445 N53 base: PASS")
    else:
        print(json.dumps(build(), sort_keys=True))
