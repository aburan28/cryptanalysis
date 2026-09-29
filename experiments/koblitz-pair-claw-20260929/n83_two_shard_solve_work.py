#!/usr/bin/env python3
"""Conditional Q1052 first-hit costs for complete query rectangles.

The finite-support relation placement is a model, not measured natural yield.
Each native invocation processes a whole rectangle before returning hits.
"""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCREEN = HERE / "n83_two_shard_screen.json"
OUTPUT = HERE / "n83_two_shard_solve_work.json"
FAILED_CALIBRATION = (HERE / "runs" /
    "n83_two_shard_chunk_M31_R24_tstart0_qstart63350767616_b20_h14_rb8.json")
QUANTILES = ("0.5", "0.8", "0.9", "0.95", "0.99")


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def success_probability(chunks, mean, table_fraction, query_fraction):
    covered = table_fraction * chunks * query_fraction
    assert 0 <= covered <= 1
    return -math.expm1(-mean * (1 - (1 - covered) ** 6))


def main():
    screen = json.loads(SCREEN.read_text())
    identity = screen["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert curve_id == screen["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert screen["proposal_id"] == "Q1052"
    assert screen["candidate_id"] is None and screen["isogeny"] == "none"
    factor = screen["factor_base"]
    assert factor["actual_usable_points_B_before_folding"] == 8000204
    assert factor["signed_frobenius_columns"] == 48194
    assert factor["enumerated_set_sha256"] == (
        "7e3c95f988225da1d586578529953ad61ae5ed62ca740eb92c2aea6d841a5a02")
    assert screen["table_shards"] == 2
    table = screen["total_table_descriptors"]
    reps = screen["query_representatives_per_chunk"]
    lift = factor["signed_frobenius_orbit_size"]
    assert table == 2 * screen["table_descriptors_per_shard"] == 1 << 32
    assert reps == 1 << 30 and lift == 166
    calls = int(screen["native_field_add_mul_sqr_call_model_per_chunk"])
    assert calls == (26 * table + 13 * reps + 13 * reps * lift +
                     90 * (2 * math.ceil(table / 1024) +
                           2 * math.ceil(reps / 8)))
    max_chunks = screen["factor_base"]["signed_frobenius_columns"] * (
        screen["factor_base"]["signed_frobenius_columns"] - 1) // 2 * lift // reps
    assert max_chunks == 179
    table_fraction = table / screen[
        "zero_pair_key_cap_before_accidental_collisions"]
    query_fraction = reps * lift / screen["unordered_query_pair_domain"]
    mean = screen["heuristic_mean_four_point_multisets"]
    cdf = [0.0] + [success_probability(
        chunk, mean, table_fraction, query_fraction)
        for chunk in range(1, max_chunks + 1)]
    assert all(a <= b for a, b in zip(cdf, cdf[1:]))
    assert cdf[58] < 0.95 <= cdf[59]
    assert math.isclose(cdf[59], screen[
        "model_success_probability_at_prefix"], rel_tol=1e-12)
    assert math.isclose(cdf[-1], screen[
        "model_success_probability_after_all_full_query_chunks"], rel_tol=1e-12)
    masses = [cdf[i] - cdf[i - 1] for i in range(1, max_chunks + 1)]
    expected_chunks_given_hit = sum(
        i * mass for i, mass in enumerate(masses, 1)) / cdf[-1]
    quantiles = {}
    for label in QUANTILES:
        threshold = float(label)
        chunk = next((i for i in range(1, max_chunks + 1)
                      if cdf[i] >= threshold), None)
        quantiles[label] = {
            "completed_chunks": chunk,
            "model_success_probability": cdf[chunk] if chunk else None,
            "cumulative_field_calls": str(chunk * calls) if chunk else None,
            "cumulative_field_calls_log2": (
                math.log2(chunk * calls) if chunk else None),
        }
    projected_days_per_chunk = (screen[
        "projected_days_if_small_filter_query_ratio_and_14_worker_speedup_transfer"] /
        screen["query_chunks_for_95pct_model"])
    failed_calibration = json.loads(FAILED_CALIBRATION.read_text())
    assert failed_calibration["kind"] == (
        "n83_public_target_two_shard_query_k48194_chunk_failed")
    assert failed_calibration["proposal_id"] == "Q1052"
    assert failed_calibration["candidate_id"] is None
    assert failed_calibration["curve_id"] == curve_id
    assert failed_calibration["isogeny"] == "none"
    assert failed_calibration["factor_base_enumerated_set_sha256"] == factor[
        "enumerated_set_sha256"]
    assert failed_calibration["native_phase_counts"] is None
    assert failed_calibration["table_descriptors_per_shard"] == 1 << 31
    assert failed_calibration["query_representatives"] == 1 << 24
    calibration_reps = failed_calibration["query_representatives"]
    failed_calibration_upper = (
        26 * table + 13 * calibration_reps +
        13 * calibration_reps * lift +
        90 * (2 * math.ceil(table / 1024) +
              2 * math.ceil(calibration_reps / 8)))
    report = {
        "kind": "n83_q1052_first_hit_conditional_work_distribution",
        "scope": "frozen finite-support heuristic; no measured natural relation or complete IC DLP",
        "proposal_id": "Q1052", "candidate_id": None,
        "curve_id": curve_id, "isogeny": "none",
        "factor_base_enumerated_set_sha256": factor[
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": factor[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": factor["signed_frobenius_columns"],
        "field_call_boundary": "native field add, multiply, and square calls plus 90 such calls per modeled inversion; includes two fresh table builds and exact replays per completed chunk; excludes base construction, keying, Bloom operations, memory traffic, prior attempts, and independent scalar replay",
        "modeled_field_calls_per_completed_chunk": str(calls),
        "modeled_field_calls_per_completed_chunk_log2": math.log2(calls),
        "first_hit_quantiles": quantiles,
        "maximum_disjoint_full_chunks": max_chunks,
        "model_success_probability_after_all_full_chunks": cdf[-1],
        "model_probability_no_hit_after_all_full_chunks": 1 - cdf[-1],
        "expected_completed_chunks_conditional_on_hit_within_full_support":
            expected_chunks_given_hit,
        "expected_field_calls_conditional_on_hit_within_full_support_log2":
            math.log2(expected_chunks_given_hit * calls),
        "all_full_chunks_field_calls_log2": math.log2(max_chunks * calls),
        "projected_days_per_chunk_if_bounded_speedups_transfer":
            projected_days_per_chunk,
        "projected_days_at_median_model_success_if_speedups_transfer":
            quantiles["0.5"]["completed_chunks"] * projected_days_per_chunk,
        "projected_days_at_95pct_model_success_if_speedups_transfer":
            quantiles["0.95"]["completed_chunks"] * projected_days_per_chunk,
        "prior_failed_full_table_calibration_actual_field_calls": None,
        "prior_failed_full_table_calibration_field_call_model_upper_bound":
            str(failed_calibration_upper),
        "prior_failed_full_table_calibration_field_call_model_upper_bound_log2":
            math.log2(failed_calibration_upper),
        "p95_plus_prior_failed_calibration_field_call_model_upper_bound_log2":
            math.log2(quantiles["0.95"]["completed_chunks"] * calls +
                      failed_calibration_upper),
        "prior_failed_calibration_receipt_sha256": hashlib.sha256(
            FAILED_CALIBRATION.read_bytes()).hexdigest(),
        "ordinary_n83_relation_measured": False,
        "complete_solve_work_log2": None,
        "limits": [
            "The first-hit probabilities assume uniform finite-support relation placement; they are not measured natural-target yield.",
            "The native run finishes a whole rectangle before reporting a hit, so quantiles charge whole completed rectangles.",
            "The conditional expected work excludes the small positive probability of no hit after all 179 full chunks.",
            "The wall-time projection transfers bounded one-worker sharing and 14-versus-8-worker ratios to full-size filters; full-size throughput is unmeasured.",
            "The failed Q1052 full-table calibration has unknown actual native work; its structural full-rectangle field-call model is only an upper bound.",
            "These stage field calls exclude prior Q1051 attempts, keying, Bloom, base setup, and final replay. They are not complete IC operations or a calibrated rho-equivalent unit.",
        ],
        "input_screen_sha256": hashlib.sha256(SCREEN.read_bytes()).hexdigest(),
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "curve_id": curve_id,
        "median_chunks": quantiles["0.5"]["completed_chunks"],
        "median_work_log2": quantiles["0.5"]["cumulative_field_calls_log2"],
        "p95_chunks": quantiles["0.95"]["completed_chunks"],
        "p95_work_log2": quantiles["0.95"]["cumulative_field_calls_log2"],
        "maximum_success_probability": cdf[-1],
    }))


if __name__ == "__main__":
    main()
