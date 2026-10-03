#!/usr/bin/env python3
"""Reserve the next 32 disjoint M32/R29 searches after Q1084."""

import hashlib
import json
import math
from pathlib import Path

from n83_full_spill_screen import field_calls

HERE = Path(__file__).resolve().parent
Q1081 = HERE / "n83_q1081_m32_wave_plan.json"
Q1083 = HERE / "n83_m32_wave_q1083_design.json"
Q1084 = HERE / "n83_q1084_local_m33_design.json"
LEDGER = HERE / "n83_full_spill_segment_work.json"
OUTPUT = HERE / "n83_m32_wave_q1085_design.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    q1081 = json.loads(Q1081.read_text())
    q1083 = json.loads(Q1083.read_text())
    q1084 = json.loads(Q1084.read_text())
    ledger = json.loads(LEDGER.read_text())
    curve = "EC1N83Ckb1h876c2921cb64"
    base = "7e3c95f988225da1d586578529953ad61ae5ed62ca740eb92c2aea6d841a5a02"
    for row in (q1081, q1083, q1084, ledger):
        assert row["curve_id"] == curve
        assert row["isogeny"] == "none"
        assert row["factor_base_enumerated_set_sha256"] == base
        assert row["actual_usable_points_B_before_folding"] == 8000204
        assert row["signed_frobenius_columns"] == 48194
    assert q1081["query_end_exclusive"] == q1083[
        "prior_Q1081_query_end_exclusive"]
    assert q1083["query_end_exclusive"] == q1084["query_start"]
    assert q1084["query_end_exclusive"] == q1084["query_start"] + (
        1 << 30)
    assert q1083["public_target"] == q1084["public_target"] == q1081[
        "public_target"]
    assert q1083["table_start"] == q1084["table_start"] == 0
    assert q1083["table_descriptors"] == 1 << 32
    assert q1084["table_descriptors"] == 1 << 33
    assert not ledger["verified_quotient_table_dlp_receipts"]
    assert not ledger["unverified_exact_hit_receipts"]
    start = q1084["query_end_exclusive"]
    reps = 1 << 29
    starts = [start + i * reps for i in range(32)]
    end = starts[-1] + reps
    assert start % (1 << 30) == 0
    assert end == 50 * (1 << 30)
    per_job = field_calls(1 << 32, reps)
    assert str(per_job) == q1083[
        "modeled_native_field_calls_per_job"]
    report = {
        "kind": "n83_q1085_next_disjoint_thirty_two_job_M32_R29_conditional_design",
        "proposal_id": "Q1085", "candidate_id": None, "run_id": None,
        "status": "design_waiting_for_Q1083_terminal_audits",
        "curve_id": curve, "isogeny": "none",
        "factor_base_enumerated_set_sha256": base,
        "actual_usable_points_B_before_folding": 8000204,
        "signed_frobenius_columns": 48194,
        "public_target": q1081["public_target"], "target_count": 1,
        "table_start": 0, "table_descriptors": 1 << 32,
        "query_starts": starts, "query_representatives": reps,
        "prior_Q1084_query_end_exclusive": start,
        "query_end_exclusive": end,
        "max_parallel_jobs": 8,
        "cpu_backend": "x86_pclmul", "query_workers": 4,
        "representative_batch": 8,
        "bits_per_key": 20, "hashes": 10,
        "modeled_native_field_calls_per_job": str(per_job),
        "modeled_native_field_calls_thirty_two_jobs_log2": math.log2(
            32 * per_job),
        "additional_unique_M28_R27_cells_if_fresh": 32 * 64,
        "relation_placement_heuristic_hit_probability": None,
        "measured_natural_relations": None,
        "complete_solve_work_log2": None,
        "launch_gates": [
            "All 16 Q1083 jobs have terminal archived artifacts and independent checked-Sage audits with zero exact hits and no verified target DLP.",
            "Q1074 and all eight Q1081 jobs have terminal independent audits; if Q1084 launched, audit its terminal receipt before freezing this wave.",
            "Regenerate the coverage ledger and reject a verified DLP, unresolved exact hit, failed or unaudited prior full search, or overlap with completed and active intervals.",
            "Freeze a source-bound executable plan and one-shot workflow with exact 32 starts, host thresholds, bounded controls, artifact retention, and eight-job maximum concurrency."
        ],
        "limits": [
            "This is a conditional coverage reservation, not a frozen dispatch or a measured relation.",
            "The 32-job field-call model excludes keying, Bloom, memory, disk, setup, failed work, and scalar replay.",
            "Hit probability and complete-solve work remain unknown until earlier terminal audits and a refreshed coverage ledger."
        ],
        "Q1081_plan_sha256": sha(Q1081),
        "Q1083_design_sha256": sha(Q1083),
        "Q1084_design_sha256": sha(Q1084),
        "coverage_ledger_sha256_at_design": sha(LEDGER),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"proposal_id": "Q1085", "jobs": len(starts),
                      "first_query_start": start,
                      "query_end_exclusive": end,
                      "modeled_field_calls_log2": math.log2(32 * per_job)}))


if __name__ == "__main__":
    main()
