#!/usr/bin/env python3
"""Q1058: conditional work for disjoint, memory-bounded n=83 table shards.

This is a finite-support stage model, not a measured relation or DLP. It
charges fresh table construction and exact replay for every rectangle.
"""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
BASE = HERE / "n83_large_knownlog_base_screen.json"
SIGNED = HERE / "n83_signed_x_screen.json"
M28 = HERE / "n83_signed_x_m28_hashes_screen.json"
PAIR = RUNS / "n83_signed_x_m28_hashes_paired.json"
PAIRED_SMOKE = RUNS / "n83_low_memory_smoke_paired.json"
FIRST = RUNS / "n83_orbit_k48194_chunk_M31_R30_tstart0_qstart0_b20_h14_rb8.json"
SOURCE = HERE / "native_n83_orbit_query_signed_x.cpp"
PAIRS = HERE / "native_n83_pairs.cpp"
CORE = HERE / "native_n83_bloom_core.hpp"
RUNNER = HERE / "run_n83_signed_x_chunk.py"
OUTPUT = HERE / "n83_low_memory_screen.json"
R = 1 << 30
FULL_M = 1 << 31
CHUNKS = 118
N = 83


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probability(coverage, mean):
    assert 0 <= coverage <= 1
    return -math.expm1(-mean * (1 - (1 - coverage) ** 6))


def signed_calls(table_entries):
    # Exactly the Q1054 analytical boundary, with a fresh build and replay.
    inversions = 90 * (2 * math.ceil(table_entries / 1024) +
                       2 * math.ceil(R / 8))
    return 26 * table_entries + 13 * R + 13 * R * N + inversions


def main():
    base = json.loads(BASE.read_text())
    signed = json.loads(SIGNED.read_text())
    m28 = json.loads(M28.read_text())
    pair = json.loads(PAIR.read_text())
    paired_smoke = json.loads(PAIRED_SMOKE.read_text())
    first = json.loads(FIRST.read_text())
    records = (base, signed, m28, pair, first)
    assert [r["proposal_id"] for r in (base, signed, m28, first)] == [
        "Q1051", "Q1054", "Q1055", "Q1051"]
    assert pair["proposal_ids"] == ["Q1054", "Q1055"]
    assert paired_smoke["proposal_ids"] == ["Q1058", "Q1059"]
    assert paired_smoke["candidate_id"] is None
    assert paired_smoke["curve_id"] == base["curve_id"]
    assert paired_smoke["isogeny"] == "none"
    assert paired_smoke["exact_native_outcomes_identical"]
    assert paired_smoke["exact_hit_queries"] == 0
    assert all(r["curve_id"] == "EC1N83Ckb1h876c2921cb64" for r in records)
    assert all(r["candidate_id"] is None and r["isogeny"] == "none"
               for r in records)
    digest = base["factor_base"]["enumerated_set_sha256"]
    assert paired_smoke["factor_base_enumerated_set_sha256"] == digest
    assert digest == "7e3c95f988225da1d586578529953ad61ae5ed62ca740eb92c2aea6d841a5a02"
    assert (signed["factor_base_enumerated_set_sha256"] ==
            m28["factor_base_enumerated_set_sha256"] ==
            pair["factor_base_enumerated_set_sha256"] ==
            first["factor_base"]["enumerated_set_sha256"] == digest)
    assert base["factor_base"]["actual_usable_points_B_before_folding"] == 8000204
    assert base["factor_base"]["signed_frobenius_columns"] == 48194
    assert signed["public_target"] == m28["public_target"] == first["public_target"]
    assert first["table_descriptors"] == FULL_M
    assert first["query_representatives"] == R
    assert first["table_start"] == first["query_start"] == 0
    assert first["native_result"]["exact_hit_queries"] == 0
    assert signed_calls(FULL_M) == int(signed["modeled_field_calls_per_completed_chunk"])
    assert sha(SOURCE) == signed["native_source_sha256"]
    assert [run["hashes"] for run in pair["runs"]] == [14, 10, 10]
    assert all(run["native_result"]["exact_hit_queries"] == 0
               for run in pair["runs"][:2])
    assert pair["runs"][2]["native_result"] is None
    assert pair["runs"][2]["field_call_model"] is None

    table_cap = base["zero_pair_key_cap_before_accidental_collisions"]
    query_domain = base["unordered_query_pair_domain"]
    mean = base["heuristic_mean_four_point_multisets"]
    qfrac = R * base["factor_base"]["signed_frobenius_orbit_size"] / query_domain
    first_coverage = FULL_M / table_cap * qfrac
    planned_coverage = CHUNKS * first_coverage
    first_p = probability(first_coverage, mean)
    planned_p = probability(planned_coverage, mean)
    assert math.isclose(planned_p, signed["modeled_success_probability_after_planned_chunks"])
    assert (CHUNKS * R <= base["cross_orbit_query_representative_domain"])

    variants = []
    for log_m in (28, 29, 30, 31):
        m = 1 << log_m
        shards = FULL_M // m
        future_rectangles = shards * (CHUNKS - 1)
        calls = signed_calls(m)
        # The completed first rectangle covers all shards at qstart=0.
        # Each future rectangle is a disjoint cross product of one table
        # shard and one R-sized query range.
        coverage_after = first_coverage + future_rectangles * (m / table_cap * qfrac)
        assert math.isclose(coverage_after, planned_coverage, rel_tol=1e-14)
        future_calls = future_rectangles * calls
        variants.append({
            "table_log2": log_m,
            "table_descriptors_per_rectangle": m,
            "disjoint_table_shards": shards,
            "remaining_query_ranges_per_shard": CHUNKS - 1,
            "future_rectangles_after_completed_Q1051": future_rectangles,
            "modeled_field_calls_per_future_rectangle": str(calls),
            "modeled_future_field_calls_log2": math.log2(future_calls),
            "modeled_completed_Q1051_plus_future_field_calls_log2":
                math.log2(int(first["native_field_add_mul_sqr_call_model"]) + future_calls),
            "modeled_success_probability_at_plan_end":
                probability(coverage_after, mean),
            "ideal_bloom_bit_array_bytes_at_20_bits_per_key":
                math.ceil(m * 20 / 8 / 64) * 64,
        })
    assert variants[-1]["future_rectangles_after_completed_Q1051"] == 117
    assert variants[0]["future_rectangles_after_completed_Q1051"] == 936

    h10 = pair["runs"][1]["native_result"]
    assert h10["table_descriptors"] == 1 << 28
    assert h10["query_representatives"] == 1 << 24
    assert h10["bloom_positive_queries"] == m28["measured_bloom_positives"]["10"]
    query_scale = R / h10["query_representatives"]
    future_m28 = variants[0]["future_rectangles_after_completed_Q1051"]
    query_only_days = (future_m28 * h10["query_seconds"] * query_scale /
                       86400)
    known_and_upper_calls = (
        int(first["native_field_add_mul_sqr_call_model"]) +
        future_m28 * signed_calls(1 << 28) +
        int(signed["current_target_prior_failed_attempts_model_upper_bound"]) +
        sum(int(run["field_call_model"]) for run in pair["runs"][:2]) +
        int(m28["interrupted_attempt_full_rectangle_field_call_model_upper_bound"]))
    # Query rate transfer is a projection. A full R30 replay may cost much
    # more than the measured R24 replay, so this is no full-wall estimate.
    report = {
        "kind": "n83_q1058_low_memory_conditional_shard_screen",
        "scope": "disjoint finite-support coverage and analytical stage calls; no natural relation or complete IC DLP",
        "proposal_id": "Q1058", "candidate_id": None,
        "curve_id": base["curve_id"], "isogeny": "none",
        "public_target": signed["public_target"],
        "factor_base_enumerated_set_sha256": digest,
        "actual_usable_points_B_before_folding": 8000204,
        "signed_frobenius_columns": 48194,
        "algorithm": "Q1055 signed-x query with 10 Bloom hashes, disjoint contiguous table shards, and 117 remaining R=2^30 query ranges per shard",
        "first_completed_Q1051_query_range": [0, R],
        "first_completed_Q1051_zero_exact_hits": True,
        "first_completed_Q1051_field_calls": first["native_field_add_mul_sqr_call_model"],
        "prior_failed_Q1051_actual_work": None,
        "prior_failed_Q1051_structural_upper_field_calls": signed[
            "current_target_prior_failed_attempts_model_upper_bound"],
        "prior_M28_completed_calibration_field_calls": str(sum(
            int(run["field_call_model"]) for run in pair["runs"][:2])),
        "prior_M28_interrupted_actual_work": None,
        "prior_M28_interrupted_structural_upper_field_calls": str(
            int(m28["interrupted_attempt_full_rectangle_field_call_model_upper_bound"])),
        "modeled_first_rectangle_success_probability": first_p,
        "modeled_plan_end_success_probability_unconditional": planned_p,
        "modeled_plan_end_success_probability_conditional_on_first_no_hit":
            (planned_p - first_p) / (1 - first_p),
        "variants": variants,
        "M28_hash10_measured_R24": {
            "query_seconds": h10["query_seconds"],
            "build_seconds": h10["build_seconds"],
            "exact_replay_seconds": h10["exact_replay_seconds"],
            "bloom_positive_queries": h10["bloom_positive_queries"],
            "peak_rss_bytes": h10["peak_rss_bytes"],
            "candidate_vector_capacity_bytes": h10[
                "candidate_vector_capacity_bytes"],
        },
        "M28_R30_query_seconds_if_R24_rate_transfers":
            h10["query_seconds"] * query_scale,
        "M28_future_query_only_days_if_R24_rate_transfers": query_only_days,
        "M28_selected_research_attempts_plus_future_structural_field_call_log2":
            math.log2(known_and_upper_calls),
        "M28_R30_bloom_positives_if_R24_rate_transfers": round(
            h10["bloom_positive_queries"] * query_scale),
        "M28_R30_peak_rss_bytes_illustrative": (
            h10["peak_rss_bytes"] - h10["candidate_vector_capacity_bytes"] +
            round(h10["candidate_vector_capacity_bytes"] * query_scale)),
        "field_call_boundary": signed["field_call_boundary"],
        "ordinary_n83_relation_measured": False,
        "complete_solve_work_log2": None,
        "limits": [
            "The success probability assumes the frozen Q1051 finite-support random-base model; it is not an empirical natural-target yield rate.",
            "The completed M31/R30 rectangle covers the first R30 query range for all eight M28 shards. The M28/R24 calibrations overlap a future range and do not add disjoint success coverage.",
            "The paired M20/R14 Q1058/Q1059 smoke also overlaps a future rectangle and does not add disjoint success coverage.",
            "Failed Q1051 and interrupted M28 attempts have unknown actual native work. Their full-rectangle structural models are upper accounting proxies, not measured consumption.",
            "The selected-receipt account includes the named Q1051 and M28 receipts plus prospective rectangles. It omits other same-target research trials, including later keyer and smoke measurements, and is not an upper bound on all historical target-dependent work.",
            "The R24-to-R30 query-time and Bloom-positive scalings are unmeasured transfers; full R30 exact replay time and peak memory are unknown.",
            "The illustrative M28 peak scales only measured candidate vector capacity. It excludes hash-table growth, allocator behavior, and swapping and is not a memory bound.",
            "Field calls exclude keying, Bloom probes, memory traffic, setup, and scalar replay, so the exponent is not a complete field-operation-equivalent DLP cost.",
            "One n83 Pollard-rho target was solved separately; this proposed IC stage has no verified natural relation and no measured rho speedup.",
        ],
        "base_screen_sha256": sha(BASE),
        "signed_screen_sha256": sha(SIGNED),
        "M28_screen_sha256": sha(M28),
        "M28_pair_receipt_sha256": sha(PAIR),
        "paired_smoke_receipt_sha256": sha(PAIRED_SMOKE),
        "first_completed_Q1051_receipt_sha256": sha(FIRST),
        "native_source_sha256": sha(SOURCE),
        "native_pairs_sha256": sha(PAIRS),
        "bloom_core_sha256": sha(CORE),
        "runner_source_sha256": sha(RUNNER),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "future_M28_rectangles": future_m28,
        "future_M28_field_calls_log2": variants[0]["modeled_future_field_calls_log2"],
        "query_only_projected_days": query_only_days,
        "conditional_success_probability": report[
            "modeled_plan_end_success_probability_conditional_on_first_no_hit"],
    }))


if __name__ == "__main__":
    main()
