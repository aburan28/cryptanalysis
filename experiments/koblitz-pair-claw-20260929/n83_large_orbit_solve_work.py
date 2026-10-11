#!/usr/bin/env python3
"""Report Q1051 first-hit work quantiles from the frozen finite-support model.

These are conditional predictions. A completed public-target rectangle is the
unit of work; the native program finishes a rectangle even if it finds a hit.
No field-call result here is a measured complete discrete logarithm.
"""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCREEN = HERE / "n83_large_knownlog_base_screen.json"
OUTPUT = HERE / "n83_large_orbit_solve_work.json"
FAILED_R31 = (HERE / "runs" /
    "n83_orbit_k48194_chunk_M31_R31_tstart0_qstart0_b20_h14_rb8.json")
FAILED_R30 = (HERE / "runs" /
    "n83_orbit_k48194_chunk_M31_R30_tstart0_qstart1073741824_b20_h14_rb8.json")
AGGREGATE = HERE / "runs" / "n83_large_orbit_campaign_aggregate.json"
FIRST_COMPLETED_R30 = (HERE / "runs" /
    "n83_orbit_k48194_chunk_M31_R30_tstart0_qstart0_b20_h14_rb8.json")
QUANTILES = ("0.5", "0.8", "0.9", "0.95", "0.99")


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def success_probability(chunks, *, mean_relations, table_fraction,
                        query_fraction_per_chunk):
    covered_pair_fraction = table_fraction * chunks * query_fraction_per_chunk
    assert 0 <= covered_pair_fraction <= 1
    return -math.expm1(-mean_relations *
                       (1 - (1 - covered_pair_fraction) ** 6))


def main():
    screen = json.loads(SCREEN.read_text())
    identity = screen["curve_identity_record"]
    curve_id = "EC1N83Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert curve_id == screen["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert screen["proposal_id"] == "Q1051"
    assert screen["candidate_id"] is None and screen["isogeny"] == "none"
    base = screen["factor_base"]
    assert base["actual_usable_points_B_before_folding"] == 8000204
    assert base["signed_frobenius_columns"] == 48194
    assert base["enumerated_set_sha256"] == (
        "7e3c95f988225da1d586578529953ad61ae5ed62ca740eb92c2aea6d841a5a02")
    table = screen["table_descriptors"]
    reps = screen["query_representatives_per_chunk"]
    lift = base["signed_frobenius_orbit_size"]
    assert table == reps == 1 << 31 and lift == 166
    max_chunks = screen["cross_orbit_query_representative_domain"] // reps
    assert max_chunks == 89
    table_fraction = table / screen[
        "zero_pair_key_cap_before_accidental_collisions"]
    query_fraction_per_chunk = reps * lift / screen[
        "unordered_query_pair_domain"]
    mean = screen["heuristic_mean_four_point_multisets"]
    inversion_equivalent_calls = 90 * (
        2 * math.ceil(table / 1024) + 2 * math.ceil(reps / 8))
    calls_per_chunk = (26 * table + 13 * reps + 13 * reps * lift +
                       inversion_equivalent_calls)
    assert math.isclose(
        math.log2(screen["query_chunks_for_95pct_model"] * calls_per_chunk),
        screen["conditional_field_add_mul_sqr_calls_total_log2"])
    cdf = [0.0] + [success_probability(
        chunk, mean_relations=mean, table_fraction=table_fraction,
        query_fraction_per_chunk=query_fraction_per_chunk)
        for chunk in range(1, max_chunks + 1)]
    assert all(a <= b for a, b in zip(cdf, cdf[1:]))
    assert cdf[58] < 0.95 <= cdf[59]
    first_hit_mass = [cdf[i] - cdf[i - 1]
                      for i in range(1, max_chunks + 1)]
    success_by_exhaustion = cdf[-1]
    expected_chunks_given_success = sum(
        chunk * chance for chunk, chance in
        enumerate(first_hit_mass, 1)) / success_by_exhaustion
    quantiles = {}
    for label in QUANTILES:
        probability = float(label)
        chunk = next((i for i in range(1, max_chunks + 1)
                      if cdf[i] >= probability), None)
        quantiles[label] = {
            "completed_chunks": chunk,
            "model_success_probability": cdf[chunk] if chunk else None,
            "cumulative_field_calls": str(chunk * calls_per_chunk)
            if chunk else None,
            "cumulative_field_calls_log2":
                math.log2(chunk * calls_per_chunk) if chunk else None,
        }
    full_chunk_projected_days = (
        screen["projected_days_if_bounded_14worker_speedup_holds_at_2pow31_filter"] /
        screen["query_chunks_for_95pct_model"])
    failed = json.loads(FAILED_R31.read_text())
    assert failed["kind"] == "n83_public_target_orbit_query_k48194_chunk_failed"
    assert failed["curve_id"] == curve_id and failed["proposal_id"] == "Q1051"
    assert failed["candidate_id"] is None and failed["isogeny"] == "none"
    assert failed["native_phase_counts"] is None
    assert failed["factor_base_enumerated_set_sha256"] == base[
        "enumerated_set_sha256"]
    assert failed["table_descriptors"] == table
    assert failed["query_representatives"] == reps
    failed_r30 = json.loads(FAILED_R30.read_text())
    assert failed_r30["kind"] == failed["kind"]
    assert failed_r30["curve_id"] == curve_id
    assert failed_r30["proposal_id"] == "Q1051"
    assert failed_r30["candidate_id"] is None
    assert failed_r30["isogeny"] == "none"
    assert failed_r30["factor_base_enumerated_set_sha256"] == base[
        "enumerated_set_sha256"]
    assert failed_r30["table_descriptors"] == table
    assert failed_r30["query_representatives"] == reps // 2
    assert failed_r30["query_start"] == reps // 2
    assert failed_r30["native_phase_counts"] is None
    half_reps = reps // 2
    half_calls = (26 * table + 13 * half_reps + 13 * half_reps * lift +
                  90 * (2 * math.ceil(table / 1024) +
                        2 * math.ceil(half_reps / 8)))
    retry_paths = []
    retry_index = 1
    while True:
        path = FAILED_R30.with_name(
            f"{FAILED_R30.stem}.retry{retry_index}.json")
        if not path.exists():
            break
        retry_paths.append(path)
        retry_index += 1
    assert set(retry_paths) == set(FAILED_R30.parent.glob(
        f"{FAILED_R30.stem}.retry*.json")), "noncontiguous retry receipts"
    assert not list(FAILED_R30.parent.glob(
        f"{FAILED_R30.stem}*.started.json")), "active retry omitted"
    failed_paths = [FAILED_R31, FAILED_R30, *retry_paths]
    for path in retry_paths:
        retry = json.loads(path.read_text())
        for key in ("kind", "curve_id", "proposal_id", "candidate_id",
                    "isogeny", "factor_base_enumerated_set_sha256",
                    "table_start", "table_descriptors", "query_start",
                    "query_representatives"):
            assert retry[key] == failed_r30[key], (path, key)
        assert retry["native_phase_counts"] is None
    aggregate = json.loads(AGGREGATE.read_text())
    assert aggregate["curve_id"] == curve_id
    assert aggregate["proposal_id"] == "Q1051"
    assert len(aggregate["failed_chunks_with_unknown_work"]) == len(
        failed_paths)
    assert {item["receipt_sha256"] for item in aggregate[
        "failed_chunks_with_unknown_work"]} == {
            hashlib.sha256(path.read_bytes()).hexdigest() for path in
            failed_paths}
    failed_upper = calls_per_chunk + (1 + len(retry_paths)) * half_calls
    assert int(aggregate["failed_native_field_call_model_upper_bound"]) == (
        failed_upper)
    half_max = screen["cross_orbit_query_representative_domain"] // half_reps
    half_cdf = [0.0] + [success_probability(
        chunk, mean_relations=mean, table_fraction=table_fraction,
        query_fraction_per_chunk=half_reps * lift / screen[
            "unordered_query_pair_domain"])
        for chunk in range(1, half_max + 1)]
    assert half_cdf[116] < 0.95 <= half_cdf[117]
    assert math.isclose(half_cdf[118], cdf[59])
    half_quantiles = {}
    for label in QUANTILES:
        probability = float(label)
        chunk = next((i for i in range(1, half_max + 1)
                      if half_cdf[i] >= probability), None)
        half_quantiles[label] = {
            "completed_chunks": chunk,
            "model_success_probability": half_cdf[chunk] if chunk else None,
            "cumulative_field_calls_log2":
                math.log2(chunk * half_calls) if chunk else None,
        }
    measured = screen["measured_extended_base_2pow31_stage"]
    half_projected_seconds = (
        measured["build_seconds"] + measured["exact_replay_seconds"] +
        measured["query_seconds"] * half_reps / (1 << 20) /
        screen["paired_bounded_query_speedup_14_vs_8_workers"])
    first_completed = json.loads(FIRST_COMPLETED_R30.read_text())
    assert first_completed["kind"] == (
        "n83_public_target_orbit_query_k48194_exact_replay_chunk")
    assert first_completed["curve_id"] == curve_id
    assert first_completed["proposal_id"] == "Q1051"
    assert first_completed["candidate_id"] is None
    assert first_completed["isogeny"] == "none"
    assert first_completed["factor_base"]["enumerated_set_sha256"] == base[
        "enumerated_set_sha256"]
    assert first_completed["table_descriptors"] == table
    assert first_completed["query_representatives"] == half_reps
    assert first_completed["table_start"] == 0
    assert first_completed["query_start"] == 0
    assert first_completed["native_result"]["exact_hit_queries"] == 0
    assert first_completed["verified_public_target_quotient_table_dlp"] is False
    assert int(first_completed["native_field_add_mul_sqr_call_model"]) == half_calls
    actual_native = first_completed["native_result"]
    actual_wall = first_completed["wrapper_subprocess_wall_seconds"]
    active_campaign = {
        "query_representatives_per_chunk": half_reps,
        "planned_chunks": 118,
        "model_success_probability_at_plan_end": half_cdf[118],
        "first_hit_quantiles": half_quantiles,
        "field_calls_per_completed_chunk": str(half_calls),
        "field_calls_per_completed_chunk_log2": math.log2(half_calls),
        "planned_completed_chunk_field_calls_log2": math.log2(118 * half_calls),
        "expected_field_calls_conditional_on_hit_within_full_support_log2":
            math.log2(half_calls * sum(
                chunk * (half_cdf[chunk] - half_cdf[chunk - 1])
                for chunk in range(1, half_max + 1)) / half_cdf[-1]),
        "maximum_disjoint_full_chunks": half_max,
        "model_probability_no_hit_after_all_full_chunks": 1 - half_cdf[-1],
        "projected_days_for_planned_chunks_if_bounded_speedup_transfers":
            118 * half_projected_seconds / 86400,
        "first_completed_R30_zero_exact_hits": True,
        "first_completed_R30_bloom_positive_queries": actual_native[
            "bloom_positive_queries"],
        "first_completed_R30_build_seconds": actual_native["build_seconds"],
        "first_completed_R30_query_seconds": actual_native["query_seconds"],
        "first_completed_R30_exact_replay_seconds": actual_native[
            "exact_replay_seconds"],
        "first_completed_R30_peak_rss_bytes": actual_native["peak_rss_bytes"],
        "first_completed_R30_wrapper_wall_seconds": actual_wall,
        "first_completed_R30_receipt_sha256": hashlib.sha256(
            FIRST_COMPLETED_R30.read_bytes()).hexdigest(),
        "projected_days_for_planned_chunks_from_one_full_R30_wall_sample":
            118 * actual_wall / 86400,
        "one_full_R30_wall_to_bounded_rate_projection_ratio":
            actual_wall / half_projected_seconds,
        "prior_failed_R31_actual_field_calls": None,
        "prior_failed_R31_field_call_model_upper_bound": str(calls_per_chunk),
        "prior_failed_R30_actual_field_calls": None,
        "prior_failed_R30_field_call_model_upper_bound": str(half_calls),
        "prior_failed_attempts_count": len(failed_paths),
        "prior_failed_attempts_field_call_model_upper_bound": str(
            failed_upper),
        "planned_plus_prior_failed_field_call_model_upper_bound_log2":
            math.log2(118 * half_calls + failed_upper),
        "prior_failed_receipt_sha256": hashlib.sha256(
            FAILED_R31.read_bytes()).hexdigest(),
        "prior_failed_R30_receipt_sha256": hashlib.sha256(
            FAILED_R30.read_bytes()).hexdigest(),
        "prior_failed_retry_receipts": [{
            "receipt": str(path.relative_to(HERE)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        } for path in retry_paths],
        "campaign_aggregate_sha256": hashlib.sha256(
            AGGREGATE.read_bytes()).hexdigest(),
    }
    report = {
        "kind": "n83_q1051_first_hit_conditional_work_distribution",
        "scope": "frozen finite-support heuristic; no measured natural relation or complete IC DLP",
        "proposal_id": "Q1051", "candidate_id": None,
        "curve_id": curve_id, "isogeny": "none",
        "factor_base_enumerated_set_sha256": base["enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": base[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": base["signed_frobenius_columns"],
        "field_call_boundary": "native field add, multiply, and square calls plus 90 such calls per modeled inversion; includes a fresh table build and exact replay for each completed chunk; excludes base construction, keying, Bloom operations, memory traffic, and independent scalar replay",
        "modeled_field_calls_per_completed_chunk": str(calls_per_chunk),
        "modeled_field_calls_per_completed_chunk_log2": math.log2(
            calls_per_chunk),
        "first_hit_quantiles": quantiles,
        "maximum_disjoint_full_chunks": max_chunks,
        "model_success_probability_after_all_full_chunks":
            success_by_exhaustion,
        "model_probability_no_hit_after_all_full_chunks":
            1 - success_by_exhaustion,
        "expected_completed_chunks_conditional_on_hit_within_full_support":
            expected_chunks_given_success,
        "expected_field_calls_conditional_on_hit_within_full_support_log2":
            math.log2(expected_chunks_given_success * calls_per_chunk),
        "all_full_chunks_field_calls_log2": math.log2(
            max_chunks * calls_per_chunk),
        "projected_days_per_full_chunk_if_bounded_worker_speedup_transfers":
            full_chunk_projected_days,
        "projected_days_at_median_model_success_if_speedup_transfers":
            quantiles["0.5"]["completed_chunks"] * full_chunk_projected_days,
        "projected_days_at_95pct_model_success_if_speedup_transfers":
            quantiles["0.95"]["completed_chunks"] * full_chunk_projected_days,
        "active_R30_campaign": active_campaign,
        "ordinary_n83_relation_measured": False,
        "complete_solve_work_log2": None,
        "limits": [
            "The success distribution assumes uniform finite-support relation placement; it is not an observed natural-target yield rate.",
            "The native run processes a whole rectangle before reporting a hit, so each first-hit quantile charges whole completed rectangles.",
            "The expected work is conditional on a hit within the 89 disjoint full chunks; the model leaves a positive no-hit probability.",
            "The older bounded-rate wall projection transfers a 14-versus-8-worker speedup from a smaller filter; that worker ratio has not been isolated at full size.",
            "The active R30 campaign now has one completed full query chunk; transferring its wall time to 118 chunks is a one-sample projection, not measured campaign time.",
            "The operation model is a specified stage boundary, not complete end-to-end IC work or a calibrated field-operation equivalent for rho.",
            "The active R30 campaign has a prior interrupted R31 attempt with unknown actual work; its structural field-call upper bound is a model, not a measured count.",
        ],
        "input_screen_sha256": hashlib.sha256(SCREEN.read_bytes()).hexdigest(),
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "curve_id": curve_id,
        "median_chunks": quantiles["0.5"]["completed_chunks"],
        "median_work_log2": quantiles["0.5"][
            "cumulative_field_calls_log2"],
        "p95_chunks": quantiles["0.95"]["completed_chunks"],
        "p95_work_log2": quantiles["0.95"][
            "cumulative_field_calls_log2"],
        "maximum_success_probability": success_by_exhaustion,
    }))


if __name__ == "__main__":
    main()
