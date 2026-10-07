#!/usr/bin/env python3
"""Independently replay a local N83 shifted witness with integer-field arithmetic."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time


HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "shifted_sat_protocol.json"
OLD_PUBLIC = HERE.parent / "hamming-ic-e2e-20260929/runs/n83_w34_sat_fixture_v1/public_input.json"
sys.path.insert(0, str(HERE.parent / "pdp-scaling"))
from gf2n import Curve, GF2n, INF, Point  # noqa: E402

R = 2417851639230796216685689


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def times(curve: Curve, count: int, point: Point) -> Point:
    result = INF
    while count:
        if count & 1:
            result = curve.add(result, point)
        point = curve.add(point, point)
        count >>= 1
    return result


def main(label: str, folder: Path) -> None:
    folder = folder.resolve()
    output = folder / "independent_replay.json"
    if output.exists():
        raise FileExistsError("replay output is immutable")
    started = time.perf_counter_ns()
    protocol = json.loads(PROTOCOL.read_text())
    old = json.loads(OLD_PUBLIC.read_text())
    public_path, private_path = folder / "public_input.json", folder / "private_fixture.json"
    public, private = json.loads(public_path.read_text()), json.loads(private_path.read_text())
    assert public["label"] == private["label"] == label
    assert public["curve_id"] == private["curve_id"] == protocol["curve_id"]
    assert private["public_input_sha256"] == sha(public_path)
    assert public["private_witness_commitment_sha256"] == \
        hashlib.sha256(canonical(private["witness"])).hexdigest()
    assert public["ordinary"] == old["ordinary"]
    assert sha(OLD_PUBLIC) == protocol["public_ordinary_input_sha256"]
    geometry_path = HERE / "runs" / f"{label}_v1" / "geometry.json"
    geometry = json.loads(geometry_path.read_text())
    assert public["geometry_sha256"] == sha(geometry_path)
    assert public["geometry_sha256"] == next(
        item["geometry_sha256"] for item in protocol["geometry"]
        if item["label"] == label)
    raw_reps = gzip.decompress((geometry_path.parent / "representatives.json.gz").read_bytes())
    assert hashlib.sha256(raw_reps).hexdigest() == geometry["representatives_sha256"]
    reps = {tuple(row) for row in json.loads(raw_reps)["representatives"]}

    field = GF2n(83, (1 << 83) | (1 << 7) | (1 << 4) | (1 << 2) | 1)
    curve = Curve(field, 1)
    conjugates = [int(value) for value in old["normal_conjugates_polynomial_bits_decimal"]]
    assert len(conjugates) == 83
    assert all(field.sqr(conjugates[i]) == conjugates[(i + 1) % 83]
               for i in range(83))

    def orbit_key(point: Point) -> tuple[int, int]:
        x, y = point.x, point.y
        values = []
        for _ in range(83):
            values.extend(((x, y), (x, x ^ y)))
            x, y = field.sqr(x), field.sqr(y)
        return min(values)

    def s3(a: int, b: int, c: int) -> int:
        e2 = field.mul(a, b) ^ field.mul(a, c) ^ field.mul(b, c)
        return field.sqr(e2) ^ field.mul(field.mul(a, b), c) ^ 1

    selected = private["witness"]["selected"]
    assert len(selected) == geometry["arity"]
    prefix = INF
    prior_x = None
    used_orbits = set()
    for index, row in enumerate(selected):
        assert row["slot"] == index
        mask = int(row["mask_decimal"])
        assert 1 <= mask < (1 << geometry["dimension"])
        slot = geometry["slot_normal_basis_indices"][index]
        x = 0
        for local_bit in range(geometry["dimension"]):
            if mask & (1 << local_bit):
                x ^= conjugates[slot[local_bit]]
        point = Point(int(row["raw_point"][0]), int(row["raw_point"][1]))
        projected = Point(int(row["projected_point"][0]),
                          int(row["projected_point"][1]))
        assert x == point.x and curve.on_curve(point)
        assert times(curve, 4, point) == projected != INF
        assert times(curve, R, projected) == INF
        key = orbit_key(projected)
        assert key in reps and key not in used_orbits
        assert [str(key[0]), str(key[1])] == row["orbit_representative"]
        used_orbits.add(key)
        prefix = curve.add(prefix, point)
        assert prefix != INF
        if prior_x is not None:
            assert s3(prior_x, point.x, prefix.x) == 0
        prior_x = prefix.x
    raw_sum = prefix
    q = times(curve, 4, raw_sum)
    assert q != INF and times(curve, R, q) == INF
    assert [str(raw_sum.x), str(raw_sum.y)] == private["witness"]["raw_sum"]
    assert [str(q.x), str(q.y)] == private["witness"]["target_Q"]
    assert [str(q.x), str(q.y)] == public["planted"]["target_Q"]
    fiber = [Point(int(row["x"]), int(row["y"]))
             for row in public["planted"]["raw_target_fiber"]]
    assert len(set(fiber)) == 4 and raw_sum in fiber
    assert all(curve.on_curve(point) and times(curve, 4, point) == q
               for point in fiber)
    receipt = {
        "schema_version": 1, "kind": "n83_shifted_sat_independent_integer_replay",
        "status": "PASS", "label": label, "candidate_id": None,
        "curve_id": protocol["curve_id"], "factor_count": len(selected),
        "all_factor_masks_in_exact_slots": True,
        "all_projected_factors_in_measured_base_orbits": True,
        "all_prefixes_nonidentity": True,
        "all_s3_links_zero": True,
        "all_four_raw_fibers_project_to_target": True,
        "target_subgroup_check": True,
        "public_input_sha256": sha(public_path),
        "private_fixture_sha256_local_only": sha(private_path),
        "geometry_sha256": sha(geometry_path),
        "source_sha256": sha(Path(__file__)),
        "gf2n_source_sha256": sha(HERE.parent / "pdp-scaling/gf2n.py"),
        "wall_ms_exploratory": (time.perf_counter_ns() - started) / 1e6,
        "claim_boundary": "Planted correctness control only; no unpinned solver or ordinary yield.",
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"label": label, "status": "PASS",
                      "factor_count": len(selected)}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    main(args.label, args.folder)
