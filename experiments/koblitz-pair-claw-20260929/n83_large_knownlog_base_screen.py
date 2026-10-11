#!/usr/bin/env python3
"""Screen the exact doubled n=83 base with one 2^31 descriptor table."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD_BASE = HERE / "runs" / "n83_knownlog_orbit_base.json"
NEW_BASE = HERE / "runs" / "n83_knownlog_orbit_base_k48194.json"
NEW_BASE_VERIFIED = HERE / "runs" / "n83_knownlog_orbit_base_k48194_verified.json"
PLANTED = HERE / "runs" / "n83_large_orbit_nonzero_offset_planted.json"
WORKERS = HERE / "runs" / "n83_large_orbit_worker_count_paired.json"
MEASURED_NEW_M28 = HERE / "runs" / "n83_orbit_k48194_chunk_M28_R20_tstart0_qstart0_b20_h14_rb8.json"
MEASURED_NEW_M31 = HERE / "runs" / "n83_orbit_k48194_chunk_M31_R20_tstart0_qstart0_b20_h14_rb8.json"
MEASURED_M31 = HERE / "runs" / "n83_orbit_chunk_M31_R20_tstart0_qstart0_b20_h14_rb8.json"
OLD_SCREEN = HERE / "n83_query_orbit_reuse_screen.json"
OUTPUT = HERE / "n83_large_knownlog_base_screen.json"
M = 1 << 31
R = 1 << 31
L = 166


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probability(mu, key_cap, pair_domain, table_count, query_pairs):
    f = table_count / key_cap
    t = query_pairs / pair_domain
    return -math.expm1(-mu * (1 - (1 - f * t) ** 6))


def field_calls_per_chunk():
    inversions = 2 * math.ceil(M / 1024) + 2 * math.ceil(R / 8)
    return 26 * M + 13 * R + 13 * R * L + 90 * inversions


def main():
    old = json.loads(OLD_BASE.read_text())
    new = json.loads(NEW_BASE.read_text())
    verified_base = json.loads(NEW_BASE_VERIFIED.read_text())
    planted = json.loads(PLANTED.read_text())
    workers = json.loads(WORKERS.read_text())
    measured_new = json.loads(MEASURED_NEW_M28.read_text())
    measured_new_m31 = json.loads(MEASURED_NEW_M31.read_text())
    measured = json.loads(MEASURED_M31.read_text())
    old_screen = json.loads(OLD_SCREEN.read_text())
    assert old["curve_id"] == new["curve_id"] == measured["curve_id"]
    assert new["curve_identity_record"] == old["curve_identity_record"]
    assert new["isogeny"] == "none"
    assert new["proposal_id"] == "Q1051" and new["candidate_id"] is None
    assert new["source_sha256"] == sha(
        HERE / "build_n83_knownlog_base_k48194.py")
    assert verified_base["all_checks_passed"] is True
    assert verified_base["base_receipt_sha256"] == sha(NEW_BASE)
    assert verified_base["verifier_source_sha256"] == sha(
        HERE / "verify_n83_knownlog_base_k48194.py")
    assert planted["verified_relation"]["independent_scalar_replay"] is True
    assert planted["base_receipt_sha256"] == sha(NEW_BASE)
    assert planted["source_sha256"] == sha(
        HERE / "verify_n83_large_orbit_planted.py")
    assert workers["proposal_id"] == "Q1051"
    assert workers["factor_base_enumerated_set_sha256"] == new[
        "factor_base"]["enumerated_set_sha256"]
    assert workers["identical_exact_outcomes"] is True
    assert workers[
        "native_exact_hits_pending_independent_verification"] == 0
    assert workers["source_sha256"] == sha(
        HERE / "bench_n83_large_orbit_workers.py")
    assert measured_new["proposal_id"] == "Q1051"
    assert measured_new["base_receipt_sha256"] == sha(NEW_BASE)
    assert measured_new["table_descriptors"] == 1 << 28
    assert measured_new["query_representatives"] == 1 << 20
    assert measured_new["native_result"]["exact_hit_queries"] == 0
    assert measured_new["verified_public_target_quotient_table_dlp"] is False
    assert measured_new["wrapper_source_sha256"] == sha(
        HERE / "run_n83_orbit_chunk_k48194.py")
    assert measured_new["native_source_sha256"] == planted[
        "native_source_sha256"]
    assert measured_new["bloom_core_sha256"] == planted[
        "bloom_core_sha256"]
    assert measured_new["native_pairs_sha256"] == planted[
        "native_pairs_sha256"]
    assert measured_new_m31["proposal_id"] == "Q1051"
    assert measured_new_m31["base_receipt_sha256"] == sha(NEW_BASE)
    assert measured_new_m31["table_descriptors"] == M
    assert measured_new_m31["query_representatives"] == 1 << 20
    assert measured_new_m31["native_result"]["exact_hit_queries"] == 0
    assert measured_new_m31[
        "verified_public_target_quotient_table_dlp"] is False
    for key in ("native_source_sha256", "bloom_core_sha256",
                "native_pairs_sha256", "compiled_binary_sha256",
                "wrapper_source_sha256", "key_file_sha256",
                "public_target", "bits_per_key", "hashes",
                "representative_batch", "query_workers"):
        assert measured_new_m31[key] == measured_new[key]
    base = new["factor_base"]
    previous = old["factor_base"]
    assert base["seed"] == previous["seed"]
    assert base["selected_point_orbits"] == 48194
    assert base["actual_usable_points_B_before_folding"] == 8000204
    assert base["signed_frobenius_columns"] == 48194
    assert base["signed_frobenius_orbit_size"] == L
    assert measured["table_descriptors"] == 1 << 31
    assert measured["query_representatives"] == 1 << 20
    assert measured["native_result"]["exact_hit_queries"] == 0
    assert old_screen["factor_base_enumerated_set_sha256"] == previous[
        "enumerated_set_sha256"]
    order = new["curve_identity_record"]["curve"]["subgroup_order"]
    b = base["actual_usable_points_B_before_folding"]
    k = base["signed_frobenius_columns"]
    mu = math.comb(b + 3, 4) / order
    pair_domain = b * (b + 1) // 2
    key_cap = math.comb(k, 2) * L + b // 2
    cross_representatives = math.comb(k, 2) * L
    max_chunks = cross_representatives // R
    assert probability(mu, key_cap, pair_domain, M,
                       max_chunks * R * L) >= 0.95
    low, high = 1, max_chunks
    while low < high:
        middle = (low + high) // 2
        if probability(mu, key_cap, pair_domain, M,
                       middle * R * L) >= 0.95:
            high = middle
        else:
            low = middle + 1
    chunks = low
    assert chunks == 59
    assert probability(mu, key_cap, pair_domain, M,
                       (chunks - 1) * R * L) < 0.95
    native = measured["native_result"]
    one_chunk_projected_seconds = (
        native["build_seconds"] + native["exact_replay_seconds"] +
        native["query_seconds"] * R / measured[
            "query_representatives"])
    new_native = measured_new["native_result"]
    new_one_chunk_projected_seconds = (
        (new_native["build_seconds"] +
         new_native["exact_replay_seconds"]) * M /
        measured_new["table_descriptors"] +
        new_native["query_seconds"] * R /
        measured_new["query_representatives"])
    new_m31_native = measured_new_m31["native_result"]
    new_m31_projected_seconds = (
        new_m31_native["build_seconds"] +
        new_m31_native["exact_replay_seconds"] +
        new_m31_native["query_seconds"] * R /
        measured_new_m31["query_representatives"])
    worker_medians = workers["median_query_ns_per_lifted_pair"]
    speedup_14_over_8 = (worker_medians["8"] /
                         worker_medians["14"])
    new_m31_14worker_projected_seconds = (
        new_m31_native["build_seconds"] +
        new_m31_native["exact_replay_seconds"] +
        new_m31_native["query_seconds"] * R /
        measured_new_m31["query_representatives"] /
        speedup_14_over_8)
    measured_false_positive_rate = (
        new_m31_native["false_positive_queries"] /
        measured_new_m31["lifted_query_pairs"])
    process_overhead = (
        new_m31_native["peak_rss_bytes"] -
        new_m31_native["bloom_bytes"] -
        new_m31_native["candidate_vector_capacity_bytes"])
    illustrative_candidate_capacity = (
        2 * R * L * measured_false_positive_rate * 24)
    illustrative_full_chunk_peak = (
        new_m31_native["bloom_bytes"] + process_overhead +
        illustrative_candidate_capacity)
    total_calls = chunks * field_calls_per_chunk()
    old_total_calls = 88 * field_calls_per_chunk()
    assert math.isclose(math.log2(old_total_calls), old_screen[
        "four_2pow31_shards_95pct_conditional_field_calls_log2"])
    report = {
        "kind": "n83_doubled_knownlog_base_single_shard_conditional_screen",
        "scope": "exact extended base, planted scalar control, measured full-table bounded-query throughput, and heuristic relation yield; no ordinary relation or IC DLP",
        "proposal_id": "Q1051", "candidate_id": None,
        "curve_id": new["curve_id"],
        "curve_identity_record": new["curve_identity_record"],
        "isogeny": "none",
        "factor_base": base,
        "table_descriptors": M,
        "table_shards": 1,
        "campaign_query_workers": 14,
        "query_representatives_per_chunk": R,
        "cross_orbit_query_representative_domain":
            cross_representatives,
        "unordered_query_pair_domain": pair_domain,
        "zero_pair_key_cap_before_accidental_collisions": key_cap,
        "heuristic_mean_four_point_multisets": mu,
        "query_chunks_for_95pct_model": chunks,
        "query_lifted_pairs_for_95pct_model": chunks * R * L,
        "model_success_probability_at_prefix": probability(
            mu, key_cap, pair_domain, M, chunks * R * L),
        "conditional_field_add_mul_sqr_calls_total": str(total_calls),
        "conditional_field_add_mul_sqr_calls_total_log2":
            math.log2(total_calls),
        "original_base_four_shard_field_calls_log2": old_screen[
            "four_2pow31_shards_95pct_conditional_field_calls_log2"],
        "field_call_ratio_original_to_extended": (
            old_total_calls / total_calls),
        "projected_days_from_original_base_2pow31_rates":
            chunks * one_chunk_projected_seconds / 86400,
        "projected_days_from_extended_base_2pow28_rates":
            chunks * new_one_chunk_projected_seconds / 86400,
        "projected_days_from_extended_base_2pow31_rates":
            chunks * new_m31_projected_seconds / 86400,
        "paired_bounded_query_speedup_14_vs_8_workers":
            speedup_14_over_8,
        "projected_days_if_bounded_14worker_speedup_holds_at_2pow31_filter":
            chunks * new_m31_14worker_projected_seconds / 86400,
        "measured_extended_base_2pow28_stage": {
            "table_descriptors": measured_new["table_descriptors"],
            "query_representatives": measured_new[
                "query_representatives"],
            "bloom_bytes": new_native["bloom_bytes"],
            "peak_rss_bytes": new_native["peak_rss_bytes"],
            "build_seconds": new_native["build_seconds"],
            "query_seconds": new_native["query_seconds"],
            "exact_replay_seconds": new_native["exact_replay_seconds"],
            "exact_hit_queries": new_native["exact_hit_queries"],
        },
        "measured_extended_base_2pow31_stage": {
            "table_descriptors": measured_new_m31[
                "table_descriptors"],
            "query_representatives": measured_new_m31[
                "query_representatives"],
            "bloom_bytes": new_m31_native["bloom_bytes"],
            "peak_rss_bytes": new_m31_native["peak_rss_bytes"],
            "build_seconds": new_m31_native["build_seconds"],
            "query_seconds": new_m31_native["query_seconds"],
            "exact_replay_seconds": new_m31_native[
                "exact_replay_seconds"],
            "exact_hit_queries": new_m31_native[
                "exact_hit_queries"],
        },
        "measured_2pow31_false_positive_fraction":
            measured_false_positive_rate,
        "illustrative_full_2pow31_query_chunk_candidate_capacity_bytes":
            illustrative_candidate_capacity,
        "illustrative_full_2pow31_query_chunk_peak_filter_phase_bytes":
            illustrative_full_chunk_peak,
        "extended_base_native_throughput_measured": True,
        "planted_nonzero_offset_scalar_replay_passed": True,
        "ordinary_n83_relation_measured": False,
        "complete_solve_work_log2": None,
        "assumptions_and_limits": [
            "The exact new base and its logs are independently verified, but the natural-target four-sum success probability is a finite-support random-base heuristic.",
            "One 2^31-descriptor table needs a 59-chunk query prefix for 95% modeled success; the same base with 58 chunks stays below 95%.",
            "The field-call model counts table build and exact replay anew in every chunk, plus batched representative and lifted target additions; it excludes keying, Bloom work, memory, setup, and scalar replay.",
            "Time projections use bounded 2^20-representative query rates at original-base 2^31, extended-base 2^28, and extended-base 2^31 table sizes. Full 2^31-representative query throughput and candidate memory remain unmeasured.",
            "The 14-worker projection applies a paired speedup measured at a smaller 2^24-descriptor table to the 2^31-filter query rate; that full-filter speedup is unmeasured.",
            "The illustrative full-chunk peak assumes twice the expected Bloom-positive candidate count at the measured false-positive rate, 24 bytes per candidate, and constant base-process overhead; it is not a memory bound.",
        ],
        "old_base_receipt_sha256": sha(OLD_BASE),
        "new_base_receipt_sha256": sha(NEW_BASE),
        "new_base_verification_sha256": sha(NEW_BASE_VERIFIED),
        "planted_receipt_sha256": sha(PLANTED),
        "worker_benchmark_receipt_sha256": sha(WORKERS),
        "measured_extended_2pow28_receipt_sha256": sha(MEASURED_NEW_M28),
        "measured_extended_2pow31_receipt_sha256": sha(MEASURED_NEW_M31),
        "measured_2pow31_receipt_sha256": sha(MEASURED_M31),
        "old_screen_sha256": sha(OLD_SCREEN),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "curve_id": report["curve_id"],
        "actual_B": b,
        "folded_columns": k,
        "chunks": chunks,
        "model_probability": report[
            "model_success_probability_at_prefix"],
        "conditional_field_calls_log2": math.log2(total_calls),
        "projected_days": report[
            "projected_days_from_extended_base_2pow31_rates"],
    }))


if __name__ == "__main__":
    main()
