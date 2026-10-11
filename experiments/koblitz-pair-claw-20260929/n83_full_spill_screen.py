#!/usr/bin/env python3
"""Q1062: full-filter SSD-spill campaign screen for the fixed n=83 target.

The native kernel is Q1060's frozen source. Only the full table footprint
and a separate named runner differ. This is a conditional model until a
full M31/R30 Q1062 terminal receipt exists.
"""

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
BASE = HERE / "n83_large_knownlog_base_screen.json"
Q1060 = HERE / "n83_spill_low_memory_screen.json"
FIRST = RUNS / "n83_orbit_k48194_chunk_M31_R30_tstart0_qstart0_b20_h14_rb8.json"
SMOKE = RUNS / "n83_full_spill_k48194_chunk_M20_R14_tstart0_qstart1073741824_b20_h10_rb8.cpu_v2.json"
Q1060_SMOKE = RUNS / "n83_spill_lowmem_k48194_chunk_M20_R14_tstart0_qstart1073741824_b20_h10_rb8.json"
Q1060_FULL = RUNS / "n83_spill_lowmem_k48194_chunk_M28_R30_tstart0_qstart1073741824_b20_h10_rb8.json"
SOURCE = HERE / "native_n83_orbit_query_spill.cpp"
PAIRS = HERE / "native_n83_pairs.cpp"
CORE = HERE / "native_n83_bloom_core.hpp"
RUNNER = HERE / "run_n83_full_spill_chunk.py"
OUTPUT = HERE / "n83_full_spill_screen.json"
M = 1 << 31
R = 1 << 30
N = 83
L = 166
FUTURE_RANGES = 117


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def field_calls(m, r):
    inversions = 2 * math.ceil(m / 1024) + 2 * math.ceil(r / 8)
    return 26 * m + 13 * r + 13 * r * N + 90 * inversions


def main():
    base = json.loads(BASE.read_text())
    q1060 = json.loads(Q1060.read_text())
    first = json.loads(FIRST.read_text())
    smoke = json.loads(SMOKE.read_text())
    old_smoke = json.loads(Q1060_SMOKE.read_text())
    measured = json.loads(Q1060_FULL.read_text())
    assert base["proposal_id"] == first["proposal_id"] == "Q1051"
    assert (q1060["proposal_id"] == old_smoke["proposal_id"] ==
            measured["proposal_id"] == "Q1060")
    assert smoke["proposal_id"] == "Q1062"
    assert smoke["wrapper_source_sha256"] == sha(RUNNER)
    assert all(row["curve_id"] == "EC1N83Ckb1h876c2921cb64"
               for row in (base, q1060, first, smoke, old_smoke, measured))
    assert all(row["candidate_id"] is None and row["isogeny"] == "none"
               for row in (base, q1060, first, smoke, old_smoke, measured))
    digest = base["factor_base"]["enumerated_set_sha256"]
    assert all(digest == row["factor_base"]["enumerated_set_sha256"]
               for row in (first, smoke, old_smoke, measured))
    assert digest == q1060["factor_base_enumerated_set_sha256"]
    assert (sha(SOURCE) == q1060["native_source_sha256"] ==
            smoke["native_source_sha256"])
    assert sha(PAIRS) == q1060["native_pairs_sha256"]
    assert sha(CORE) == q1060["bloom_core_sha256"]
    assert smoke["native_result"]["bloom_positive_queries"] == 247
    assert smoke["native_child_cpu_user_seconds"] > 0
    assert smoke["native_child_cpu_system_seconds"] >= 0
    assert math.isclose(smoke["native_child_cpu_total_seconds"],
                        smoke["native_child_cpu_user_seconds"] +
                        smoke["native_child_cpu_system_seconds"])
    for key in ("bloom_positive_queries", "exact_hit_queries",
                "candidate_spill_bytes", "hits"):
        assert smoke["native_result"][key] == old_smoke["native_result"][key]
    assert first["native_result"]["exact_hit_queries"] == 0
    assert measured["native_result"]["exact_hit_queries"] == 0
    assert first["table_descriptors"] == M and first["query_representatives"] == R
    assert measured["query_start"] == R and measured["table_descriptors"] == M // 8
    assert field_calls(M // 8, R) == int(
        measured["native_field_add_mul_sqr_call_model"])
    per_range = field_calls(M, R)
    future_calls = FUTURE_RANGES * per_range
    report = {
        "kind": "n83_q1062_full_filter_spill_conditional_screen",
        "scope": "same frozen Q1060 native kernel on a full M31 filter per R30 range; bounded exact controls passed, full-size memory and natural relation unmeasured",
        "proposal_id": "Q1062", "candidate_id": None, "run_id": None,
        "curve_id": base["curve_id"], "isogeny": "none",
        "curve_identity_record": base["curve_identity_record"],
        "public_target": first["public_target"],
        "factor_base": base["factor_base"],
        "table_descriptors_per_range": M,
        "table_start": 0,
        "query_representatives_per_range": R,
        "query_range_starts": [R, FUTURE_RANGES * R],
        "remaining_full_ranges_after_Q1051": FUTURE_RANGES,
        "bits_per_key": 20, "hashes": 10, "representative_batch": 8,
        "query_workers": 14,
        "native_source_reused_from_Q1060": True,
        "measured_bounded_smoke_bloom_positives": smoke[
            "native_result"]["bloom_positive_queries"],
        "measured_bounded_smoke_exact_hits": smoke[
            "native_result"]["exact_hit_queries"],
        "measured_bounded_smoke_native_cpu_seconds": smoke[
            "native_child_cpu_total_seconds"],
        "full_M31_R30_Q1062_terminal_measured": False,
        "modeled_field_calls_per_full_range": str(per_range),
        "modeled_field_calls_per_full_range_log2": math.log2(per_range),
        "modeled_117_future_ranges_field_calls_log2": math.log2(future_calls),
        "modeled_Q1051_plus_117_Q1062_field_calls_log2": math.log2(
            int(first["native_field_add_mul_sqr_call_model"]) + future_calls),
        "modeled_success_probability_conditional_on_first_Q1051_no_hit":
            q1060["modeled_plan_end_success_probability_conditional_on_first_no_hit"],
        "Q1060_completed_first_shard_is_overlapped_by_first_Q1062_range": True,
        "Q1060_completed_first_shard_field_calls_log2": measured[
            "native_field_add_mul_sqr_call_model_log2"],
        "Q1060_sunk_and_prior_failed_actual_work": None,
        "complete_solve_work_log2": None,
        "ordinary_n83_relation_measured": False,
        "limits": [
            "Q1062 would recompute the first Q1060 shard in its first full range; the Q1060 receipt remains separately charged historical work and contributes no extra disjoint coverage.",
            "An in-flight second Q1060 shard and any further Q1060 results must be reconciled before a Q1062 full launch; this screen pins only the first completed Q1060 shard.",
            "The success probability is the frozen Q1051 random-base finite-support heuristic, not an observed natural relation rate.",
            "Full M31/R30 Q1062 peak RSS and wall time are unmeasured; Q1051's full-filter receipt used a different hash count and in-memory candidate buffer.",
            "Field calls omit keying, Bloom operations, memory and SSD traffic, historical failed work, and independent scalar replay.",
        ],
        "base_screen_sha256": sha(BASE),
        "Q1060_screen_sha256": sha(Q1060),
        "first_Q1051_receipt_sha256": sha(FIRST),
        "Q1060_full_receipt_sha256": sha(Q1060_FULL),
        "Q1062_smoke_receipt_sha256": sha(SMOKE),
        "Q1060_smoke_receipt_sha256": sha(Q1060_SMOKE),
        "native_source_sha256": sha(SOURCE),
        "native_pairs_sha256": sha(PAIRS),
        "bloom_core_sha256": sha(CORE),
        "runner_source_sha256": sha(RUNNER),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "future_ranges": FUTURE_RANGES,
        "modeled_future_field_calls_log2": math.log2(future_calls),
        "full_size_measured": False,
        "complete_solve_work_log2": None,
    }))


if __name__ == "__main__":
    main()
