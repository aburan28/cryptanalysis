#!/usr/bin/env python3
"""Recompute matched stage costs and conditional N131 work screens."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / "experiments/compact-s3-m4-20261003"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ceil_div(numerator: int, denominator: int) -> int:
    return (numerator + denominator - 1) // denominator


def build() -> dict:
    audited = json.loads((HERE / "audit.json").read_text())
    replay = json.loads((HERE / "sage_replay.json").read_text())
    base_path = BASE / "runs/n131_q1413_projected_x_w6.json"
    bound_path = BASE / "runs/n131_q1414_exact_uniform_query_bound.json"
    exact_base = json.loads(base_path.read_text())
    uniform_bound = json.loads(bound_path.read_text())
    assert audited["status"] == replay["status"] == "PASS"
    n = exact_base["field_degree_n"]
    b = exact_base["actual_usable_points_B_before_folding"]
    k = exact_base["signed_frobenius_columns_K"]
    d = b // 2
    assert n == 131 and 2 * d == b and d == n * k
    queries = uniform_bound["query_bounds"]["rank_success_95_percent"][
        "minimum_uniform_nonidentity_queries"]
    assert queries == 209828278
    by_cell = {row["cell"]: row for row in audited["rows"]}
    reference = by_cell["n83_control_w4096"]
    rate_numerator = reference["field_mul"]
    rate_denominator = reference["root_calls"]
    optimistic_roots = queries * d
    optimistic_muls = ceil_div(optimistic_roots * rate_numerator,
                               rate_denominator)
    old_rate = reference["baseline_field_mul"] / reference["baseline_root_calls"]
    old_muls = queries * exact_base["nominal_x_mask_count"] * old_rate
    # Every unordered rational-x pair contributes at most two S3 output
    # coordinates. The output marginal here is uniform over the full field.
    output_count = 1 << n
    fixed_output_scans = ceil_div(19 * k * output_count,
                                  20 * d * (d + 1))
    fixed_output_roots = fixed_output_scans * d
    window_sweep = []
    for degree in (53, 83):
        for window in (4096, 16384):
            row = by_cell[f"n{degree}_control_w{window}"]
            window_sweep.append({
                "field_degree": degree, "window": window,
                "root_calls": row["root_calls"],
                "field_mul": row["field_mul"],
                "baseline_field_mul": row["baseline_field_mul"],
                "exact_field_mul_reduction_fraction": (
                    1 - row["field_mul"] / row["baseline_field_mul"]),
                "census_field_inversions_once": row["census_field_inv"],
                "target_scan_seconds_exploratory": row["scan_ns"] / 1e9,
                "census_seconds_once_exploratory": row["census_ns"] / 1e9,
                "peak_rss_bytes": row["peak_rss_bytes"],
            })
    return {
        "schema": "q20261010120000-analysis-v1",
        "proposal_id": "Q20261010120000", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "audit_sha256": sha(HERE / "audit.json"),
        "sage_replay_sha256": sha(HERE / "sage_replay.json"),
        "freeze_sha256": sha(HERE / "freeze.json"),
        "source_sha256": sha(Path(__file__)),
        "n131_base_receipt_sha256": sha(base_path),
        "n131_uniform_query_receipt_sha256": sha(bound_path),
        "window_sweep": window_sweep,
        "n131_optimistic_uniform_query_screen": {
            "curve_id": exact_base["curve_id"],
            "factor_base_actual_B": b, "folded_columns_K": k,
            "rational_raw_x_masks_D": d,
            "current_source_full_mask_vector_bytes": 16 * d,
            "declared_challenge_peak_rss_cap_bytes": 4 * (1 << 30),
            "current_source_n131_supported": False,
            "current_source_n131_memory_gate_pass": False,
            "streaming_successor_required_for_n131": True,
            "minimum_queries_for_95pct_rank": queries,
            "minimum_complete_rational_scans_root_calls": str(optimistic_roots),
            "minimum_complete_rational_scans_root_calls_log2":
                math.log2(optimistic_roots),
            "measured_n83_field_mul_per_root_numerator": rate_numerator,
            "measured_n83_field_mul_per_root_denominator": rate_denominator,
            "conditional_field_mul_calls": str(optimistic_muls),
            "conditional_field_mul_log2": math.log2(optimistic_muls),
            "gap_above_2pow61_field_mul_bits": math.log2(optimistic_muls) - 61,
            "predecessor_conditional_field_mul_log2_recomputed": math.log2(old_muls),
            "assumptions": [
                "Q1414 uniform nonidentity subgroup-query marginal and every returned representation is a novel row",
                "all K rows come from these queries; at least one full rational-x scan per query",
                "N83 4096-window field-multiplication rate per rational root transfers to N131",
                "a streaming N131 implementation preserves the root-operation rate without materializing the current 16*D-byte mask vector",
                "all other costs set to zero, including reusable census, output generation, final matrix and target descent",
            ],
            "is_complete_solve_projection": False,
            "complete_cold_work_log2": None,
            "complete_online_one_target_work_log2": None,
        },
        "n131_uniform_fixed_output_screen": {
            "input_law": "each scanned fixed output has a uniform F_2^131 marginal; outputs may be correlated",
            "maximum_mean_rational_pair_hits_numerator": str(d * (d + 1)),
            "maximum_mean_rational_pair_hits_denominator": str(output_count),
            "minimum_scans_for_95pct_rank": str(fixed_output_scans),
            "minimum_scans_log2": math.log2(fixed_output_scans),
            "minimum_root_calls": str(fixed_output_roots),
            "minimum_root_calls_log2": math.log2(fixed_output_roots),
            "gap_above_2pow61_root_units_bits": math.log2(fixed_output_roots) - 61,
            "proof": "At most D(D+1)/2 unordered rational-x pairs occur, each yielding at most two S3 output coordinates. Uniformity and Markov require at least ceil(0.95 K 2^n/[D(D+1)]) scans. Each complete scan visits D rational inputs.",
            "weight_hyperparameter_identity": "If every rational-x orbit has length n and each folded column is one orbit, D=nK. Thus the root-call lower bound approaches 0.95*2^n/n and changing only the sparse-weight cutoff cannot remove the uniform-output bottleneck.",
            "is_empirical_output_law": False,
            "is_complete_solve_projection": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build()
    output = HERE / "analysis.json"
    content = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.check:
        assert output.read_text() == content
        print("PASS: conditional work screens")
    else:
        assert not output.exists()
        output.write_text(content)
        print(json.dumps({"status": "PASS", "optimistic_log2": result[
            "n131_optimistic_uniform_query_screen"]["conditional_field_mul_log2"],
            "uniform_fixed_output_log2": result[
                "n131_uniform_fixed_output_screen"]["minimum_root_calls_log2"]}))


if __name__ == "__main__":
    main()
