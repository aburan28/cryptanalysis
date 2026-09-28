#!/usr/bin/env python3
"""Enumerate the exact target-seeded n83 base on a frozen public point."""

import hashlib
import json
import math
import resource
import time
from pathlib import Path

import curves
import field
from dyadic_base_geometry import enumerate_points, replay_sample_labels
from perf_probe import sha

HERE = Path(__file__).resolve().parent
WINDOW = 1000
PROPOSAL_ID = "Q1020"


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def main():
    reference_path = HERE / "runs" / "n83_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    order = int(reference["subgroup_order"])
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    target = tuple(reference["workload"]["target"])
    assert curve.onCurve(target) and curve.mul(target, order) is None
    eigenvalue = curves.frobeniusEigenvalue(curve, generator, order)
    started = time.perf_counter()
    labels, representatives, digests = enumerate_points(
        curve, onb, [generator, target], WINDOW, eigenvalue, order)
    samples = replay_sample_labels(curve, [generator, target], WINDOW,
                                   eigenvalue, order)
    elapsed = time.perf_counter() - started
    b = len(labels)
    assert b == 2 * 2 * 83 * WINDOW == 332000
    assert len(representatives) == 2 * WINDOW
    per_seed = 2 * 83 * WINDOW
    pairs = per_seed**2
    workload = {"curve_id": reference["curve_id"], "target": target,
                "input_law": reference["workload"], "target_count": 1,
                "seed_policy": "public G and public target Q", "doubling_window": WINDOW}
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    report = {
        "kind": "n83_exact_target_seed_dyadic_base_geometry",
        "scope": "exact target-dependent factor-base geometry; no index, ordinary relation, or DLP",
        "proposal_id": PROPOSAL_ID, "candidate_id": None,
        "run_id": f"{PROPOSAL_ID}W{workload_id}R1",
        "workload_id": workload_id, "workload": workload,
        "curve_id": reference["curve_id"],
        "curve_identity_record": reference["curve_identity_record"],
        "isogeny": "none", "endomorphism_order_conductor": None,
        "subgroup_order": str(order), "cofactor": reference["cofactor"],
        "generator": generator, "target": target,
        "target_seed_log": "unknown_to_algorithm",
        "factor_base": {
            "construction": "all signed-Frobenius images of 1000 consecutive doublings of G and Q",
            "nominal_seed_columns": 2,
            "geometric_selected_seed_inputs": 2,
            "doubling_window": WINDOW,
            "actual_usable_points_B_before_folding": b,
            "signed_frobenius_columns": len(representatives),
            "effective_unknown_log_columns_after_dyadic_labels": 1,
            **digests,
        },
        "frobenius_eigenvalue_mod_r": str(eigenvalue),
        "sample_scalar_label_replays": samples,
        "conditional_direct_pair_screen": {
            "exact_cross_seed_unordered_pair_count": str(pairs),
            "quotient_cross_seed_pair_generators": pairs // (2 * 83),
            "one_relation_pair_complement_probes_model_log2": math.log2(order / pairs),
            "verified_complete_solve_work_log2": None,
            "ordinary_relation_yield_measured": None,
            "target_scalar_recovered": False,
        },
        "target_dependent_base_enumeration_seconds": elapsed,
        "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "source_sha256": sha(Path(__file__)),
        "dependency_sha256": {"dyadic_base_geometry.py": sha(HERE / "dyadic_base_geometry.py")},
        "reference_sha256": sha(reference_path),
    }
    out = HERE / "runs" / "n83_dyadic_target_seed_geometry.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"curve_id": report["curve_id"], "B": b,
                      "columns": len(representatives),
                      "unknown_logs": 1, "seconds": elapsed,
                      "pair_probe_model_log2": math.log2(order / pairs)}))


if __name__ == "__main__":
    main()
