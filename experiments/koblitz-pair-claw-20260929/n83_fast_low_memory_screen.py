#!/usr/bin/env python3
"""Q1059 conditional screen: Q1058 shards with the exact Q1056 keyer."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1058 = HERE / "n83_low_memory_screen.json"
PAIRED = HERE / "runs" / "n83_fast_keyer_paired.json"
MICRO = HERE / "runs" / "n83_fast_keyer_microbenchmark.json"
PLANTED = HERE / "runs" / "n83_fast_low_memory_planted.json"
SMOKE = (HERE / "runs" /
         "n83_fast_lowmem_k48194_chunk_M20_R14_tstart0_qstart1073741824_b20_h10_rb8.json")
PAIRED_SMOKE = HERE / "runs" / "n83_low_memory_smoke_paired.json"
RUNNER = HERE / "run_n83_signed_x_chunk.py"
SOURCE = HERE / "native_n83_orbit_query_signed_x.cpp"
PAIRS = HERE / "native_n83_pairs.cpp"
OUTPUT = HERE / "n83_fast_low_memory_screen.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    shard = json.loads(Q1058.read_text())
    paired = json.loads(PAIRED.read_text())
    micro = json.loads(MICRO.read_text())
    planted = json.loads(PLANTED.read_text())
    smoke = json.loads(SMOKE.read_text())
    paired_smoke = json.loads(PAIRED_SMOKE.read_text())
    assert shard["proposal_id"] == "Q1058"
    assert paired["proposal_ids"] == ["Q1054", "Q1056"]
    assert micro["proposal_id"] == "Q1056"
    assert planted["proposal_id"] == "Q1059"
    assert smoke["proposal_id"] == "Q1059"
    assert all(r["candidate_id"] is None and r["isogeny"] == "none"
               for r in (shard, paired, micro, planted, smoke))
    assert shard["curve_id"] == paired["curve_id"] == micro[
        "curve_id"] == planted["curve_id"] == smoke["curve_id"]
    assert shard["factor_base_enumerated_set_sha256"] == paired[
        "factor_base_enumerated_set_sha256"]
    assert shard["public_target"] == paired["public_target"]
    assert smoke["public_target"] == shard["public_target"]
    assert planted["factor_base_enumerated_set_sha256"] == shard[
        "factor_base_enumerated_set_sha256"]
    assert shard["native_source_sha256"] == paired[
        "native_source_sha256"] == sha(SOURCE)
    assert shard["native_pairs_sha256"] == paired[
        "native_pairs_sha256"] == micro["native_pairs_source_sha256"] == sha(PAIRS)
    assert shard["runner_source_sha256"] == sha(RUNNER)
    assert micro["test_result"]["all_keys_equal"]
    assert planted["verified_relation"]["independent_scalar_replay"]
    assert planted["native_result"]["exact_hit_queries"] >= 1
    assert planted["natural_relation_yield"] is False
    assert planted["fast_keyer_enabled"] and planted["bloom_hashes"] == 10
    assert smoke["fast_keyer_enabled"] and smoke["hashes"] == 10
    assert smoke["native_result"]["exact_hit_queries"] == 0
    assert smoke["verified_public_target_quotient_table_dlp"] is False
    assert smoke["table_descriptors"] == 1 << 20
    assert smoke["query_representatives"] == 1 << 14
    assert smoke["query_start"] == 1 << 30
    assert paired_smoke["proposal_ids"] == ["Q1058", "Q1059"]
    assert paired_smoke["exact_native_outcomes_identical"]
    assert paired_smoke["fast_receipt_sha256"] == sha(SMOKE)
    assert paired_smoke["factor_base_enumerated_set_sha256"] == shard[
        "factor_base_enumerated_set_sha256"]
    assert paired["summary"]["exact_hit_queries"] == 0
    assert paired["summary"]["bloom_positive_queries"] == 52139
    assert len(paired["runs"]) == 4
    assert all(row["exit_code"] == 0 and row["guard_reason"] is None and
               row["swapouts_after"] == row["swapouts_before"]
               for row in paired["runs"])
    speedup = paired["summary"]["query_speedup_reference_over_fast"]
    assert speedup > 1
    m28 = next(row for row in shard["variants"] if row["table_log2"] == 28)
    assert m28["future_rectangles_after_completed_Q1051"] == 936
    projected_days = shard[
        "M28_future_query_only_days_if_R24_rate_transfers"] / speedup
    report = {
        "kind": "n83_q1059_fast_keyer_low_memory_conditional_screen",
        "scope": "Q1058 finite-support coverage and field-call model with Q1056 exact keyer; no natural relation or complete IC DLP",
        "proposal_id": "Q1059", "candidate_id": None,
        "curve_id": shard["curve_id"], "isogeny": "none",
        "public_target": shard["public_target"],
        "factor_base_enumerated_set_sha256": shard[
            "factor_base_enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": shard[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": shard["signed_frobenius_columns"],
        "algorithm": "Q1058 M28/R30 disjoint shards, signed-x arithmetic and 10-hash Bloom filter, compiled with ECC2K83_FAST_KEYER=1",
        "first_completed_Q1051_receipt_sha256": shard[
            "first_completed_Q1051_receipt_sha256"],
        "future_rectangles_after_completed_Q1051": m28[
            "future_rectangles_after_completed_Q1051"],
        "same_disjoint_coverage_and_finite_support_model_as_Q1058": True,
        "modeled_plan_end_success_probability_conditional_on_first_no_hit":
            shard["modeled_plan_end_success_probability_conditional_on_first_no_hit"],
        "modeled_future_native_field_calls_log2": m28[
            "modeled_future_field_calls_log2"],
        "selected_research_attempts_plus_future_structural_field_call_log2":
            shard["M28_selected_research_attempts_plus_future_structural_field_call_log2"],
        "measured_M20_R22_hash14_fast_keyer_query_speedup": speedup,
        "measured_M20_R22_hash14_bloom_positives": paired["summary"][
            "bloom_positive_queries"],
        "M28_R30_hash10_future_query_only_days_if_both_rate_and_speedup_transfer":
            projected_days,
        "ordinary_n83_relation_measured": False,
        "complete_solve_work_log2": None,
        "limits": [
            "The M20/R22 14-hash paired speedup is measured on a smaller filter than the planned M28/R30 10-hash rectangles. Transferring it is a second extrapolation on top of Q1058's R24-to-R30 rate transfer.",
            "The combined fast-keyer and 10-hash planted scalar replay passed, but planted decompositions do not estimate natural relation yield.",
            "The unchanged native field-call exponent excludes key conversion, Bloom probes, memory traffic, setup, and scalar replay; it is not a calibrated complete solve cost.",
            "Prior interrupted attempts have unknown actual work and are represented only by structural upper proxies.",
            "The selected-receipt account omits other same-target research trials and is not a bound on all historical target-dependent work.",
            "No natural n83 relation or complete IC DLP has been measured.",
        ],
        "Q1058_screen_sha256": sha(Q1058),
        "Q1056_paired_receipt_sha256": sha(PAIRED),
        "Q1056_micro_receipt_sha256": sha(MICRO),
        "Q1059_planted_receipt_sha256": sha(PLANTED),
        "Q1059_smoke_receipt_sha256": sha(SMOKE),
        "paired_smoke_receipt_sha256": sha(PAIRED_SMOKE),
        "runner_source_sha256": sha(RUNNER),
        "native_source_sha256": sha(SOURCE),
        "native_pairs_sha256": sha(PAIRS),
        "bloom_core_sha256": shard["bloom_core_sha256"],
        "source_sha256": sha(Path(__file__)),
    }
    assert math.isclose(projected_days * speedup,
                        shard["M28_future_query_only_days_if_R24_rate_transfers"])
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "future_field_calls_log2": m28["modeled_future_field_calls_log2"],
        "conditional_query_only_days_if_two_transfers_hold": projected_days,
        "paired_bounded_query_speedup": speedup,
    }))


if __name__ == "__main__":
    main()
