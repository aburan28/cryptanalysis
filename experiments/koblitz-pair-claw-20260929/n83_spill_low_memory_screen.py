#!/usr/bin/env python3
"""Q1060: conditional memory/work screen for SSD-spooled n=83 candidates."""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
Q1059 = HERE / "n83_fast_low_memory_screen.json"
Q1058 = HERE / "n83_low_memory_screen.json"
CONTROLS = RUNS / "n83_spill_controls.json"
SMOKE = RUNS / "n83_spill_lowmem_k48194_chunk_M20_R14_tstart0_qstart1073741824_b20_h10_rb8.json"
SOURCE = HERE / "native_n83_orbit_query_spill.cpp"
RUNNER = HERE / "run_n83_signed_x_chunk.py"
OUTPUT = HERE / "n83_spill_low_memory_screen.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    fast = json.loads(Q1059.read_text())
    shards = json.loads(Q1058.read_text())
    controls = json.loads(CONTROLS.read_text())
    smoke = json.loads(SMOKE.read_text())
    assert fast["proposal_id"] == "Q1059"
    assert shards["proposal_id"] == "Q1058"
    assert controls["proposal_id"] == smoke["proposal_id"] == "Q1060"
    assert all(r["candidate_id"] is None and r["isogeny"] == "none"
               for r in (fast, shards, controls, smoke))
    assert fast["curve_id"] == shards["curve_id"] == controls[
        "curve_id"] == smoke["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    digest = fast["factor_base_enumerated_set_sha256"]
    assert digest == shards["factor_base_enumerated_set_sha256"] == controls[
        "factor_base_enumerated_set_sha256"] == smoke[
        "factor_base"]["enumerated_set_sha256"]
    assert fast["public_target"] == controls["public_target"] == smoke[
        "public_target"]
    assert controls["planted_verified_relation"]["independent_scalar_replay"]
    assert controls["public_exact_outcomes_equal_to_Q1059"]
    assert controls["natural_relation_yield"] is False
    assert controls["native_source_sha256"] == smoke[
        "native_source_sha256"] == sha(SOURCE)
    assert smoke["candidate_spill_enabled"] and smoke["fast_keyer_enabled"]
    assert smoke["native_result"]["candidate_store_mode"] == "unlinked_file"
    assert smoke["native_result"]["exact_hit_queries"] == 0
    assert smoke["verified_public_target_quotient_table_dlp"] is False
    assert smoke["table_descriptors"] == 1 << 20
    assert smoke["query_representatives"] == 1 << 14
    assert smoke["query_start"] == 1 << 30
    assert smoke["candidate_spill_directory"] == controls[
        "candidate_spill_directory"]

    # The positive rate is transferred from the one completed M28/R24
    # h10 run. This is illustrative, not a full-R30 measurement or bound.
    positives = shards["M28_R30_bloom_positives_if_R24_rate_transfers"]
    measured = shards["M28_hash10_measured_R24"]
    assert measured["bloom_positive_queries"] == 304118
    assert measured["bloom_bytes"] == 671154176
    assert positives == 304118 * 64
    spool_bytes = positives * 24
    exact_slots = (positives * 10 // 7 + 1024) * 28
    base_rss_proxy = (measured["peak_rss_bytes"] -
                      measured["candidate_vector_capacity_bytes"] -
                      measured["bloom_bytes"])
    query_phase_rss_proxy = base_rss_proxy + measured["bloom_bytes"]
    replay_rss_if_filter_released = base_rss_proxy + exact_slots
    replay_rss_if_filter_retained = (
        base_rss_proxy + measured["bloom_bytes"] + exact_slots)
    assert query_phase_rss_proxy < replay_rss_if_filter_released
    report = {
        "kind": "n83_q1060_spilled_candidate_conditional_screen",
        "scope": "exact small controls plus prospective M28/R30 storage arithmetic; no full-size memory/rate or natural relation measured",
        "proposal_id": "Q1060", "candidate_id": None,
        "curve_id": fast["curve_id"], "isogeny": "none",
        "public_target": fast["public_target"],
        "factor_base_enumerated_set_sha256": digest,
        "actual_usable_points_B_before_folding": fast[
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": fast["signed_frobenius_columns"],
        "algorithm": "Q1059 M28/R30 signed-x fast-keyer and h10 Bloom search with Bloom-positive Candidate records in unlinked SSD-backed files",
        "first_completed_Q1051_receipt_sha256": fast[
            "first_completed_Q1051_receipt_sha256"],
        "future_rectangles_after_completed_Q1051": fast[
            "future_rectangles_after_completed_Q1051"],
        "same_disjoint_coverage_and_finite_support_model_as_Q1059": True,
        "modeled_plan_end_success_probability_conditional_on_first_no_hit":
            fast["modeled_plan_end_success_probability_conditional_on_first_no_hit"],
        "modeled_future_native_field_calls_log2": fast[
            "modeled_future_native_field_calls_log2"],
        "complete_solve_work_log2": None,
        "ordinary_n83_relation_measured": False,
        "candidate_spill_directory_in_controls": controls[
            "candidate_spill_directory"],
        "M28_R30_bloom_positives_if_R24_rate_transfers": positives,
        "M28_R30_candidate_spill_bytes_if_positive_rate_transfers":
            spool_bytes,
        "M28_R30_candidate_spill_bytes_log2": math.log2(spool_bytes),
        "M28_R30_exact_table_slot_bytes_if_positive_rate_transfers":
            exact_slots,
        "M28_R30_query_phase_rss_bytes_illustrative": query_phase_rss_proxy,
        "M28_R30_replay_rss_bytes_if_filter_released_illustrative":
            replay_rss_if_filter_released,
        "M28_R30_replay_rss_bytes_if_filter_retained_illustrative":
            replay_rss_if_filter_retained,
        "M28_R30_full_native_wall_seconds": None,
        "limits": [
            "Bloom-positive rate is scaled from one M28/R24 ten-hash run; R30 positives and storage are unmeasured.",
            "RSS arithmetic uses the measured M28/R24 peak minus Bloom and vector capacity as a base-process proxy. Allocator retention and exact-table growth can make actual peak higher; neither RSS scenario is a bound.",
            "The spill kernel writes all Bloom-positive records twice through an unlinked file and reads them for exact replay. Its full-size I/O overhead and wall time are unmeasured.",
            "The native field-call exponent is unchanged from Q1059; it excludes keying, Bloom, file I/O, memory traffic, setup, and scalar replay, and is not a complete operation-equivalent DLP cost.",
            "The Q1060 planted control is a correctness fixture, not natural relation yield.",
        ],
        "Q1059_screen_sha256": sha(Q1059),
        "Q1058_screen_sha256": sha(Q1058),
        "controls_receipt_sha256": sha(CONTROLS),
        "smoke_receipt_sha256": sha(SMOKE),
        "native_source_sha256": sha(SOURCE),
        "native_pairs_sha256": controls["native_pairs_sha256"],
        "bloom_core_sha256": controls["bloom_core_sha256"],
        "runner_source_sha256": sha(RUNNER),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "future_field_calls_log2": report[
            "modeled_future_native_field_calls_log2"],
        "spool_bytes_if_rate_transfers": spool_bytes,
        "rss_if_filter_released_illustrative": replay_rss_if_filter_released,
        "rss_if_filter_retained_illustrative": replay_rss_if_filter_retained,
    }))


if __name__ == "__main__":
    main()
