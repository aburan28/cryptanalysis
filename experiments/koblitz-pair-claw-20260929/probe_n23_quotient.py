#!/usr/bin/env python3
"""Frozen n=23 quotient-claw witness and imported-log scalar replay control."""

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
sys.path.insert(0, str(CODEGEN))

import curves
import field
from orbit_key import OrbitKey
from quotient_walk import walk
from run_n23 import build_base, orbit_labels, point_digest, relation_row, sha

DP_BITS = 3
MAX_TRAIL = 512
MAX_EVALS = 50000
WALK_SEED = 999999


def main():
    reference_path = HERE / "runs" / "n23_one_target.json"
    reference = json.loads(reference_path.read_text())
    assert reference["curve_id"] == "EC1N23Ckb1haed91d8afed0"
    identity = reference["curve_identity_record"]
    order = identity["curve"]["subgroup_order"]
    generator = tuple(identity["curve"]["generator"])
    target = tuple(reference["workload"]["target"])
    onb = field.Onb(23)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    base, _ = build_base(curve, onb, order)
    assert len(base) == 322
    assert point_digest(base) == reference["factor_base"]["enumerated_set_sha256"]
    representatives, labels, _ = orbit_labels(curve, generator, order, base)
    assert [list(point) for point in representatives] == reference["representatives"]

    before = time.perf_counter_ns()
    result = walk(curve, base, generator, order, target, orbit, WALK_SEED,
                  DP_BITS, MAX_TRAIL, MAX_EVALS)
    online_ns = time.perf_counter_ns() - before
    assert result["relation"] is not None
    points = [tuple(point) for point in result["relation"]["points"]]
    assert all(point in set(base) for point in points)
    total = None
    for point in points:
        total = curve.add(total, point)
    assert total == target
    row = relation_row(labels, result["relation"]["points"], 7, order)
    scalar = sum(value * log for value, log in zip(
        row, reference["representative_logs"])) % order
    assert curve.mul(generator, scalar) == target
    assert scalar == reference["recovered_scalar"] == 987654

    report = {
        "kind": "n23_signed_frobenius_quotient_claw_target_stage_control",
        "scope": "one ordinary target, imported target-independent base logs from the direct-claw candidate",
        "proposal_id": "Q1038", "candidate_id": None, "run_id": None,
        "curve_id": reference["curve_id"],
        "curve_identity_record": identity, "isogeny": "none",
        "public_target": list(target),
        "factor_base": reference["factor_base"],
        "imported_base_log_candidate_id": reference["candidate_id"],
        "imported_base_log_receipt_sha256": sha(reference_path),
        "quotient_rule": "canonical minimum of both signs and all 23 Frobenius rotations in type-II ONB cycle coordinates",
        "distinguished_bits": DP_BITS, "max_trail": MAX_TRAIL,
        "max_main_evaluations": MAX_EVALS, "walk_seed": WALK_SEED,
        "target_result": result, "target_relation_row": row,
        "verified_target_scalar_from_imported_base_logs": scalar,
        "verified_complete_pipeline": False,
        "complete_work_log2": None,
        "target_stage_plus_replay_wall_ns": online_ns,
        "direct_claw_same_target_main_evaluations": reference[
            "logical_walk_evaluations_online"],
        "source_sha256": sha(Path(__file__)),
        "quotient_walk_sha256": sha(HERE / "quotient_walk.py"),
        "orbit_key_sha256": sha(HERE / "orbit_key.py"),
        "dependency_sha256": {name: sha(CODEGEN / name)
                              for name in ("curves.py", "field.py", "indexcalc.py")},
    }
    path = HERE / "runs" / "n23_quotient_target_control.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"curve_id": report["curve_id"],
                      "main_evaluations": result[
                          "main_step_evaluations_excluding_replay"],
                      "direct_main_evaluations": report[
                          "direct_claw_same_target_main_evaluations"],
                      "wall_ms": online_ns / 1e6,
                      "recovered_scalar": scalar,
                      "receipt": str(path)}))


if __name__ == "__main__":
    main()
