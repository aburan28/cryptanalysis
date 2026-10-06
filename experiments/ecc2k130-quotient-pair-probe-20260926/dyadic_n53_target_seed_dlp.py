#!/usr/bin/env python3
"""One ordinary n53 DLP through a target-seeded four-summand quotient index.

The public target is the unknown-log seed.  Its fixture scalar is used only
after recovery, for independent validation.  Every query scalar is public to
the algorithm because it generates a known-log relation target.
"""

import hashlib
import json
import random
import resource
import time
from pathlib import Path

import curves
import field
from dyadic_base_geometry import enumerate_points
from dyadic_n53_relation_probe import build_cross_seed_index, extract_first
from perf_probe import sha
from x_only_cycle import XOnlyCycle

HERE = Path(__file__).resolve().parent
PROPOSAL_ID = "Q1019"
QUERY_SEED = 202609290153
MAX_QUERIES = 8
WINDOW = 16


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def main():
    reference_path = HERE / "runs" / "n53_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    order = int(reference["subgroup_order"])
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    target = tuple(reference["workload"]["target"])
    assert target is not None and curve.mul(target, order) is None
    assert curve.mul(generator, order) is None
    eigenvalue = curves.frobeniusEigenvalue(curve, generator, order)
    canonicalize = XOnlyCycle(onb)
    rng = random.Random(QUERY_SEED)
    query_scalars = rng.sample(range(1, order), MAX_QUERIES)
    workload = {
        "curve_id": reference["curve_id"], "target": target,
        "input_law": reference["workload"], "target_count": 1,
        "query_scalar_seed": QUERY_SEED,
        "query_scalars": query_scalars,
        "stop_rule": "first verified nonzero target coefficient or eight complete query scans",
        "window": WINDOW, "seed_policy": "public G and public target Q",
    }
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    report_path = HERE / "runs" / "n53_dyadic_target_seed_dlp.json"
    started = time.perf_counter()
    labels, representatives, digests = enumerate_points(
        curve, onb, [generator, target], WINDOW, eigenvalue, order)
    geometry_seconds = time.perf_counter() - started
    assert len(labels) == 2 * 2 * 53 * WINDOW == 3392
    index, build = build_cross_seed_index(
        curve, sorted(labels), representatives, labels, canonicalize)
    report = {
        "kind": "n53_target_seed_quotient_four_sum_dlp",
        "scope": "one public target; target-dependent base and index are charged online; n53 pilot only",
        "proposal_id": PROPOSAL_ID, "candidate_id": None,
        "run_id": f"{PROPOSAL_ID}W{workload_id}R1",
        "workload_id": workload_id, "workload": workload,
        "curve_id": reference["curve_id"],
        "curve_identity_record": reference["curve_identity_record"],
        "isogeny": "none", "endomorphism_order_conductor": None,
        "subgroup_order": str(order), "target": target,
        "factor_base": {
            "construction": "all signed-Frobenius images of 16 consecutive doublings of G and Q",
            "nominal_seed_columns": 2,
            "geometric_selected_seed_inputs": 2,
            "doubling_window": WINDOW,
            "actual_usable_points_B_before_folding": len(labels),
            "signed_frobenius_columns": len(representatives),
            "effective_unknown_log_columns_after_dyadic_labels": 1,
            **digests,
        },
        "frobenius_eigenvalue_mod_r": str(eigenvalue),
        "online_interval": "first target-dependent base operation through independent scalar replay",
        "online_phase_seconds": {"factor_base": geometry_seconds,
                                 "index_build": build["build_seconds"],
                                 "relation_queries": None,
                                 "linear_recovery_and_check": None},
        "index_build": build,
        "query_rows": [], "status": "running", "recovered_scalar": None,
        "verified_single_target_dlp": False,
        "total_pair_complement_probes": 0,
        "online_wall_seconds": None,
        "field_operation_equivalent": None,
        "source_sha256": sha(Path(__file__)),
        "dependency_sha256": {name: sha(HERE / name) for name in (
            "dyadic_base_geometry.py", "dyadic_n53_relation_probe.py",
            "batch_x_only.py", "x_only_cycle.py", "curves.py", "field.py")},
        "reference_sha256": sha(reference_path),
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    query_time = 0.0
    recovery_time = 0.0
    for index_no, alpha in enumerate(query_scalars):
        query_target = curve.mul(generator, alpha)
        witness, query = extract_first(curve, index, query_target, canonicalize)
        query_time += query["wall_seconds"]
        report["total_pair_complement_probes"] += query["lookups_including_failed"]
        row = {"query_index": index_no, "known_scalar_alpha": alpha,
               "query_target": query_target, "ordinary_query": query,
               "relation": None}
        if witness is not None:
            check_started = time.perf_counter()
            vector = [0, 0]
            total = None
            for point in witness:
                total = curve.add(total, point)
                seed, coefficient = labels[point]
                vector[seed] = (vector[seed] + coefficient) % order
            assert total == query_target
            replay = curve.add(curve.mul(generator, vector[0]),
                               curve.mul(target, vector[1]))
            assert replay == query_target
            relation = {"point_witness": witness,
                        "coefficient_vector_mod_r": vector,
                        "group_sum_and_seed_scalar_replay_verified": True,
                        "target_coefficient_nonzero": vector[1] != 0}
            if vector[1]:
                scalar = (alpha - vector[0]) * pow(vector[1], -1, order) % order
                assert curve.mul(generator, scalar) == target
                assert scalar == reference["target_fixture_scalar"]
                relation["recovered_scalar"] = scalar
                relation["independent_scalar_replay_verified"] = True
                report["recovered_scalar"] = scalar
                report["verified_single_target_dlp"] = True
                report["status"] = "verified_dlp"
            row["relation"] = relation
            recovery_time += time.perf_counter() - check_started
        report["query_rows"].append(row)
        report["online_phase_seconds"]["relation_queries"] = query_time
        report["online_phase_seconds"]["linear_recovery_and_check"] = recovery_time
        report["online_wall_seconds"] = time.perf_counter() - started
        report["peak_process_rss_bytes"] = resource.getrusage(
            resource.RUSAGE_SELF).ru_maxrss
        if report["status"] != "verified_dlp":
            report["status"] = ("running" if index_no + 1 < MAX_QUERIES else
                                "query_limit_no_dlp")
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"query_index": index_no, "status": query["status"],
                          "lookups": query["lookups_including_failed"],
                          "verified_dlp": report["verified_single_target_dlp"],
                          "online_seconds": report["online_wall_seconds"]}), flush=True)
        if report["verified_single_target_dlp"]:
            break


if __name__ == "__main__":
    main()
