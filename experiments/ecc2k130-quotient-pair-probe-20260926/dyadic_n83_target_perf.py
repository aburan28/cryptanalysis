#!/usr/bin/env python3
"""Complete L32 n83 target-seeded index and bounded ordinary query prefixes."""

import hashlib
import json
import platform
import random
import resource
import statistics
import time
from pathlib import Path

import curves
import field
from batch_x_only import query_prefix_batch
from compare_batch_x_only import CountingField
from dyadic_base_geometry import enumerate_points
from dyadic_n53_relation_probe import build_cross_seed_index
from perf_probe import sha
from x_only_cycle import XOnlyCycle

HERE = Path(__file__).resolve().parent
PROPOSAL_ID = "Q1022"
WINDOW = 32
PREFIX_LOOKUPS = 166 * 64
REPETITIONS = 3
QUERY_SEED = 202609290383


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def measured_prefix(onb, index, target, canonicalize):
    counting = CountingField(onb)
    curve = curves.Curve(counting)
    result = query_prefix_batch(curve, index, target, 83, canonicalize,
                                PREFIX_LOOKUPS)
    result["field_api_operations"] = dict(counting.counts)
    result["field_api_operation_boundary"] = (
        "public Curve/Field calls in the bounded prefix; canonical cyclic bit "
        "rotations and batch-formula direct XORs are separate")
    return result


def main():
    reference_path = HERE / "runs" / "n83_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    order = int(reference["subgroup_order"])
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    target_seed = tuple(reference["workload"]["target"])
    assert curve.onCurve(target_seed) and curve.mul(target_seed, order) is None
    lam = curves.frobeniusEigenvalue(curve, generator, order)
    canonicalize = XOnlyCycle(onb)
    started = time.perf_counter()
    labels, representatives, digests = enumerate_points(
        curve, onb, [generator, target_seed], WINDOW, lam, order)
    base_seconds = time.perf_counter() - started
    assert len(labels) == 4 * 83 * WINDOW == 10624
    index, build = build_cross_seed_index(
        curve, sorted(labels), representatives, labels, canonicalize)
    rng = random.Random(QUERY_SEED)
    alpha = rng.randrange(1, order)
    known_log_query_target = curve.mul(generator, alpha)
    workload = {"curve_id": reference["curve_id"],
                "target": target_seed,
                "input_law": reference["workload"],
                "target_count": 1,
                "known_log_query_scalar": alpha,
                "doubling_window": WINDOW,
                "bounded_lookups_per_repetition": PREFIX_LOOKUPS,
                "repetitions": REPETITIONS}
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    results = [measured_prefix(onb, index, known_log_query_target, canonicalize)
               for _ in range(REPETITIONS)]
    assert len({tuple(row["verified_hit_positions"]) for row in results}) == 1
    planted = curve.add(next(iter(index.values()))[0],
                        list(index.values())[1][0])
    positive = query_prefix_batch(curve, index, planted, 83, canonicalize, 166)
    assert positive["verified_hit_positions"]
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() != "Darwin":
        peak *= 1024
    report = {
        "kind": "n83_target_seed_L32_complete_index_bounded_query_perf",
        "scope": "exact target-dependent L32 base and complete quotient index; three bounded ordinary known-log query prefixes and one planted correctness control; no ordinary relation yield or DLP",
        "proposal_id": PROPOSAL_ID, "candidate_id": None,
        "run_id": f"{PROPOSAL_ID}W{workload_id}R1",
        "workload_id": workload_id, "workload": workload,
        "curve_id": reference["curve_id"],
        "curve_identity_record": reference["curve_identity_record"],
        "isogeny": "none", "endomorphism_order_conductor": None,
        "target_seed": target_seed,
        "factor_base": {"construction": "all signed-Frobenius images of 32 consecutive doublings of G and public Q",
                        "nominal_seed_columns": 2,
                        "doubling_window": WINDOW,
                        "actual_usable_points_B_before_folding": len(labels),
                        "signed_frobenius_columns": len(representatives),
                        "effective_unknown_log_columns_after_dyadic_labels": 1,
                        **digests},
        "frobenius_eigenvalue_mod_r": str(lam),
        "target_dependent_base_enumeration_seconds": base_seconds,
        "index_build": build,
        "ordinary_query_prefixes": results,
        "ordinary_query_prefix_median_wall_ns": int(statistics.median(
            row["wall_ns"] for row in results)),
        "ordinary_query_prefix_verified_hits": results[0]["verified_hit_positions"],
        "planted_positive_control": positive,
        "peak_process_rss_bytes": peak,
        "verified_single_target_dlp": False,
        "ordinary_relation_yield_measured": None,
        "verified_complete_solve_work_log2": None,
        "source_sha256": sha(Path(__file__)),
        "dependency_sha256": {name: sha(HERE / name) for name in (
            "dyadic_base_geometry.py", "dyadic_n53_relation_probe.py",
            "batch_x_only.py", "compare_batch_x_only.py", "x_only_cycle.py",
            "curves.py", "field.py")},
        "reference_sha256": sha(reference_path),
    }
    path = HERE / "runs" / "n83_dyadic_target_perf_L32.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"curve_id": report["curve_id"],
                      "actual_B": len(labels), "index_keys": build["quotient_keys"],
                      "build_seconds": build["build_seconds"],
                      "median_prefix_ms": report["ordinary_query_prefix_median_wall_ns"] / 1e6,
                      "ordinary_hit_positions": results[0]["verified_hit_positions"],
                      "planted_verified_hits": positive["verified_hit_positions"],
                      "peak_rss_bytes": peak}))


if __name__ == "__main__":
    main()
