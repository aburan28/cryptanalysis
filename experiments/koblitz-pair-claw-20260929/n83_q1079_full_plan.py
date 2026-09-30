#!/usr/bin/env python3
"""Freeze the next full-size Q1079 rectangles after terminal prior audits."""

import argparse
import hashlib
import json
import math
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
SCREEN = HERE / "n83_full_spill_screen.json"
DESIGN = HERE / "n83_m32_wave_q1077_design.json"
Q1075 = HERE / "n83_m32_wave_q1075_plan.json"
LEDGER = HERE / "n83_full_spill_segment_work.json"
OUTPUT = HERE / "n83_q1079_m32_wave_plan.json"
sys.path.insert(0, str(HERE))
from bench_n83_zero_run_stage import FROZEN, generated_sources  # noqa: E402
from n83_identity_contract import validate_receipt, validate_reference  # noqa: E402
from n83_full_spill_screen import field_calls  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def terminal_zero(screen, receipt, sage_path, *, start, descriptors, reps):
    assert receipt.is_file(), f"terminal receipt missing: {receipt}"
    assert sage_path.is_file(), f"independent checked-Sage audit missing: {sage_path}"
    assert not receipt.with_suffix(".started.json").exists(), (
        f"active start marker remains for terminal receipt: {receipt}")
    row = json.loads(receipt.read_text())
    sage = json.loads(sage_path.read_text())
    validate_receipt(screen, row)
    assert row["kind"] == "n83_public_target_signed_x_query_k48194_exact_replay_chunk"
    assert row["proposal_id"] == "Q1061"
    assert row["table_start"] == 0 and row["table_descriptors"] == descriptors
    assert row["query_start"] == start and row["query_representatives"] == reps
    assert row["native_result"]["exact_hit_queries"] == 0
    assert not row["verified_public_target_quotient_table_dlp"]
    assert not row["verified_public_target_relations"]
    assert sage["receipt_sha256"] == sha(receipt)
    assert sage["curve_id"] == screen["curve_id"]
    assert sage["verified_relation_count"] == 0
    assert not sage["natural_public_target_relation_verified"]
    return {"receipt": str(receipt.relative_to(HERE)),
            "receipt_sha256": sha(receipt),
            "sage_audit": str(sage_path.relative_to(HERE)),
            "sage_audit_sha256": sha(sage_path)}


def freeze():
    screen = json.loads(SCREEN.read_text())
    design = json.loads(DESIGN.read_text())
    q1075 = json.loads(Q1075.read_text())
    validate_reference(screen)
    assert design["proposal_id"] == "Q1077"
    assert design["status"] == "design_waiting_for_Q1073_and_Q1075_terminal_audits"
    assert design["curve_id"] == screen["curve_id"]
    assert design["isogeny"] == "none"
    assert design["factor_base_enumerated_set_sha256"] == screen[
        "factor_base"]["enumerated_set_sha256"]
    assert q1075["proposal_id"] == "Q1075"
    assert q1075["query_end_exclusive"] == design["query_starts"][0]
    assert len(design["query_starts"]) == 8
    m = design["table_descriptors"]
    r = design["query_representatives"]
    assert m == 1 << 32 and r == 1 << 29
    assert design["query_starts"] == [design["query_starts"][0] + i * r
                                      for i in range(8)]
    assert design["query_end_exclusive"] == design["query_starts"][-1] + r
    assert design["cpu_backend"] == "x86_pclmul"
    # An independently audited hit, including a single unresolved exact
    # native hit, closes this dispatch path until reviewed.
    q1073 = terminal_zero(
        screen, RUNS / "n83_local_arm_m33_q1073_retry2.json",
        RUNS / "n83_local_arm_m33_q1073_retry2_sage_verify.json",
        start=12348030976, descriptors=1 << 33, reps=r)
    assert not list(RUNS.glob("*q1074*")), (
        "Q1074 has run files; adjudicate its terminal status before freezing Q1079")
    audited = [q1073]
    q1075_receipts = []
    for start in q1075["query_starts"]:
        matches = list(RUNS.glob(
            f"n83_portable_q1075_M32_R29_ci_*_qstart{start}/bundle.json"))
        assert len(matches) == 1, f"expected one Q1075 terminal bundle at {start}"
        bundle_path = matches[0]
        bundle = json.loads(bundle_path.read_text())
        assert bundle["proposal_id"] == "Q1075"
        assert bundle["status"] == "completed_zero_hit"
        assert bundle["curve_id"] == screen["curve_id"]
        assert bundle["query_start"] == start
        assert bundle["plan_sha256"] == sha(Q1075)
        receipt = bundle_path.parent / "full.json"
        sage_path = bundle_path.parent / "sage_verify.json"
        assert bundle["artifact_sha256"]["full.json"] == sha(receipt)
        item = terminal_zero(screen, receipt, sage_path,
                             start=start, descriptors=m, reps=r)
        item["bundle"] = str(bundle_path.relative_to(HERE))
        item["bundle_sha256"] = sha(bundle_path)
        q1075_receipts.append(item)
    audited.extend(q1075_receipts)
    ledger = json.loads(LEDGER.read_text())
    assert ledger["curve_id"] == screen["curve_id"]
    assert ledger["isogeny"] == "none"
    assert ledger["complete_solve_work_log2"] is None
    assert not ledger["verified_quotient_table_dlp_receipts"]
    assert not ledger["unverified_exact_hit_receipts"]
    completed = {row["path"] for row in ledger["completed_receipts"]}
    assert all(item["receipt"].startswith("runs/") and
               f"experiments/koblitz-pair-claw-20260929/{item['receipt']}" in
               completed for item in audited), (
                   "regenerate coverage ledger from all terminal Sage-audited receipts")
    assert not any("q1073_retry2" in marker or "q1075" in marker for marker in
                   ledger["active_start_markers_excluded"])
    # The Q1080 partial rectangle starts after these eight intervals and
    # does not alter the Q1062 R27-grid coverage used by this plan.
    q1080 = HERE / "n83_q1080_m28_r24_paired_plan.json"
    q1080_plan = json.loads(q1080.read_text())
    assert q1080_plan["query_start"] == design["query_end_exclusive"]
    q1080_audit_path = RUNS / "n83_q1080_x86_ci_36770585105/audit.json"
    assert q1080_audit_path.is_file(), (
        "Q1080 must have a terminal independent audit before Q1079 dispatch")
    q1080_audit = json.loads(q1080_audit_path.read_text())
    assert q1080_audit["proposal_id"] == "Q1080"
    assert q1080_audit["curve_id"] == screen["curve_id"]
    assert q1080_audit["factor_base_enumerated_set_sha256"] == screen[
        "factor_base"]["enumerated_set_sha256"]
    assert q1080_audit["plan_sha256"] == sha(q1080)
    assert q1080_audit["exact_hit_queries"] == 0
    assert not q1080_audit["natural_public_target_relation_verified"]
    assert all(sha(path) == digest for path, digest in FROZEN.items())
    with tempfile.TemporaryDirectory() as temp:
        pairs, core, native = generated_sources(Path(temp))
        generated_hashes = {
            "zero_run_pairs_source_sha256": sha(pairs),
            "zero_run_core_source_sha256": sha(core),
            "zero_run_native_source_sha256": sha(native),
        }
    field_header = HERE.parents[1] / "ecc2k130/runner/generated/eccF83.h"
    per_job = field_calls(m, r)
    result = {
        "kind": "n83_q1079_source_bound_eight_job_M32_R29_zero_run_plan",
        "proposal_id": "Q1079", "status": "ready_for_dispatch",
        "candidate_id": None, "run_id": None,
        "curve_id": screen["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": screen[
            "factor_base"]["enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": screen[
            "factor_base"]["actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": screen[
            "factor_base"]["signed_frobenius_columns"],
        "public_target": screen["public_target"], "target_count": 1,
        "table_start": design["table_start"], "table_descriptors": m,
        "query_starts": design["query_starts"],
        "query_representatives": r,
        "query_end_exclusive": design["query_end_exclusive"],
        "cpu_backend": "x86_pclmul",
        "workers": design["query_workers"],
        "representative_batch": design["representative_batch"],
        "bits_per_key": design["bits_per_key"],
        "hashes": design["hashes"],
        "minimum_mem_available_bytes": design["minimum_mem_available_bytes"],
        "minimum_root_free_bytes": design["minimum_root_free_bytes"],
        "minimum_spill_free_bytes": design["minimum_root_free_bytes"],
        "timeout_seconds_per_job": design["timeout_seconds_per_job"],
        "modeled_native_field_calls_per_job": str(per_job),
        "modeled_native_field_calls_eight_jobs_log2": math.log2(8 * per_job),
        "measured_natural_relations": None,
        "measured_complete_solve_work_log2": None,
        "terminal_prior_audits": audited,
        "Q1077_design_sha256": sha(DESIGN),
        "Q1075_plan_sha256": sha(Q1075),
        "Q1080_plan_sha256": sha(q1080),
        "Q1080_terminal_audit_path": str(q1080_audit_path.relative_to(HERE)),
        "Q1080_terminal_audit_sha256": sha(q1080_audit_path),
        "coverage_ledger_sha256": sha(LEDGER),
        "screen_sha256": sha(SCREEN),
        "runner_source_sha256": sha(HERE / "run_n83_zero_run_chunk.py"),
        "source_generator_sha256": sha(HERE / "bench_n83_zero_run_stage.py"),
        "portable_native_source_sha256": sha(HERE /
                                                "native_n83_orbit_query_spill_portable.cpp"),
        "portable_core_source_sha256": sha(HERE /
                                              "native_n83_bloom_core_portable.hpp"),
        "portable_pairs_source_sha256": sha(HERE /
                                               "native_n83_pairs_portable.cpp"),
        "generated_field_sha256": sha(field_header),
        **generated_hashes,
        "source_sha256": sha(Path(__file__)),
        "limits": [
            "This is a source-bound search dispatch, not measured natural yield or a complete DLP.",
            "Field calls omit keying, Bloom, memory, disk, setup, and scalar replay.",
            "Each exact hit must pass independent checked-Sage replay before any DLP or work claim.",
        ],
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    assert not args.out.exists(), "refusing to overwrite frozen Q1079 plan"
    result = freeze()
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"proposal_id": "Q1079", "plan": str(args.out),
                      "prior_audits": len(result["terminal_prior_audits"]),
                      "eight_job_field_calls_log2": result[
                          "modeled_native_field_calls_eight_jobs_log2"]}))


if __name__ == "__main__":
    main()
