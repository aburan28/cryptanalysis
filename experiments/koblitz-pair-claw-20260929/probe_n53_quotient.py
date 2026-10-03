#!/usr/bin/env python3
"""Bounded n=53 ordinary-target search with signed-Frobenius quotient claw."""

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
sys.path.insert(0, str(CODEGEN))

import curves
import field
from orbit_key import OrbitKey
from probe_n53_relation import base_and_columns
from quotient_walk import walk
from run_n23 import frozen, point_digest, sha

DP_BITS = 7
MAX_TRAIL = 4096
MAX_EVALS = 2000000
WALK_SEED = 530929


def main():
    reference = json.loads(REFERENCE.read_text())
    identity = reference["curve_identity_record"]
    curve_id = "EC1N53Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert reference["curve_id"] == curve_id
    order = identity["curve"]["subgroup_order"]
    cofactor = identity["curve"]["cofactor"]
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    generator = tuple(identity["curve"]["generator"])
    target = tuple(reference["workload"]["target"])
    assert curve.mul(generator, order) is None
    assert curve.mul(target, order) is None
    setup_started = time.perf_counter_ns()
    base, representatives, rational_x = base_and_columns(curve, onb,
                                                           order, cofactor)
    setup_ns = time.perf_counter_ns() - setup_started
    assert len(base) == 24062 and len(representatives) == 227
    orbit = OrbitKey(onb)
    outcome = walk(curve, base, generator, order, target, orbit, WALK_SEED,
                   DP_BITS, MAX_TRAIL, MAX_EVALS)
    if outcome["relation"] is not None:
        points = [tuple(point) for point in outcome["relation"]["points"]]
        assert len(points) == 4 and all(point in set(base) for point in points)
        total = None
        for point in points:
            total = curve.add(total, point)
        assert total == target
    workload = {"curve_id": curve_id, "target": list(target),
                "target_count": 1, "target_input_law": "fixed public subgroup point",
                "normal_x_weight_bound": 3, "walk_seed": WALK_SEED,
                "distinguished_bits": DP_BITS, "max_trail": MAX_TRAIL,
                "max_walk_evaluations": MAX_EVALS,
                "quotient_rule": "signed Frobenius"}
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    report = {
        "kind": "n53_full_weight3_base_bounded_signed_frobenius_quotient_claw_probe",
        "scope": "one ordinary public target; quotient relation stage only, no base logs or DLP",
        "proposal_id": "Q1039", "candidate_id": None, "run_id": None,
        "curve_id": curve_id, "curve_identity_record": identity,
        "workload_id": workload_id, "workload": workload,
        "isogeny": "none",
        "factor_base": {
            "construction": "all nonzero type-II ONB x supports of weight at most three; rational lift; cofactor projection; both signs; full Frobenius closure",
            "cofactor_projection": cofactor,
            "rational_x_coordinates": rational_x,
            "actual_usable_points_B_before_folding": len(base),
            "signed_frobenius_columns": len(representatives),
            "enumerated_set_sha256": point_digest(base)},
        "target_independent_base_and_column_setup_ns": setup_ns,
        "ordinary_query": outcome,
        "verified_relation_count": int(outcome["relation"] is not None),
        "verified_single_target_dlp": False,
        "complete_work_log2": None,
        "peak_parent_rss_bytes": (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                                  if platform.system() == "Darwin" else
                                  resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
        "runtime": {"python": sys.version, "platform": platform.platform()},
        "source_sha256": sha(Path(__file__)),
        "base_source_sha256": sha(HERE / "probe_n53_relation.py"),
        "quotient_walk_sha256": sha(HERE / "quotient_walk.py"),
        "orbit_key_sha256": sha(HERE / "orbit_key.py"),
        "reference_sha256": sha(REFERENCE),
        "dependency_sha256": {name: sha(CODEGEN / name)
                              for name in ("curves.py", "field.py", "indexcalc.py")},
    }
    path = HERE / "runs" / "n53_weight3_quotient_relation_probe.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"curve_id": curve_id, "B": len(base),
                      "columns": len(representatives),
                      "status": outcome["status"],
                      "main_evaluations": outcome[
                          "main_step_evaluations_excluding_replay"],
                      "wall_s": outcome["wall_ns"] / 1e9,
                      "receipt": str(path)}))


if __name__ == "__main__":
    main()
