#!/usr/bin/env python3
"""Independent witness, orbit archive, and field-call-boundary replay."""
import base64
import gzip
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
import curves
import field


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = json.loads((HERE / "direct_protocol.json").read_text())
    r = json.loads((HERE / "direct_result.json").read_text())
    assert r["protocol_sha256"] == sha(HERE / "direct_protocol.json")
    assert r["source_sha256"] == sha(HERE / "direct_run.py")
    assert r["curve_id"] == p["curve_id"]
    for relative, digest in p["sources_sha256"].items():
        assert sha(ROOT / relative) == digest
    ref_path = ROOT / "experiments/koblitz-pair-claw-20260929/runs/n53_weight3_relation_probe.json"
    assert sha(ref_path) == p["reference_sha256"]
    ref = json.loads(ref_path.read_text())
    assert r["factor_base_enumerated_set_sha256"] == ref["factor_base"]["enumerated_set_sha256"]
    archive_path = ROOT / "experiments/compact-s3-m4-20261003/bases/n53_weight3_orbits.json.gz"
    with gzip.open(archive_path, "rt") as stream:
        archive = json.load(stream)
    fb = archive["factor_base"]
    packed = base64.b64decode(fb["packed_canonical_x_keys_base64"])
    assert hashlib.sha256(packed).hexdigest() == fb["enumerated_set_sha256"]
    keys = {int.from_bytes(packed[i:i+7], "little") for i in range(0, len(packed), 7)}
    assert len(keys) == 227
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    points = [tuple(point) for point in r["witness_points"]]
    target = curve.pointFromX(onb.fromCoords(p["complement_x_onb_coords"]))
    order = int(ref["curve_identity_record"]["curve"]["subgroup_order"])
    assert target is not None
    assert len(points) == 2
    for point, x in zip(points, r["witness_x_onb_coords"]):
        assert curve.onCurve(point)
        assert curve.mul(point, order) is None
        assert onb.toCoords(point[0]) == x
        assert any(onb.toCoords(onb.frob(point[0], shift)) in keys
                   for shift in range(53))
    assert curve.add(*points) == target
    assert r["query_attempts_including_failures"] <= p["factor_base_actual_B"]
    calls = r["query_field_api_calls_excluding_verification"]
    assert calls["inv"] == r["query_attempts_including_failures"]
    assert calls["mul"] == 2 * r["query_attempts_including_failures"]
    assert r["complete_n131_solve_work_log2"] is None
    print("PASS Q1519 independent N53 pair and archive orbit replay")


if __name__ == "__main__":
    main()
