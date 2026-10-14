#!/usr/bin/env python3
"""Paired n=53 screen of one versus four salted quotient-claw epochs."""

import argparse
import hashlib
import json
import platform
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
REFERENCE = (HERE.parent / "ecc2k130-quotient-pair-probe-20260926" /
             "runs" / "n53_perf_prefix.json")
PLAN = HERE / "n53_quotient_epoch_plan.json"
BASELINE = HERE / "runs" / "n53_weight3_quotient_relation_probe.json"
sys.path.insert(0, str(CODEGEN))

import curves
import field
from orbit_key import OrbitKey
from probe_n53_relation import base_and_columns
from quotient_epoch_walk import walk_epochs
from run_n23 import frozen, point_digest, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=("single", "four"), required=True)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), "refusing to overwrite a measured receipt"
    runtime = json.loads(args.runtime_info.read_text())
    assert runtime["status"] == "verified"
    plan = json.loads(PLAN.read_text())
    assert plan["status"] == "frozen_bounded_screen"
    assert plan["proposal_id"] == "Q1067"
    assert plan["candidate_id"] is None and plan["run_id"] is None
    assert plan["isogeny"] == "none"
    assert plan["reference_sha256"] == sha(REFERENCE)
    assert plan["baseline_sha256"] == sha(BASELINE)
    reference = json.loads(REFERENCE.read_text())
    identity = reference["curve_identity_record"]
    curve_id = "EC1N53Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert reference["curve_id"] == plan["curve_id"] == curve_id
    assert reference["workload"]["target"] == plan["public_target"]
    order = identity["curve"]["subgroup_order"]
    cofactor = identity["curve"]["cofactor"]
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    generator = tuple(identity["curve"]["generator"])
    target = tuple(plan["public_target"])
    assert curve.mul(generator, order) is None
    assert curve.mul(target, order) is None
    setup_started = time.perf_counter_ns()
    base, representatives, rational_x = base_and_columns(
        curve, onb, order, cofactor)
    setup_ns = time.perf_counter_ns() - setup_started
    factor_base = plan["factor_base"]
    assert len(base) == factor_base["actual_usable_points_B_before_folding"]
    assert len(representatives) == factor_base["signed_frobenius_columns"]
    assert point_digest(base) == factor_base["enumerated_set_sha256"]
    orbit = OrbitKey(onb)
    epochs = plan["variants"][args.variant]["epochs"]
    outcome = walk_epochs(
        curve, base, generator, order, target, orbit, plan["walk_seed"],
        plan["distinguished_bits"], plan["max_trail"],
        plan["max_main_step_evaluations"], epochs)
    relation = outcome["relation"]
    if relation is not None:
        points = [tuple(point) for point in relation["points"]]
        assert len(points) == 4 and all(point in set(base) for point in points)
        total = None
        for point in points:
            total = curve.add(total, point)
        assert total == target
    workload = {
        "curve_id": curve_id, "target": list(target), "target_count": 1,
        "target_input_law": "fixed public subgroup point",
        "factor_base_enumerated_set_sha256": factor_base["enumerated_set_sha256"],
    }
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    report = {
        "kind": "n53_full_weight3_base_salted_quotient_claw_epoch_screen",
        "scope": "one ordinary public target; relation stage only; no factor-base log recovery or DLP",
        "proposal_id": "Q1067", "candidate_id": None, "run_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "workload_id": workload_id, "workload": workload,
        "isogeny": "none", "variant": args.variant,
        "variant_config": {
            "walk_seed": plan["walk_seed"],
            "distinguished_bits": plan["distinguished_bits"],
            "max_trail": plan["max_trail"],
            "max_main_step_evaluations": plan["max_main_step_evaluations"],
            "epochs": epochs,
            "salt_rule": plan["salt_rule"],
        },
        "factor_base": dict(factor_base,
                            rational_x_coordinates=rational_x),
        "target_independent_base_setup_ns": setup_ns,
        "ordinary_query": outcome,
        "same_implementation_relation_check_passed": relation is not None,
        "independent_relation_verified": False,
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "work_boundary": (
            "Main and replay step evaluations count calls to the salted "
            "pair-map step; seed scalar multiplications, base setup, "
            "hashing, canonicalization, memory, and any independent "
            "replay are outside that operation count."),
        "peak_parent_rss_bytes": (
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if platform.system() == "Darwin" else
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
        "runtime": {"python": sys.version, "platform": platform.platform()},
        "plan_sha256": sha(PLAN),
        "sage_runtime_info_sha256": sha(args.runtime_info),
        "source_sha256": sha(Path(__file__)),
        "epoch_walk_source_sha256": sha(HERE / "quotient_epoch_walk.py"),
        "base_source_sha256": sha(HERE / "probe_n53_relation.py"),
        "orbit_key_source_sha256": sha(HERE / "orbit_key.py"),
        "reference_sha256": sha(REFERENCE),
        "baseline_sha256": sha(BASELINE),
        "dependency_sha256": {name: sha(CODEGEN / name)
                              for name in ("curves.py", "field.py", "indexcalc.py")},
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "variant": args.variant, "epochs_completed": outcome["epochs_completed"],
        "status": outcome["status"],
        "main_evaluations": outcome["main_step_evaluations_excluding_replay"],
        "replay_evaluations": outcome["replay_step_evaluations"],
        "wall_seconds": outcome["wall_ns"] / 1e9,
        "out": str(args.out),
    }), flush=True)


if __name__ == "__main__":
    main()
