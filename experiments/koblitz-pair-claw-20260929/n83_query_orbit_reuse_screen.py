#!/usr/bin/env python3
"""Conditional n=83 pair-orbit reuse work screen from exact indexing controls."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
FINITE = HERE / "n83_knownlog_conditional_screen.json"
N23 = HERE / "runs" / "n23_query_orbit_reuse_control.json"
N83 = HERE / "runs" / "n83_query_orbit_reuse_sample.json"
NATIVE = HERE / "runs" / "n83_native_query_orbit_bounded.json"
ABBA = HERE / "runs" / "n83_orbit_reuse_vs_direct_ABBA_bounded.json"
MEASURED_M28 = HERE / "runs" / "n83_orbit_chunk_M28_R20_tstart0_qstart0_b20_h14_rb8.json"
OUTPUT = HERE / "n83_query_orbit_reuse_screen.json"
M = 1 << 32
REPRESENTATIVES_PER_CHUNK = 1 << 31
BATCH = 1024
REP_BATCH = 8


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def success(finite, table_descriptors, query_pairs):
    f = table_descriptors / finite[
        "signed_frobenius_zero_pair_key_cap_before_accidental_collisions"]
    t = query_pairs / finite["unordered_pair_domain"]
    mu = finite[
        "heuristic_mean_four_point_multiset_relations_for_one_target"]
    return -math.expm1(-mu * (1 - (1 - f * t) ** 6))


def calls_per_chunk(m, reps, orbit_size):
    query_pairs = reps * orbit_size
    inversions = (2 * math.ceil(m / BATCH) +
                  2 * math.ceil(reps / REP_BATCH))
    return (26 * m + 13 * reps + 13 * query_pairs +
            90 * inversions)


def main():
    finite = json.loads(FINITE.read_text())
    n23 = json.loads(N23.read_text())
    n83 = json.loads(N83.read_text())
    native = json.loads(NATIVE.read_text())
    abba = json.loads(ABBA.read_text())
    measured_m28 = json.loads(MEASURED_M28.read_text())
    assert n23["all_checks_passed"] and n83["all_checks_passed"]
    assert n83["curve_id"] == finite["curve_id"]
    assert n83["factor_base_enumerated_set_sha256"] == finite[
        "factor_base_enumerated_set_sha256"]
    assert native["curve_id"] == abba["curve_id"] == finite["curve_id"]
    assert native["factor_base"]["enumerated_set_sha256"] == finite[
        "factor_base_enumerated_set_sha256"]
    assert abba["factor_base_enumerated_set_sha256"] == finite[
        "factor_base_enumerated_set_sha256"]
    assert native["planted_control"]["verified_relation"][
        "independent_scalar_replay"] is True
    assert native["planted_control"]["table_start"] == 1024
    assert native["planted_control"]["query_start"] == 256
    assert all(row["exact_hit_queries"] == 0 for row in native[
        "public_target_runs"])
    assert abba["direct_to_orbit_query_speedup"] > 1
    assert measured_m28["curve_id"] == finite["curve_id"]
    assert measured_m28["factor_base"]["enumerated_set_sha256"] == finite[
        "factor_base_enumerated_set_sha256"]
    assert measured_m28["table_descriptors"] == 1 << 28
    assert measured_m28["query_representatives"] == 1 << 20
    assert measured_m28["native_result"]["exact_hit_queries"] == 0
    K = n83["signed_frobenius_columns"]
    L = 166
    cross_reps = math.comb(K, 2) * L
    assert cross_reps == n83["cross_orbit_pair_representative_domain"]
    cross_pairs = cross_reps * L
    within_pairs = K * L * (L + 1) // 2
    assert cross_pairs + within_pairs == finite["unordered_pair_domain"]
    target_95_queries = next(item[
        "ideal_unique_query_pairs_for_95pct_success"]
        for item in finite["tradeoff_rows"]
        if item["hypothetical_distinct_table_keys"] == 1 << 33)
    chunks_per_shard = math.ceil(
        target_95_queries / (L * REPRESENTATIVES_PER_CHUNK))
    rep_prefix = chunks_per_shard * REPRESENTATIVES_PER_CHUNK
    assert rep_prefix <= cross_reps
    queries_per_shard = rep_prefix * L
    chunk_calls = calls_per_chunk(M, REPRESENTATIVES_PER_CHUNK, L)
    total_calls = 2 * chunks_per_shard * chunk_calls
    measured = measured_m28["native_result"]
    measured_m = measured_m28["table_descriptors"]
    measured_q = measured_m28["lifted_query_pairs"]
    full_q = REPRESENTATIVES_PER_CHUNK * L
    full_seconds_per_chunk = (
        measured["build_seconds"] * M / measured_m +
        measured["query_seconds"] * full_q / measured_q +
        measured["exact_replay_seconds"] * M / measured_m)
    full_projected_days = (2 * chunks_per_shard *
                           full_seconds_per_chunk / 86400)
    measured_fpr = (measured["false_positive_queries"] /
                    measured_q)
    process_overhead = (measured["peak_rss_bytes"] -
                        measured["bloom_bytes"] -
                        measured["candidate_vector_capacity_bytes"])

    def projected_peak(m):
        bloom_bytes = ((m * 20 + 511) // 512 + 1024) * 64
        # Twice the expected candidate count is illustrative, not a bound.
        candidate_bytes = 2 * full_q * measured_fpr * 24
        return bloom_bytes + candidate_bytes + process_overhead

    safe_m = 1 << 31
    safe_shards = 4
    safe_total_calls = (safe_shards * chunks_per_shard *
                        calls_per_chunk(safe_m,
                                        REPRESENTATIVES_PER_CHUNK, L))
    safe_seconds_per_chunk = (
        measured["build_seconds"] * safe_m / measured_m +
        measured["query_seconds"] * full_q / measured_q +
        measured["exact_replay_seconds"] * safe_m / measured_m)
    direct_chunk_queries = 1 << 38
    direct_chunks = 29
    direct_inversions = (2 * math.ceil(M / BATCH) +
                         2 * math.ceil(direct_chunk_queries / BATCH))
    direct_chunk_calls = (26 * M + 27 * direct_chunk_queries +
                          90 * direct_inversions)
    direct_total_calls = 2 * direct_chunks * direct_chunk_calls
    report = {
        "kind": "n83_signed_frobenius_query_pair_orbit_reuse_conditional_screen",
        "scope": "exact pair-orbit indexing and sampled key identities; work model only, no native runtime or natural relation",
        "proposal_id": "Q1050", "candidate_id": None,
        "curve_id": finite["curve_id"],
        "curve_identity_record": finite["curve_identity_record"],
        "isogeny": "none",
        "actual_usable_points_B_before_folding": n83[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": K,
        "factor_base_enumerated_set_sha256": n83[
            "factor_base_enumerated_set_sha256"],
        "signed_frobenius_orbit_size": L,
        "cross_orbit_query_representative_domain": cross_reps,
        "cross_orbit_lifted_query_pairs": cross_pairs,
        "within_orbit_pairs_not_covered": within_pairs,
        "within_orbit_pair_fraction": within_pairs / finite[
            "unordered_pair_domain"],
        "query_representatives_per_chunk": REPRESENTATIVES_PER_CHUNK,
        "representative_batch_size_in_field_call_model": REP_BATCH,
        "lifted_query_pairs_per_chunk": REPRESENTATIVES_PER_CHUNK * L,
        "query_chunks_per_table_shard_for_95pct_model": chunks_per_shard,
        "total_chunk_runs_for_95pct_model": 2 * chunks_per_shard,
        "representative_prefix_per_shard": rep_prefix,
        "lifted_query_pairs_per_shard": queries_per_shard,
        "model_success_probability_at_prefix": success(
            finite, 2 * M, queries_per_shard),
        "conditional_field_add_mul_sqr_calls_per_chunk": str(chunk_calls),
        "conditional_field_add_mul_sqr_calls_total": str(total_calls),
        "conditional_field_add_mul_sqr_calls_total_log2":
            math.log2(total_calls),
        "current_direct_bloom_58_chunk_field_calls": str(
            direct_total_calls),
        "field_call_ratio_direct_to_orbit_reuse": (
            direct_total_calls / total_calls),
        "bounded_native_query_ns_per_lifted_pair": [row[
            "query_ns_per_lifted_pair"] for row in native[
                "public_target_runs"]],
        "bounded_paired_ABBA_direct_to_orbit_query_speedup": abba[
            "direct_to_orbit_query_speedup"],
        "bounded_planted_nonzero_offset_scalar_replay_passed": True,
        "measured_2pow28_filter_stage": {
            "table_descriptors": measured_m,
            "query_representatives": measured_m28[
                "query_representatives"],
            "lifted_query_pairs": measured_q,
            "bloom_bytes": measured["bloom_bytes"],
            "peak_rss_bytes": measured["peak_rss_bytes"],
            "build_seconds": measured["build_seconds"],
            "query_seconds": measured["query_seconds"],
            "exact_replay_seconds": measured["exact_replay_seconds"],
            "false_positive_queries": measured[
                "false_positive_queries"],
            "exact_hit_queries": measured["exact_hit_queries"],
        },
        "two_2pow32_shards_95pct_projected_days_from_2pow28_rates":
            full_projected_days,
        "one_2pow32_shard_illustrative_peak_filter_bytes":
            projected_peak(M),
        "four_2pow31_shards_95pct_total_chunk_runs": (
            safe_shards * chunks_per_shard),
        "four_2pow31_shards_95pct_conditional_field_calls_log2":
            math.log2(safe_total_calls),
        "four_2pow31_shards_95pct_projected_days_from_2pow28_rates":
            safe_shards * chunks_per_shard *
            safe_seconds_per_chunk / 86400,
        "one_2pow31_shard_illustrative_peak_filter_bytes":
            projected_peak(safe_m),
        "native_runtime_measured": True,
        "ordinary_n83_relation_measured": False,
        "complete_solve_work_log2": None,
        "assumptions_and_limits": [
            "Every cross-orbit unordered query pair is represented exactly once by one of 166 signed-Frobenius lifts of a pair descriptor; within-orbit pairs are omitted in this proposal.",
            "The key identity is exact, but the success probability retains the random-base Poisson and schedule-placement heuristics of the finite-support screen.",
            "The operation model assumes one batched pair addition per representative and one batched target-complement addition per lifted pair, plus one filter build and exact replay per chunk.",
            "The field-call model excludes canonical keying, Bloom probes, memory traffic, base construction, and scalar replay; it is not a complete solve-work count.",
            "The paired ABBA query speedup was measured at 2^24 table descriptors with different deterministic query schedules and while another full-size shard ran concurrently; 2^32-table throughput is unmeasured.",
            "The 2^28-filter public-target run measured stage throughput without concurrent full-size work; scaling it to 2^31 or 2^32 filters is conditional and may fail under host swap or cache effects.",
            "The four-shard 2^31-table option has the same modeled success prefix but twice as many lifted target-query evaluations as two 2^32-table shards; its lower memory is projected, not verified at full size.",
        ],
        "finite_support_screen_sha256": sha(FINITE),
        "n23_control_sha256": sha(N23),
        "n83_sample_sha256": sha(N83),
        "bounded_native_receipt_sha256": sha(NATIVE),
        "paired_ABBA_receipt_sha256": sha(ABBA),
        "measured_2pow28_receipt_sha256": sha(MEASURED_M28),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "curve_id": report["curve_id"],
        "total_chunk_runs": report["total_chunk_runs_for_95pct_model"],
        "model_success_probability": report[
            "model_success_probability_at_prefix"],
        "field_calls_log2": math.log2(total_calls),
        "direct_to_orbit_field_call_ratio": (
            direct_total_calls / total_calls),
        "two_2pow32_projected_days": full_projected_days,
        "four_2pow31_projected_days": (
            safe_shards * chunks_per_shard *
            safe_seconds_per_chunk / 86400),
    }))


if __name__ == "__main__":
    main()
