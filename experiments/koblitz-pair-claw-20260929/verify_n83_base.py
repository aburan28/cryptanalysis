#!/usr/bin/env python3
"""Independently verify the compressed four-million-point n=83 base."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
sys.path.insert(0, str(CODEGEN))

import curves
import field
from orbit_key import OrbitKey
from run_n23 import frozen, sha


def verify():
    receipt = json.loads((HERE / "runs" / "n83_weight5_orbit_base.json").read_text())
    assert receipt["source_sha256"] == sha(HERE / "build_n83_orbit_base.py")
    assert receipt["orbit_key_sha256"] == sha(HERE / "orbit_key.py")
    for name, digest in receipt["dependency_sha256"].items():
        assert digest == sha(CODEGEN / name)
    reference_path = (HERE.parent / "ecc2k130-quotient-pair-probe-20260926" /
                      "runs" / "n83_perf_prefix.json")
    assert receipt["reference_sha256"] == sha(reference_path)
    identity = receipt["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert receipt["curve_id"] == curve_id == "EC1N83Ckb1h876c2921cb64"
    assert receipt["isogeny"] == "none"
    assert receipt["candidate_id"] is None
    order = identity["curve"]["subgroup_order"]
    assert curves.isPrimeBig(order)
    assert identity["curve"]["order"] == 4 * order
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    generator = tuple(identity["curve"]["generator"])
    eigenvalue = receipt["factor_base"]["frobenius_eigenvalue_mod_r"]
    assert curve.mul(generator, eigenvalue) == curve.frob(generator)
    assert pow(eigenvalue, 83, order) == 1
    assert all(pow(eigenvalue, j, order) not in (1, order - 1)
               for j in range(1, 83))
    key_file = HERE / receipt["factor_base"]["orbit_key_file"]
    data = key_file.read_bytes()
    assert sha(key_file) == receipt["factor_base"]["enumerated_set_sha256"]
    assert len(data) == receipt["factor_base"]["orbit_key_file_bytes"]
    assert len(data) % 21 == 0
    keys = [int.from_bytes(data[index:index + 21], "little")
            for index in range(0, len(data), 21)]
    assert len(keys) == 24097
    assert all(0 <= key < (1 << 166) for key in keys)
    assert keys == sorted(set(keys))
    for key in keys:
        point = orbit.point_from_key(key)
        assert point is not None and curve.onCurve(point)
        assert orbit.canonical(point)[0] == key
        assert curve.mul(point, order) is None
    base = receipt["factor_base"]
    assert base["selected_point_orbits"] == len(keys)
    assert base["signed_frobenius_orbit_size"] == 166
    assert base["actual_usable_points_B_before_folding"] == 166 * len(keys) == 4000102
    assert base["signed_frobenius_columns"] == len(keys)
    assert receipt["verified_relation_count"] == 0
    assert receipt["verified_single_target_dlp"] is False
    return {"curve_id": curve_id, "actual_B": 166 * len(keys),
            "folded_columns": len(keys),
            "verified_projected_representatives": len(keys)}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
