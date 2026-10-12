#!/usr/bin/env python3
"""Exact full-base second-pair lookup on the frozen positive N53 complement."""
import hashlib
import json
import sys
import time
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
sys.path.insert(0, str(ROOT / "experiments/compact-s3-m4-20261003/q20261011_operation_account"))
import curves
from counted_onb import CountedOnb

REFERENCE = ROOT / "experiments/koblitz-pair-claw-20260929/runs/n53_weight3_relation_probe.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def exact_base(curve, onb, order, cofactor):
    points = set()
    rational_x = 0
    for weight in (1, 2, 3):
        for support in combinations(range(53), weight):
            x = onb.fromCoords(sum(1 << bit for bit in support))
            point = curve.pointFromX(x)
            if point is None:
                continue
            rational_x += 1
            projected = curve.mul(point, cofactor)
            if projected is not None:
                assert curve.mul(projected, order) is None
                points.add(projected)
                points.add(curve.neg(projected))
    return sorted(points), rational_x


def main():
    protocol = json.loads((HERE / "direct_protocol.json").read_text())
    assert not (HERE / "direct_result.json").exists()
    for relative, digest in protocol["sources_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    ref = json.loads(REFERENCE.read_text())
    assert sha(REFERENCE) == protocol["reference_sha256"]
    identity = ref["curve_identity_record"]
    assert ref["curve_id"] == protocol["curve_id"]
    assert identity["curve"]["cofactor"] == protocol["cofactor"]
    order = int(identity["curve"]["subgroup_order"])
    onb = CountedOnb(53)
    curve = curves.Curve(onb)
    t0 = time.perf_counter_ns()
    base, rational_x = exact_base(curve, onb, order, protocol["cofactor"])
    setup_ns = time.perf_counter_ns() - t0
    assert len(base) == protocol["factor_base_actual_B"]
    digest = hashlib.sha256()
    for x, y in base:
        digest.update(f"{x},{y}\n".encode())
    assert digest.hexdigest() == ref["factor_base"]["enumerated_set_sha256"]
    base_set = set(base)
    target = curve.pointFromX(onb.fromCoords(protocol["complement_x_onb_coords"]))
    assert target is not None
    onb.reset_counts()
    t0 = time.perf_counter_ns()
    found = None
    attempts = 0
    for p in base:
        attempts += 1
        q = curve.add(target, curve.neg(p))
        if q in base_set:
            found = (p, q)
            break
    query_ns = time.perf_counter_ns() - t0
    counts = onb.snapshot_counts()
    assert found is not None
    assert curve.add(*found) == target
    assert all(point in base_set for point in found)
    assert all(curve.mul(point, order) is None for point in found)
    save(HERE / "direct_result.json", {
        "proposal_id": "Q1519", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "isogeny": "none",
        "point_decomposition_stage_code": "PDP4mitm",
        "protocol_sha256": sha(HERE / "direct_protocol.json"),
        "source_sha256": sha(Path(__file__)),
        "status": "EXACT_BASE_PAIR_VERIFIED",
        "factor_base_actual_B": len(base),
        "factor_base_enumerated_set_sha256": digest.hexdigest(),
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "rational_raw_x_count": rational_x,
        "complement_x_onb_coords": protocol["complement_x_onb_coords"],
        "query_attempts_including_failures": attempts,
        "query_field_api_calls_excluding_verification": counts,
        "query_wall_ns_exploratory": query_ns,
        "base_setup_wall_ns_exploratory": setup_ns,
        "witness_x_onb_coords": [onb.toCoords(point[0]) for point in found],
        "witness_points": [list(point) for point in found],
        "complete_n53_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
    })


if __name__ == "__main__":
    main()
