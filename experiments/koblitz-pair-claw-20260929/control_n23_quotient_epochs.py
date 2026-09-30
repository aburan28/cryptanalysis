#!/usr/bin/env python3
"""Small exact control for the salted signed-Frobenius pair-claw walk."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "ecc2k130" / "runner" / "codegen"))

import curves
import field
from orbit_key import OrbitKey
from quotient_epoch_walk import walk_epochs
from run_n23 import build_base, frozen, point_digest, sha


def main():
    reference_path = HERE / "runs" / "n23_one_target.json"
    runtime_path = HERE / "runs" / "n53_quotient_epoch_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    reference = json.loads(reference_path.read_text())
    identity = reference["curve_identity_record"]
    curve_id = "EC1N23Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert curve_id == reference["curve_id"]
    onb = field.Onb(23)
    curve = curves.Curve(onb)
    order = identity["curve"]["subgroup_order"]
    generator = tuple(identity["curve"]["generator"])
    target = tuple(reference["workload"]["target"])
    assert curve.mul(generator, order) is None
    assert curve.mul(target, order) is None
    base, _ = build_base(curve, onb, order)
    assert len(base) == reference["factor_base"]["actual_usable_points_B_before_folding"]
    assert point_digest(base) == reference["factor_base"]["enumerated_set_sha256"]
    workload = {"curve_id": curve_id, "target": list(target),
                "target_count": 1,
                "target_input_law": "fixed public subgroup point",
                "factor_base_enumerated_set_sha256": point_digest(base)}
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    rows = []
    for epochs in (1, 4):
        result = walk_epochs(curve, base, generator, order, target,
                             OrbitKey(onb), 999999, 3, 512, 50000, epochs)
        relation = result["relation"]
        assert relation is not None
        points = [tuple(point) for point in relation["points"]]
        assert len(points) == 4 and all(point in base for point in points)
        total = None
        for point in points:
            total = curve.add(total, point)
        assert total == target
        rows.append({"epochs": epochs,
                     "main_step_evaluations_excluding_replay":
                     result["main_step_evaluations_excluding_replay"],
                     "replay_step_evaluations":
                     result["replay_step_evaluations"],
                     "relation": relation})
    print(json.dumps({
        "kind": "n23_salted_quotient_claw_correctness_control",
        "proposal_id": "Q1067", "candidate_id": None, "run_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "workload_id": workload_id, "workload": workload,
        "isogeny": "none", "factor_base_B": len(base),
        "factor_base_enumerated_set_sha256": point_digest(base),
        "signed_frobenius_columns": reference["factor_base"]["signed_frobenius_columns"],
        "controls": rows, "reference_sha256": sha(reference_path),
        "sage_runtime_info_sha256": sha(runtime_path),
        "source_sha256": sha(Path(__file__)),
        "epoch_walk_source_sha256": sha(HERE / "quotient_epoch_walk.py"),
        "complete_work_log2": None,
    }, indent=2))


if __name__ == "__main__":
    main()
