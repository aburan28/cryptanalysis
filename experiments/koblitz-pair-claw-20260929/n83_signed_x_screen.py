#!/usr/bin/env python3
"""Conditional work screen for the paired-sign x-only n=83 query kernel."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD_WORK = HERE / "n83_large_orbit_solve_work.json"
PAIRED = HERE / "runs" / "n83_signed_x_paired_bounded.json"
PAIRED_14 = HERE / "runs" / "n83_signed_x_paired_14worker.json"
PLANTED = HERE / "runs" / "n83_signed_x_nonzero_offset_planted.json"
FIRST_COMPLETED = (HERE / "runs" /
    "n83_orbit_k48194_chunk_M31_R30_tstart0_qstart0_b20_h14_rb8.json")
AGGREGATE = HERE / "runs" / "n83_large_orbit_campaign_aggregate.json"
SOURCE = HERE / "native_n83_orbit_query_signed_x.cpp"
OUTPUT = HERE / "n83_signed_x_screen.json"
M = 1 << 31
R = 1 << 30
N = 83
L = 2 * N
PLANNED_CHUNKS = 118


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    old = json.loads(OLD_WORK.read_text())
    paired = json.loads(PAIRED.read_text())
    paired_14 = json.loads(PAIRED_14.read_text())
    planted = json.loads(PLANTED.read_text())
    first = json.loads(FIRST_COMPLETED.read_text())
    aggregate = json.loads(AGGREGATE.read_text())
    curve_id = "EC1N83Ckb1h876c2921cb64"
    base_digest = "7e3c95f988225da1d586578529953ad61ae5ed62ca740eb92c2aea6d841a5a02"
    assert old["proposal_id"] == first["proposal_id"] == "Q1051"
    assert paired["proposal_id"] == paired_14[
        "proposal_id"] == planted["proposal_id"] == "Q1054"
    assert all(record["curve_id"] == curve_id for record in
               (old, paired, paired_14, planted, first, aggregate))
    assert all(record["candidate_id"] is None and
               record["isogeny"] == "none" for record in
               (old, paired, paired_14, planted, first))
    assert (paired["factor_base_enumerated_set_sha256"] ==
            planted["factor_base_enumerated_set_sha256"] ==
            first["factor_base"]["enumerated_set_sha256"] == base_digest)
    assert paired["actual_usable_points_B_before_folding"] == 8000204
    assert paired["signed_frobenius_columns"] == 48194
    assert paired["public_target"] == first["public_target"]
    assert paired_14["public_target"] == first["public_target"]
    assert paired_14["factor_base_enumerated_set_sha256"] == base_digest
    assert paired_14["actual_usable_points_B_before_folding"] == 8000204
    assert paired_14["signed_frobenius_columns"] == 48194
    assert paired_14["query_workers"] == 14
    assert paired_14["table_descriptors"] == 1 << 20
    assert paired_14["query_representatives"] == 1 << 22
    assert planted["verified_relation"]["independent_scalar_replay"]
    assert planted["natural_relation_yield"] is False
    assert paired["natural_relation_yield_verified"] is False
    assert paired["native_source_sha256"]["signed_x"] == sha(SOURCE)
    assert paired_14["native_source_sha256"]["signed_x"] == sha(SOURCE)
    assert planted["native_source_sha256"] == sha(SOURCE)
    assert first["query_representatives"] == R
    assert first["native_result"]["exact_hit_queries"] == 0
    assert int(first["native_field_add_mul_sqr_call_model"]) == int(
        old["active_R30_campaign"]["field_calls_per_completed_chunk"])
    speedup = paired_14["bounded_query_speedup_original_over_signed_x"]
    assert speedup > 1
    # Two full point additions cost 26 calls per signed pair. Sharing their
    # denominator and returning only x costs 6 adds + 5 muls + 2 sqrs = 13.
    inversions = 90 * (2 * math.ceil(M / 1024) +
                       2 * math.ceil(R / 8))
    signed_x_calls = 26 * M + 13 * R + 13 * R * N + inversions
    old_calls = 26 * M + 13 * R + 13 * R * L + inversions
    assert old_calls == int(first["native_field_add_mul_sqr_call_model"])
    model_success = old["active_R30_campaign"][
        "model_success_probability_at_plan_end"]
    assert model_success >= 0.95
    original_wall = first["wrapper_subprocess_wall_seconds"]
    native = first["native_result"]
    projected_new_wall = (original_wall - native["query_seconds"] +
                          native["query_seconds"] / speedup)
    failed_upper = int(aggregate[
        "failed_native_field_call_model_upper_bound"])
    report = {
        "kind": "n83_signed_x_conditional_first_hit_stage_screen",
        "scope": "analytical field-call model and bounded one-worker timing transferred to full-size 14-worker queries; no measured natural relation or complete IC DLP",
        "proposal_id": "Q1054", "candidate_id": None,
        "curve_id": curve_id, "isogeny": "none",
        "public_target": first["public_target"],
        "factor_base_enumerated_set_sha256": base_digest,
        "actual_usable_points_B_before_folding": 8000204,
        "signed_frobenius_columns": 48194,
        "table_descriptors_per_chunk": M,
        "query_representatives_per_chunk": R,
        "query_signed_pairs_per_chunk": R * N,
        "same_finite_support_probability_model_as_Q1051": True,
        "planned_chunks_for_95pct_model": PLANNED_CHUNKS,
        "modeled_success_probability_after_planned_chunks": model_success,
        "field_call_boundary": "native field add/mul/sqr calls plus 90 per modeled inversion, including fresh table build and exact replay per chunk; paired-sign x-only complement arithmetic counts 13 calls per two signs; excludes keying, Bloom, memory traffic, base setup, prior attempts, and scalar replay",
        "modeled_field_calls_per_completed_chunk": str(signed_x_calls),
        "modeled_field_calls_per_completed_chunk_log2": math.log2(signed_x_calls),
        "standalone_95pct_prefix_modeled_field_calls": str(
            PLANNED_CHUNKS * signed_x_calls),
        "standalone_95pct_prefix_modeled_field_calls_log2": math.log2(
            PLANNED_CHUNKS * signed_x_calls),
        "old_Q1051_field_calls_per_chunk": str(old_calls),
        "modeled_field_call_reduction_per_chunk": old_calls / signed_x_calls,
        "bounded_one_worker_query_speedup": paired[
            "bounded_query_speedup_original_over_signed_x"],
        "bounded_14_worker_query_speedup": speedup,
        "bounded_14_worker_paired_speedup_ratios": paired_14[
            "paired_query_speedup_ratios"],
        "projected_full_chunk_wall_seconds_if_speedup_transfers":
            projected_new_wall,
        "projected_95pct_days_if_bounded_speedup_transfers":
            PLANNED_CHUNKS * projected_new_wall / 86400,
        "current_target_prior_Q1051_completed_field_calls": str(old_calls),
        "current_target_prior_failed_attempts_actual_field_calls": None,
        "current_target_prior_failed_attempts_model_upper_bound": str(
            failed_upper),
        "current_target_if_remaining_117_chunks_use_signed_x_model_upper_bound_log2":
            math.log2(old_calls + (PLANNED_CHUNKS - 1) * signed_x_calls +
                      failed_upper),
        "ordinary_n83_relation_measured": False,
        "complete_solve_work_log2": None,
        "limits": [
            "The finite-support first-hit probability is a heuristic, not a measured natural-target success rate.",
            "The paired 14-worker timing used a 2^20-descriptor filter; its 1.176x query speedup may not transfer to the full 2^31-descriptor filter.",
            "Failed Q1051 attempts have unknown actual native work; their full-rectangle structural model is only an upper bound.",
            "The prior Q1051 completed chunk and failures belong to the same public target and must be charged if Q1054 continues its search.",
            "The field-call count is analytical from source operations, not a hardware-instrumented count or a calibrated complete operation equivalent.",
        ],
        "paired_receipt_sha256": sha(PAIRED),
        "paired_14_worker_receipt_sha256": sha(PAIRED_14),
        "planted_receipt_sha256": sha(PLANTED),
        "first_completed_Q1051_receipt_sha256": sha(FIRST_COMPLETED),
        "campaign_aggregate_sha256": sha(AGGREGATE),
        "native_source_sha256": sha(SOURCE),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "standalone_p95_field_calls_log2": report[
            "standalone_95pct_prefix_modeled_field_calls_log2"],
        "projected_p95_days": report[
            "projected_95pct_days_if_bounded_speedup_transfers"],
        "current_target_with_prior_failures_model_upper_log2": report[
            "current_target_if_remaining_117_chunks_use_signed_x_model_upper_bound_log2"],
    }))


if __name__ == "__main__":
    main()
