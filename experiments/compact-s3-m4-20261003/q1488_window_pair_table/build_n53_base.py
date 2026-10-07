#!/usr/bin/env python3
"""Materialize every Q1481 N53 window-base point from packed projected x keys."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1481 = PARENT / "q1481_window_orbit_base"
sys.path.insert(0, str(PARENT))
from run_probe import curves, field  # noqa: E402
sys.path.insert(0, str(Q1481))
from enumerate_base import onb_x_from_cycle_mask  # noqa: E402
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))
from orbit_key import OrbitKey  # noqa: E402

KEYS = Q1481 / "n53_d14_projected_keys.bin"
BASE_RECEIPT = Q1481 / "n53_d14_base.json"
POINTS = HERE / "n53_window_points.bin"
RECEIPT = HERE / "n53_window_points_receipt.json"
WIDTH = 7


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_keys() -> list[int]:
    packed = KEYS.read_bytes()
    keys = [int.from_bytes(packed[i:i + WIDTH], "little")
            for i in range(0, len(packed), WIDTH)]
    assert len(packed) == WIDTH * len(keys)
    assert keys == sorted(set(keys))
    return keys


def build() -> dict:
    assert not POINTS.exists() and not RECEIPT.exists(), "refuse overwrite"
    base = json.loads(BASE_RECEIPT.read_text())
    assert base["proposal_id"] == "Q1481"
    assert base["curve_id"] == "EC1N53Ckb1hf77aab617904"
    assert base["nominal_window_dimension_d"] == 14
    assert base["enumerated_set_sha256"] == sha(KEYS)
    keys = read_keys()
    assert len(keys) == base["signed_frobenius_columns_K"] == 4060
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    subgroup_order = json.loads((Q1481 / "protocol.json").read_text())[
        "instances"]["53"]["subgroup_order"]
    started = time.perf_counter()
    points = []
    for key in keys:
        x = onb_x_from_cycle_mask(key, onb, orbit)
        point = curve.pointFromX(x)
        assert point is not None
        assert curve.mul(point, subgroup_order) is None
        for shift in range(53):
            image = curve.frob(point, shift)
            points.extend((image, curve.neg(image)))
    assert len(points) == base["actual_usable_points_B_before_folding"] == (
        430360)
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
    result = {
        "kind": "q1488_complete_n53_window_base_point_materialization",
        "proposal_id": "Q1488", "candidate_id": None,
        "isogeny": "none", "curve_id": base["curve_id"],
        "nominal_window_dimension_d": 14,
        "factor_base_actual_B": len(points),
        "folded_columns_K": len(keys),
        "factor_base_enumerated_set_sha256": sha(KEYS),
        "q1481_base_receipt_sha256": sha(BASE_RECEIPT),
        "point_encoding": (
            "sorted affine x,y normal-basis coordinate masks; "
            "each mask 7-byte little-endian"),
        "point_bytes": POINTS.stat().st_size,
        "point_file_sha256": sha(POINTS),
        "source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
        "construction_wall_seconds_exploratory": time.perf_counter() -
            started,
        "peak_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "target_independent": True,
    }
    RECEIPT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def read_points() -> list[tuple[int, int]]:
    receipt = json.loads(RECEIPT.read_text())
    assert receipt["proposal_id"] == "Q1488"
    assert sha(POINTS) == receipt["point_file_sha256"]
    data = POINTS.read_bytes()
    assert len(data) == 2 * WIDTH * receipt["factor_base_actual_B"]
    encoded = [(int.from_bytes(data[i:i + WIDTH], "little"),
                int.from_bytes(data[i + WIDTH:i + 2 * WIDTH], "little"))
               for i in range(0, len(data), 2 * WIDTH)]
    assert encoded == sorted(set(encoded))
    onb = field.Onb(53)
    return [(onb.fromCoords(x), onb.fromCoords(y)) for x, y in encoded]


def check() -> None:
    receipt = json.loads(RECEIPT.read_text())
    assert receipt["source_sha256"] == sha(Path(__file__))
    assert receipt["runtime_info_sha256"] == sha(
        HERE / "sage_runtime_info.json")
    assert receipt["q1481_base_receipt_sha256"] == sha(BASE_RECEIPT)
    assert receipt["factor_base_enumerated_set_sha256"] == sha(KEYS)
    assert len(read_points()) == receipt["factor_base_actual_B"] == 430360
    print("Q1488 N53 complete window base: PASS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check()
    else:
        print(json.dumps(build(), sort_keys=True))
