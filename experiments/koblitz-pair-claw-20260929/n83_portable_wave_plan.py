#!/usr/bin/env python3
"""Freeze the next eight disjoint physical-x86 R29 quotient queries."""

import hashlib
import json
import math
from pathlib import Path

import n83_full_spill_work as work
import n83_portable_ci_ingest as portable
from n83_full_spill_screen import field_calls
from n83_identity_contract import validate_reference

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCREEN = HERE / "n83_full_spill_screen.json"
BASE = HERE / "n83_large_knownlog_base_screen.json"
LEDGER = HERE / "n83_full_spill_segment_work.json"
WORKFLOW = REPO / ".github/workflows/n83-portable-quotient-wave.yml"
SEGMENT_WORKFLOW = REPO / ".github/workflows/n83-portable-quotient-segment.yml"
OUTPUT = HERE / "n83_portable_wave_plan.json"
FIRST_GROUP = (HERE / "runs" /
               "n83_portable_q1061_M31_R29_ci_36669737583")
M31 = 1 << 31
R27 = 1 << 27
R29 = 1 << 29
R30 = 1 << 30
STARTS = tuple(range_index * R30 + half * R29
               for range_index in range(2, 6) for half in range(2))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    screen = json.loads(SCREEN.read_text())
    base = json.loads(BASE.read_text())
    ledger = json.loads(LEDGER.read_text())
    validate_reference(screen)
    assert screen["curve_id"] == base["curve_id"] == ledger["curve_id"]
    assert screen["factor_base"]["enumerated_set_sha256"] == ledger[
        "factor_base_enumerated_set_sha256"]
    assert ledger["verified_quotient_table_dlp_receipts"] == []
    assert ledger["unverified_exact_hit_receipts"] == []
    first_bundle_path = FIRST_GROUP / "bundle.json"
    first_bundle_sha = first_sage_sha = None
    if first_bundle_path.exists():
        bundle = json.loads(first_bundle_path.read_text())
        assert bundle["github_run_id"] == 36669737583
        assert bundle["query_start"] == R30 + R27
        assert bundle["query_representatives"] == R29
        assert bundle["curve_id"] == screen["curve_id"]
        first_bundle_sha = sha(first_bundle_path)
        if bundle["status"] == "completed_zero_hit":
            full_path = FIRST_GROUP / "full.json"
            row = portable.verified_row(
                screen, full_path, full=True, full_query_reps=R29)
            assert row["native_result"]["exact_hit_queries"] == 0
            sage_path = FIRST_GROUP / "sage_verify.json"
            assert sage_path.exists(), "independent Sage zero replay required"
            sage = json.loads(sage_path.read_text())
            assert sage["receipt_sha256"] == sha(full_path)
            assert sage["verified_relation_count"] == 0
            assert sage["natural_public_target_relation_verified"] is False
            first_sage_sha = sha(sage_path)
            status = "ready_after_independent_first_R29_zero_receipt"
        else:
            status = f"hold_after_first_R29_{bundle['status']}"
    else:
        status = "staged_inactive_pending_first_R29_terminal_review"
    assert len(STARTS) == len(set(STARTS)) == 8
    assert all(start >= 2 * R30 and start % R29 == 0 and
               start % R30 + R29 <= R30 for start in STARTS)
    assert STARTS[0] > R30 + R27 + R29
    for receipt in ledger["completed_receipts"]:
        row = json.loads((REPO / receipt["path"]).read_text())
        query_start = row["query_start"]
        query_end = query_start + row["query_representatives"]
        assert all(query_end <= start or start + R29 <= query_start
                   for start in STARTS), receipt["path"]
    workflow = WORKFLOW.read_text()
    assert all(f'"{start}"' in workflow for start in STARTS)
    calls = field_calls(M31, R29)
    coverage_cells = len(STARTS) * (R29 // R27) * 8
    cell_fraction = (
        (1 << 28) / base["zero_pair_key_cap_before_accidental_collisions"]
        * R27 * base["factor_base"]["signed_frobenius_orbit_size"]
        / base["unordered_query_pair_domain"])
    mean = base["heuristic_mean_four_point_multisets"]
    old_intensity = work.intensity(
        ledger["completed_disjoint_M28_by_R27_cells"],
        cell_fraction=cell_fraction, mean=mean)
    new_intensity = work.intensity(
        ledger["completed_disjoint_M28_by_R27_cells"] + coverage_cells,
        cell_fraction=cell_fraction, mean=mean)
    report = {
        "kind": "n83_q1061_physical_x86_grouped_wave_plan",
        "proposal_id": "Q1061", "candidate_id": None, "run_id": None,
        "status": status,
        "curve_id": screen["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": screen["factor_base"][
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": screen[
            "factor_base"]["actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": screen["factor_base"][
            "signed_frobenius_columns"],
        "table_descriptors_per_job": M31,
        "query_representatives_per_job": R29,
        "query_starts": list(STARTS),
        "grouped_jobs": len(STARTS),
        "max_parallel_jobs": 4,
        "new_M28_by_R27_cells_if_all_complete": coverage_cells,
        "modeled_native_field_calls_per_job": str(calls),
        "modeled_native_field_calls_all_jobs": str(len(STARTS) * calls),
        "modeled_native_field_calls_all_jobs_log2": math.log2(
            len(STARTS) * calls),
        "heuristic_hit_probability_conditional_on_archived_zero_hits":
            -math.expm1(-(new_intensity - old_intensity)),
        "pending_first_R29_github_run_id": 36669737583,
        "first_R29_bundle_sha256": first_bundle_sha,
        "first_R29_sage_replay_sha256": first_sage_sha,
        "activation_gate": (
            "Review terminal first-R29 receipt and independent Sage replay; "
            "do not activate if it has a verified or unverified exact hit."),
        "screen_sha256": sha(SCREEN),
        "base_screen_sha256": sha(BASE),
        "coverage_ledger_sha256": sha(LEDGER),
        "workflow_sha256": sha(WORKFLOW),
        "segment_workflow_sha256": sha(SEGMENT_WORKFLOW),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "grouped_jobs": len(STARTS),
        "new_cells": coverage_cells,
        "modeled_field_calls_log2": report[
            "modeled_native_field_calls_all_jobs_log2"],
        "heuristic_hit_probability": report[
            "heuristic_hit_probability_conditional_on_archived_zero_hits"],
        "status": report["status"],
    }), flush=True)


if __name__ == "__main__":
    main()
