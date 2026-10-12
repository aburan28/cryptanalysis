#!/usr/bin/env python3
"""Replay the full Q1325 point-key set and both known subset bases."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import sys
from pathlib import Path

from q1325_inputs import read_inputs
from run_probe import HERE, ROOT, curves, field, sha

PAIR = ROOT / "experiments/koblitz-pair-claw-20260929"
sys.path.insert(0, str(PAIR))
from orbit_key import OrbitKey  # noqa: E402


def replay():
    base_path, base, key_path, keys, _, _ = read_inputs()
    runtime_path = HERE / "q1325_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    fb = base["factor_base"]
    assert base["field"]["n"] == 83 and base["isogeny"] == "none"
    assert fb["normal_basis_weight_bound"] == 5
    assert fb["raw_x_frobenius_orbits"] == 373101
    assert fb["signed_frobenius_columns"] == len(keys)
    assert fb["actual_usable_points_B_before_folding"] == 166 * len(keys)
    assert fb["identity_projection_orbits"] == 0
    assert fb["duplicate_projection_orbits"] == 0
    assert sum(row["rational_x_orbits"] for row in base[
        "weight_strata"]) == len(keys)
    key_set = set(keys)
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    r = base["curve"]["subgroup_order"]
    assert base["curve"]["order"] == 4 * r
    for index, key in enumerate(keys):
        point = orbit.point_from_key(key)
        assert point is not None and curve.onCurve(point)
        assert orbit.canonical(point)[0] == key
        if index % 2900 == 0:
            assert curve.mul(point, r) is None
    q1041_path = PAIR / "runs/n83_weight5_orbit_base.json"
    q1041 = json.loads(q1041_path.read_text())
    q1041_key_path = PAIR / q1041["factor_base"]["orbit_key_file"]
    q1041_data = q1041_key_path.read_bytes()
    q1041_keys = set(int.from_bytes(q1041_data[i:i + 21], "little")
                     for i in range(0, len(q1041_data), 21))
    assert len(q1041_keys) == 24097 and q1041_keys <= key_set
    w4_path = HERE / "bases/n83_weight4_orbits.json.gz"
    with gzip.open(w4_path, "rt") as stream:
        w4 = json.load(stream)
    w4_fb = w4["factor_base"]
    packed_x = base64.b64decode(w4_fb["packed_canonical_x_keys_base64"])
    assert hashlib.sha256(packed_x).hexdigest() == w4_fb[
        "enumerated_set_sha256"]
    w4_x = [int.from_bytes(packed_x[i:i + 11], "little")
            for i in range(0, len(packed_x), 11)]
    assert len(w4_x) == w4_fb["signed_frobenius_columns"] == 11651
    w4_point_keys = set()
    for x in w4_x:
        point = curve.pointFromX(onb.fromCoords(x))
        assert point is not None and curve.mul(point, r) is None
        w4_point_keys.add(orbit.canonical(point)[0])
    assert len(w4_point_keys) == 11651 and w4_point_keys <= key_set
    return {
        "kind": "q1325_independent_full_point_key_replay",
        "proposal_id": "Q1325", "candidate_id": None,
        "curve_id": base["curve"]["curve_id"], "isogeny": "none",
        "status": "PASS",
        "actual_usable_points_B_before_folding": fb[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": len(keys),
        "point_keys_replayed_on_curve_and_canonical": len(keys),
        "sampled_subgroup_order_checks": len(range(0, len(keys), 2900)),
        "q1041_subset_columns_verified": len(q1041_keys),
        "q1302_weight4_subset_columns_verified": len(w4_point_keys),
        "factor_base_enumerated_set_sha256": fb["enumerated_set_sha256"],
        "base_receipt_sha256": sha(base_path),
        "point_key_file_sha256": sha(key_path),
        "q1041_receipt_sha256": sha(q1041_path),
        "q1041_point_key_file_sha256": sha(q1041_key_path),
        "q1302_weight4_archive_sha256": sha(w4_path),
        "runtime_info_sha256": sha(runtime_path),
        "field_source_sha256": sha(Path(field.__file__)),
        "curve_source_sha256": sha(Path(curves.__file__)),
        "orbit_source_sha256": sha(PAIR / "orbit_key.py"),
        "source_sha256": sha(Path(__file__)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    out = HERE / "runs/n83_q1325_full_base_replay.json"
    report = replay()
    content = json.dumps(report, indent=2) + "\n"
    if args.check:
        assert out.read_text() == content
    else:
        assert not out.exists()
        out.write_text(content)
    print(json.dumps({"status": report["status"],
                      "B": report["actual_usable_points_B_before_folding"],
                      "K": report["signed_frobenius_columns"]}))


if __name__ == "__main__":
    main()
