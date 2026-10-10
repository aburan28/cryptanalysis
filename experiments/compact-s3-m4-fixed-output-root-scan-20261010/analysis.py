#!/usr/bin/env python3
"""Measured root costs and a conditional N131 uniform-output screen."""

from __future__ import annotations

import json
import math
from pathlib import Path

import experiment

HERE = Path(__file__).resolve().parent
OLD = experiment.OLD
BASE = OLD / "runs/n131_q1413_projected_x_w6.json"
QUERY = OLD / "runs/n131_q1414_exact_uniform_query_bound.json"


def model() -> dict:
    base = json.loads(BASE.read_text())
    query = json.loads(QUERY.read_text())
    n = 131
    weight = 6
    d = sum(math.comb(n, k) for k in range(1, weight + 1))
    k = base["signed_frobenius_columns_K"]
    assert d == base["nominal_x_mask_count"] == 6559349863
    assert k == query["folded_columns_K"] == 25036774
    assert query["curve_id"] == base["curve_id"]
    q = 1 << n
    # A fixed unordered raw x pair gives at most two S3 output roots.
    # Uniform output v thus has E[pair hits] <= 2*C(D+1,2)/2^n.
    probability_numerator = d * (d + 1)
    minimum_full_scans_95 = (
        95 * k * q + 100 * probability_numerator - 1
    ) // (100 * probability_numerator)
    minimum_root_calls_95 = minimum_full_scans_95 * d
    return {
        "schema": "q20261010103500-conditional-uniform-screen-v1",
        "curve_id": base["curve_id"],
        "field_degree": n,
        "normal_basis_weight_bound": weight,
        "raw_nonzero_x_masks_D": d,
        "actual_usable_points_B": base[
            "actual_usable_points_B_before_folding"],
        "folded_columns_K": k,
        "uniform_fixed_output_pair_hit_mean_upper_numerator": str(
            probability_numerator),
        "uniform_fixed_output_pair_hit_mean_upper_denominator": str(q),
        "uniform_fixed_output_pair_hit_mean_upper_log2": math.log2(
            probability_numerator) - n,
        "minimum_complete_fixed_output_scans_for_95pct_rank": str(
            minimum_full_scans_95),
        "minimum_complete_fixed_output_scans_log2": math.log2(
            minimum_full_scans_95),
        "minimum_s3_root_calls_for_95pct_rank": str(
            minimum_root_calls_95),
        "minimum_s3_root_calls_log2": math.log2(minimum_root_calls_95),
        "gap_above_2pow61_root_call_units_bits": math.log2(
            minimum_root_calls_95) - 61,
        "assumptions": [
            "Every scanned fixed output has a uniform F_2^131 marginal; outputs may be correlated.",
            "Every candidate enumerates all D raw weight-at-most-six first coordinates.",
            "Each unordered right-pair hit yields at most one novel relation row.",
            "All K independent rows come from these fixed-output scans.",
        ],
        "proof": ("Each unordered x pair has at most two S3 roots in the "
                  "output coordinate. Summing over D(D+1)/2 pairs bounds "
                  "the mean hits per uniform output by D(D+1)/2^131. "
                  "Novel rank cannot exceed hits. Markov bounds the "
                  "probability of rank at least K by expected hits/K."),
        "relation_query_support_bound_sha256": experiment.sha(QUERY),
        "exact_base_receipt_sha256": experiment.sha(BASE),
        "is_complete_solve_projection": False,
        "complete_cold_work_log2": None,
        "complete_online_one_target_work_log2": None,
    }


def main() -> None:
    experiment.check_freeze()
    verified = json.loads((HERE / "verification.json").read_text())
    sage = json.loads((HERE / "sage_replay.json").read_text())
    assert verified["all_eight_cells_checked"]
    assert len(sage["rows"]) == 8
    rows = verified["rows"]
    measured = []
    for row in rows:
        name = row["cell"]
        scan = json.loads((HERE / "runs" / f"{name}.scan.json").read_text())
        ops = scan["operation_counts"]["scan"]
        measured.append({
            "cell": name, "status": row["status"],
            "scanned_masks": row["scanned_masks"],
            "root_calls": row["root_calls"],
            "scan_wall_seconds": row["scan_wall_seconds"],
            "field_mul_calls": ops["field_mul_calls"],
            "field_inv_calls": ops["field_inv_calls"],
            "field_mul_per_root": ops["field_mul_calls"] /
                                  ops["s3_root_calls"],
            "field_inv_per_root": ops["field_inv_calls"] /
                                  ops["s3_root_calls"],
            "unique_weight_pairs": row["unique_weight_pairs"],
            "recorded_hits": row["recorded_hits"],
            "sage_verified_relations": sum(
                hit["status"] == "verified_four_point_relation"
                for replay in sage["rows"] if replay["cell"] == name
                for hit in replay["hits"]),
        })
    projection = model()
    output = {
        "schema": "q20261010103500-analysis-v1",
        "proposal_id": "Q20261010103500",
        "freeze_sha256": experiment.sha(HERE / "freeze.json"),
        "verification_sha256": experiment.sha(HERE / "verification.json"),
        "sage_replay_sha256": experiment.sha(HERE / "sage_replay.json"),
        "measured_stage_rows": measured,
        "conditional_n131_screen": projection,
    }
    experiment.write_json(HERE / "analysis.json", output)
    print(json.dumps({"status": "PASS", "measured_cells": len(measured),
                      "conditional_min_root_calls_log2": projection[
                          "minimum_s3_root_calls_log2"]}))


if __name__ == "__main__":
    main()
