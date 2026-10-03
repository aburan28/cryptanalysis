#!/usr/bin/env python3
"""Reserve a fresh local M33/R30 interval after the staged Q1083 wave."""

import hashlib
import json
import math
from pathlib import Path

from n83_full_spill_screen import field_calls

HERE = Path(__file__).resolve().parent
Q1074 = HERE / "n83_local_arm_m33_r30_q1074_plan.json"
Q1081 = HERE / "n83_q1081_m32_wave_plan.json"
Q1083 = HERE / "n83_m32_wave_q1083_design.json"
LEDGER = HERE / "n83_full_spill_segment_work.json"
OUTPUT = HERE / "n83_q1084_local_m33_design.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    q1074 = json.loads(Q1074.read_text())
    q1081 = json.loads(Q1081.read_text())
    q1083 = json.loads(Q1083.read_text())
    ledger = json.loads(LEDGER.read_text())
    curve = "EC1N83Ckb1h876c2921cb64"
    base = "7e3c95f988225da1d586578529953ad61ae5ed62ca740eb92c2aea6d841a5a02"
    for row in (q1074, q1081, q1083, ledger):
        assert row["curve_id"] == curve
        assert row["isogeny"] == "none"
        assert row["factor_base_enumerated_set_sha256"] == base
        assert row["actual_usable_points_B_before_folding"] == 8000204
        assert row["signed_frobenius_columns"] == 48194
    assert q1083["prior_Q1081_query_end_exclusive"] == q1081[
        "query_end_exclusive"]
    assert q1083["query_end_exclusive"] == q1083["query_starts"][-1] + (
        1 << 29)
    assert q1074["table_start"] == q1083["table_start"] == 0
    assert q1074["table_descriptors"] == 1 << 33
    assert q1074["query_representatives"] == 1 << 30
    assert not ledger["verified_quotient_table_dlp_receipts"]
    assert not ledger["unverified_exact_hit_receipts"]
    start = q1083["query_end_exclusive"]
    end = start + (1 << 30)
    assert start % (1 << 30) == 0
    assert start >= q1081["query_end_exclusive"]
    assert start >= q1074["query_end_exclusive"]
    calls = field_calls(1 << 33, 1 << 30)
    assert calls == int(q1074["modeled_native_field_calls"])
    report = {
        "kind": "n83_q1084_local_arm_M33_R30_conditional_design",
        "proposal_id": "Q1084", "candidate_id": None, "run_id": None,
        "status": "design_waiting_for_Q1074_and_Q1081_terminal_audits",
        "curve_id": curve, "isogeny": "none",
        "factor_base_enumerated_set_sha256": base,
        "actual_usable_points_B_before_folding": 8000204,
        "signed_frobenius_columns": 48194,
        "public_target": q1074["public_target"], "target_count": 1,
        "table_start": 0, "table_descriptors": 1 << 33,
        "query_start": start, "query_representatives": 1 << 30,
        "query_end_exclusive": end,
        "cpu_backend": "arm_pmull", "query_workers": 4,
        "representative_batch": 8,
        "bits_per_key": 20, "hashes": 10,
        "modeled_native_field_calls": str(calls),
        "modeled_native_field_calls_log2": math.log2(calls),
        "relation_placement_heuristic_hit_probability": None,
        "measured_natural_relations": None,
        "complete_solve_work_log2": None,
        "preferred_spill_root": "/Volumes/SSD990/llm/tmp",
        "minimum_spill_volume_free_bytes_before_launch": 8 << 30,
        "minimum_system_free_memory_bytes_before_launch": 24 << 30,
        "launch_gates": [
            "Q1074 has a terminal receipt and independent checked-Sage audit with zero exact hits and no verified target DLP.",
            "All eight Q1081 jobs have terminal archived receipts and independent checked-Sage audits with zero exact hits and no verified target DLP.",
            "Rebuild the coverage ledger; reject any verified DLP, unresolved exact hit, or overlap with a completed or active full-size interval.",
            "Freeze a source-bound executable plan only after reviewing Q1074 measured wall time, peak memory, and disk use against the M32 alternative.",
            "Check physical ARM backend, available memory, and at least 8 GiB free on the selected spill volume before launch.",
            "Save checked Sage --runtime-info outside the measured interval and launch the job through /Volumes/SSD990/cryptanalysis/sage."
        ],
        "limits": [
            "This reserves a disjoint interval; it is neither a frozen executable plan nor a dispatched run.",
            "Field calls exclude keying, Bloom, memory, disk, failed work, setup, and scalar replay.",
            "Hit probability and complete-solve work remain unknown until terminal audits and a refreshed coverage screen."
        ],
        "Q1074_plan_sha256": sha(Q1074),
        "Q1081_plan_sha256": sha(Q1081),
        "Q1083_design_sha256": sha(Q1083),
        "coverage_ledger_sha256_at_design": sha(LEDGER),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"proposal_id": "Q1084", "query_start": start,
                      "query_end_exclusive": end,
                      "modeled_native_field_calls_log2": math.log2(calls)}))


if __name__ == "__main__":
    main()
