#!/usr/bin/env python3
"""Rebuild and verify the exact n=83 known-log signed-Frobenius base."""

import hashlib
import json
import random
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
    receipt = json.loads((HERE / "runs" / "n83_knownlog_orbit_base.json").read_text())
    assert receipt["source_sha256"] == sha(HERE / "build_n83_knownlog_base.py")
    assert receipt["orbit_key_sha256"] == sha(HERE / "orbit_key.py")
    for name, digest in receipt["dependency_sha256"].items():
        assert digest == sha(CODEGEN / name)
    reference_path = (HERE.parent / "ecc2k130-quotient-pair-probe-20260926" /
                      "runs" / "n83_perf_prefix.json")
    assert receipt["reference_sha256"] == sha(reference_path)
    identity = receipt["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert receipt["curve_id"] == curve_id == "EC1N83Ckb1h876c2921cb64"
    assert receipt["isogeny"] == "none" and receipt["candidate_id"] is None
    order = identity["curve"]["subgroup_order"]
    assert curves.isPrimeBig(order)
    assert identity["curve"]["order"] == 4 * order
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    generator = tuple(identity["curve"]["generator"])
    assert curve.mul(generator, order) is None
    base_record = receipt["factor_base"]
    eigen = base_record["frobenius_eigenvalue_mod_r"]
    assert curve.mul(generator, eigen) == curve.frob(generator)
    assert eigen != 1 and pow(eigen, 83, order) == 1
    file_path = HERE / base_record["key_and_log_file"]
    data = file_path.read_bytes()
    assert sha(file_path) == base_record["key_and_log_file_sha256"]
    assert len(data) == base_record["key_and_log_file_bytes"] == 24097 * 32
    keys = []
    logs = []
    for offset in range(0, len(data), 32):
        keys.append(int.from_bytes(data[offset:offset + 21], "little"))
        logs.append(int.from_bytes(data[offset + 21:offset + 32], "little"))
    assert keys == sorted(set(keys))
    assert all(0 <= log < order for log in logs)
    assert hashlib.sha256(b"".join(key.to_bytes(21, "little")
                                for key in keys)).hexdigest() == base_record[
                                    "enumerated_set_sha256"]
    assert hashlib.sha256(b"".join(log.to_bytes(11, "little")
                                for log in logs)).hexdigest() == base_record[
                                    "canonical_log_sha256"]

    # Replay the independent scalar stream and compare every canonical
    # representative and known log, not merely a random sample.
    rng = random.Random(base_record["seed"])
    entries = {}
    draws = 0
    while len(entries) < base_record["selected_point_orbits"]:
        alpha = rng.randrange(1, order)
        draws += 1
        point = curve.mul(generator, alpha)
        key, exponent, sign = orbit.canonical(point)
        entries.setdefault(key, sign * pow(eigen, exponent, order) * alpha % order)
    assert draws == base_record["drawn_scalars"]
    assert keys == sorted(entries)
    assert logs == [entries[key] for key in keys]
    for index in (0, 1, 42, 1024, 12048, 24096):
        point = orbit.point_from_key(keys[index])
        assert point is not None and curve.onCurve(point)
        assert curve.mul(generator, logs[index]) == point
    assert base_record["signed_frobenius_orbit_size"] == 166
    assert base_record["actual_usable_points_B_before_folding"] == 166 * len(keys) == 4000102
    assert base_record["signed_frobenius_columns"] == len(keys) == 24097
    assert base_record["initially_known_log_columns"] == len(keys)
    assert base_record["unknown_log_columns"] == 0
    assert receipt["verified_relation_count"] == 0
    assert receipt["verified_single_target_dlp"] is False
    return {"curve_id": curve_id, "actual_B": 166 * len(keys),
            "folded_columns": len(keys),
            "known_logs": len(logs), "drawn_scalars": draws}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
