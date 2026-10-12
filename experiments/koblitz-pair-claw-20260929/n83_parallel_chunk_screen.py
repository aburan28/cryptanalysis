#!/usr/bin/env python3
"""Conditional first-chunk size, work, memory, and time from paired n83 data."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
FINITE = HERE / "n83_knownlog_conditional_screen.json"
BLOOM = HERE / "runs" / "n83_native_bloom_exact_replay_perf.json"
PARALLEL = HERE / "runs" / "n83_native_bloom_parallel_perf.json"
RESOURCE = HERE / "n83_bloom_resource_screen.json"
OUTPUT = HERE / "n83_parallel_chunk_screen.json"
M = 1 << 33
Q = 1 << 38
WORKERS = 8
BATCH = 1024


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    finite = json.loads(FINITE.read_text())
    bloom = json.loads(BLOOM.read_text())
    parallel = json.loads(PARALLEL.read_text())
    resource = json.loads(RESOURCE.read_text())
    assert finite["curve_id"] == bloom["curve_id"] == parallel["curve_id"] == resource["curve_id"]
    assert parallel["disjoint_range_partition_checks_passed"]
    assert parallel["identical_full_query_outcomes_across_worker_counts"]
    measured = next(row for row in parallel["large_full_runs"]
                    if row["query_workers"] == WORKERS)
    assert measured["table_descriptors"] == 1 << 28
    assert measured["query_start"] == 0
    assert measured["query_pairs"] == 1 << 25
    assert measured["exact_hit_queries"] == 0
    fraction = M / finite[
        "signed_frobenius_zero_pair_key_cap_before_accidental_collisions"]
    query_fraction = Q / finite["unordered_pair_domain"]
    mean = finite["heuristic_mean_four_point_multiset_relations_for_one_target"]
    success = -math.expm1(-mean * (1 - (1 - fraction * query_fraction) ** 6))
    measured_false_rate = measured["false_positive_queries"] / measured[
        "query_pairs"]
    positive_queries = Q * measured_false_rate
    bloom_bytes = resource["hypothetical_bloom_bytes"]
    candidate_capacity_bytes = 2 * positive_queries * measured[
        "candidate_record_bytes"]
    non_table_bytes = resource["observed_nontable_rss_bytes_at_2pow28_exact_table"]
    build_seconds = M * measured["build_seconds"] / measured["table_descriptors"]
    query_seconds = Q * measured["query_seconds"] / measured["query_pairs"]
    replay_seconds = M * measured["exact_replay_seconds"] / measured[
        "table_descriptors"]
    inversions = 2 * math.ceil(M / BATCH) + 2 * math.ceil(Q / BATCH)
    field_calls = 26 * M + 27 * Q + 90 * inversions
    report = {
        "kind": "n83_one_target_first_parallel_bloom_chunk_conditional_screen",
        "scope": "first full-key-table, bounded-query chunk prediction from smaller measured table; no natural relation or IC DLP claimed",
        "proposal_id": "Q1049", "candidate_id": None,
        "curve_id": finite["curve_id"],
        "curve_identity_record": finite["curve_identity_record"],
        "isogeny": "none",
        "actual_usable_points_B_before_folding": finite[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": finite[
            "actual_signed_frobenius_columns"],
        "factor_base_enumerated_set_sha256": finite[
            "factor_base_enumerated_set_sha256"],
        "table_descriptors": M,
        "query_start": 0,
        "query_count": Q,
        "query_workers": WORKERS,
        "query_fraction_of_exact_unordered_pair_domain": query_fraction,
        "heuristic_probability_one_target_relation_in_first_chunk": success,
        "projected_bloom_bytes": bloom_bytes,
        "projected_false_positive_queries_at_bounded_rate": positive_queries,
        "illustrative_twice_count_candidate_vector_bytes":
            candidate_capacity_bytes,
        "illustrative_peak_filter_phase_bytes": (
            bloom_bytes + candidate_capacity_bytes + non_table_bytes),
        "host_physical_memory_bytes_from_resource_screen": resource[
            "host_physical_memory_bytes_from_memory_pressure"],
        "projected_filter_build_seconds_at_paired_eight_worker_run_rate":
            build_seconds,
        "projected_eight_worker_target_query_seconds_at_paired_rate":
            query_seconds,
        "projected_exact_replay_seconds_at_paired_run_rate":
            replay_seconds,
        "projected_total_seconds_excluding_base_setup_and_checks":
            build_seconds + query_seconds + replay_seconds,
        "conditional_field_add_mul_sqr_call_model": str(field_calls),
        "conditional_field_add_mul_sqr_call_model_log2": math.log2(
            field_calls),
        "verified_n83_quotient_table_dlp": False,
        "same_target_rho_reference": finite["n83_same_target_rho_reference"],
        "assumptions_and_limits": [
            "The relation probability uses the same Poisson finite-support heuristic as the prior screen and is not measured yield.",
            "The 8-worker rate was measured at 2^28 table descriptors and 2^25 target queries. It may change at a 24 GiB filter and 2^38 queries.",
            "The candidate count projects the measured 8-worker false-positive rate; vector capacity is illustrated as twice that count.",
            "Each chunk rebuilds the target-independent filter and replays its positives exactly. Repeated chunks must charge every build, query, and replay when reporting cumulative work.",
            "The field-call count omits quotient-keying, Bloom hashing and probes, memory traffic, and independent scalar replay.",
            "Physical memory headroom can change during a long run; the projection is not proof that the first chunk will finish without paging.",
        ],
        "finite_support_screen_sha256": sha(FINITE),
        "bloom_receipt_sha256": sha(BLOOM),
        "parallel_receipt_sha256": sha(PARALLEL),
        "resource_screen_sha256": sha(RESOURCE),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "curve_id": report["curve_id"],
        "heuristic_relation_probability": success,
        "projected_hours": report[
            "projected_total_seconds_excluding_base_setup_and_checks"] / 3600,
        "illustrative_peak_bytes": report[
            "illustrative_peak_filter_phase_bytes"],
        "field_calls_log2": report[
            "conditional_field_add_mul_sqr_call_model_log2"],
    }))


if __name__ == "__main__":
    main()
