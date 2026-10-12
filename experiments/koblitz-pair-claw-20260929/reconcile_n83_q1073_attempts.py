#!/usr/bin/env python3
"""Archive Q1073 attempt 1's stale marker after audited same-range retry."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
MARKER = RUNS / "n83_local_arm_m33_q1073.started.json"
INTERRUPTED = RUNS / "n83_local_arm_m33_q1073_interrupted.json"
RETRY = RUNS / "n83_local_arm_m33_q1073_retry2.json"
SAGE_VERIFY = RUNS / "n83_local_arm_m33_q1073_retry2_sage_verify.json"
TERMINAL_AUDIT = RUNS / "n83_local_arm_m33_q1073_retry2_terminal_audit.json"
RETRY_PREFLIGHT = RUNS / "n83_local_arm_m33_q1073_retry2_preflight.json"
RETRY_RUNTIME = RUNS / "n83_local_arm_m33_q1073_retry2_runtime_info.json"
Q1074_PLAN = HERE / "n83_local_arm_m33_r30_q1074_plan.json"
Q1074_PREFLIGHT = RUNS / "n83_local_arm_m33_r30_q1074_preflight.json"
Q1074_MARKER = RUNS / "n83_local_arm_m33_r30_q1074.started.json"
Q1074_TERMINAL = RUNS / "n83_local_arm_m33_r30_q1074.json"
LEDGER = HERE / "n83_full_spill_segment_work.json"
ARCHIVE_DIR = RUNS / "reconciled_start_markers"
ARCHIVE_MARKER = ARCHIVE_DIR / "n83_local_arm_m33_q1073.started.json"
PENDING = RUNS / ".n83_local_arm_m33_q1073_attempt_reconciliation.pending.json"
FINAL = RUNS / "n83_local_arm_m33_q1073_attempt_reconciliation.json"
Q1074_BINARY = Path("/private/tmp/n83-q1074-r30-bin/ecc2k83-m33")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def open_pids(path: Path) -> list[int]:
    result = subprocess.run(["lsof", "-t", str(path)], capture_output=True,
                            text=True, check=False)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"lsof failed for {path}: {result.stderr[-500:]}")
    return sorted({int(line) for line in result.stdout.splitlines() if line})


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, path)


def validate_inputs() -> dict:
    for path in (MARKER, INTERRUPTED, RETRY, SAGE_VERIFY, TERMINAL_AUDIT,
                 RETRY_PREFLIGHT, RETRY_RUNTIME, Q1074_PLAN, Q1074_PREFLIGHT,
                 Q1074_MARKER, LEDGER):
        if not path.is_file():
            raise FileNotFoundError(path)
    if Q1074_TERMINAL.exists():
        raise RuntimeError("Q1074 became terminal; refresh the handoff snapshot")
    if (RETRY.with_suffix(".started.json")).exists():
        raise RuntimeError("Q1073 retry 2 still has a start marker")
    if FINAL.exists() or PENDING.exists() or ARCHIVE_MARKER.exists():
        raise FileExistsError("a Q1073 reconciliation artifact already exists")
    if open_pids(MARKER):
        raise RuntimeError("Q1073 attempt 1 marker is still open by a process")

    marker = read(MARKER)
    interrupted = read(INTERRUPTED)
    retry = read(RETRY)
    sage = read(SAGE_VERIFY)
    audit = read(TERMINAL_AUDIT)
    retry_preflight = read(RETRY_PREFLIGHT)
    retry_runtime = read(RETRY_RUNTIME)
    plan = read(Q1074_PLAN)
    q1074_preflight = read(Q1074_PREFLIGHT)
    q1074_marker = read(Q1074_MARKER)
    ledger = read(LEDGER)

    marker_digest = sha(MARKER)
    retry_digest = sha(RETRY)
    sage_digest = sha(SAGE_VERIFY)
    audit_digest = sha(TERMINAL_AUDIT)
    interrupted_digest = sha(INTERRUPTED)
    assert marker_digest == interrupted["start_marker_sha256"]
    assert interrupted["attempt_number"] == 1
    assert interrupted["status"] == "interrupted_no_terminal_search_receipt"
    assert interrupted["terminal_receipt_present"] is False
    assert interrupted["native_phase_counts"] is None
    assert interrupted["native_field_calls"] is None
    assert interrupted["exact_hit_queries"] is None
    assert interrupted["coverage_credited"] is False

    for row in (marker, interrupted, retry, audit, sage):
        assert row["curve_id"] == "EC1N83Ckb1h876c2921cb64"
        assert row.get("candidate_id") is None
        assert row.get("run_id") is None
    assert retry["kind"] == "n83_public_target_signed_x_query_k48194_exact_replay_chunk"
    assert retry["proposal_id"] == "Q1061"
    assert retry["query_start"] == interrupted["query_start"]
    assert retry["query_representatives"] == interrupted["query_representatives"]
    assert retry["table_start"] == interrupted["table_start"]
    assert retry["table_descriptors"] == interrupted["table_descriptors"]
    assert retry["public_target"] == interrupted["public_target"]
    assert retry["factor_base"]["enumerated_set_sha256"] == interrupted[
        "factor_base_enumerated_set_sha256"]
    assert retry["native_result"]["exact_hit_queries"] == 0
    assert retry["verified_public_target_quotient_table_dlp"] is False
    assert audit["status"] == "terminal_zero_hit_independent_sage_audited"
    assert audit["receipt_sha256"] == retry_digest
    assert audit["sage_verify_sha256"] == sage_digest
    assert audit["native_exact_hit_queries"] == 0
    assert audit["sage_verified_relation_count"] == 0
    assert audit["natural_public_target_relation_verified"] is False
    assert sage["receipt_sha256"] == retry_digest
    assert sage["verified_relation_count"] == 0
    assert sage["natural_public_target_relation_verified"] is False
    assert retry["sage_runtime_info_sha256"] == sha(RETRY_RUNTIME)
    assert retry_preflight["prior_interrupted_attempt_sha256"] == interrupted_digest
    assert retry_preflight["plan_sha256"] == sha(
        HERE / "n83_local_arm_m33_q1073_plan.json")
    assert retry_runtime["status"] == "verified"

    assert plan["proposal_id"] == "Q1074"
    assert plan["candidate_id"] is None and plan["run_id"] is None
    assert plan["query_start"] == (
        retry["query_start"] + retry["query_representatives"])
    assert q1074_preflight["status"] == "passed_before_launch"
    assert q1074_preflight["Q1073_receipt_sha256"] == retry_digest
    assert q1074_preflight["Q1073_audit_sha256"] == sage_digest
    assert q1074_preflight["Q1073_interruption_sha256"] == interrupted_digest
    assert q1074_marker["query_start"] == plan["query_start"]

    entries = [entry for entry in ledger["completed_receipts"]
               if entry["path"].endswith("n83_local_arm_m33_q1073_retry2.json")]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["sha256"] == retry_digest
    assert entry["field_calls"] == "823190880256"
    assert entry["new_cells"] == 32
    assert entry["new_M32_extension_cells"] == 32
    assert entry["new_M33_extension_cells"] == 64

    q1074_binary_pids = open_pids(Q1074_BINARY) if Q1074_BINARY.exists() else []
    return {
        "kind": "n83_q1073_attempt1_marker_reconciliation",
        "schema_version": 1,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "proposal_id": "Q1073",
        "executable_proposal_id": "Q1061",
        "candidate_id": None,
        "run_id": None,
        "curve_id": retry["curve_id"],
        "isogeny": "none",
        "factor_base_enumerated_set_sha256": retry[
            "factor_base"]["enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": retry["factor_base"][
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": retry["factor_base"][
            "signed_frobenius_columns"],
        "reconciliation_script_sha256": sha(Path(__file__)),
        "attempt1": {
            "status": interrupted["status"],
            "start_marker_sha256": marker_digest,
            "interruption_receipt_sha256": interrupted_digest,
            "work_counts": "unknown",
            "coverage_credit": 0,
            "unknown_work_preserved": True,
        },
        "attempt2": {
            "terminal_receipt_sha256": retry_digest,
            "terminal_audit_sha256": audit_digest,
            "sage_verification_sha256": sage_digest,
            "query_start": retry["query_start"],
            "query_representatives": retry["query_representatives"],
            "query_end_exclusive": retry["query_start"] + retry[
                "query_representatives"],
            "table_start": retry["table_start"],
            "table_descriptors": retry["table_descriptors"],
            "exact_hit_queries": 0,
            "sage_verified_relation_count": 0,
            "verified_target_dlp": False,
            "coverage_credited_once_from_ledger": {
                "modeled_field_calls": entry["field_calls"],
                "new_primary_cells": entry["new_cells"],
                "new_M32_extension_cells": entry["new_M32_extension_cells"],
                "new_M33_extension_cells": entry["new_M33_extension_cells"],
            },
        },
        "reconciliation": {
            "status": "attempt1_unknown_uncredited_retry2_terminal_zero_audited",
            "rule": "Attempt 2 repeats the entire attempt 1 table/query interval and is bound by an independent checked-Sage zero-relation audit. Count the retry receipt once; retain attempt 1 as unknown with no additional coverage.",
            "marker_archive_path": str(ARCHIVE_MARKER),
            "marker_bytes_preserved": True,
        },
        "concurrent_Q1074_snapshot": {
            "proposal_id": "Q1074",
            "start_marker_sha256": sha(Q1074_MARKER),
            "terminal_receipt_present": False,
            "native_binary_open_pids": q1074_binary_pids,
            "status": "active" if q1074_binary_pids else "unresolved_marker_without_native_handle",
        },
        "input_sha256": {
            "attempt1_start_marker": marker_digest,
            "attempt1_interruption_receipt": interrupted_digest,
            "attempt2_terminal_receipt": retry_digest,
            "attempt2_terminal_audit": audit_digest,
            "attempt2_sage_verification": sage_digest,
            "attempt2_preflight": sha(RETRY_PREFLIGHT),
            "attempt2_runtime_info": sha(RETRY_RUNTIME),
            "Q1074_preflight": sha(Q1074_PREFLIGHT),
            "Q1074_plan": sha(Q1074_PLAN),
            "coverage_ledger": sha(LEDGER),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="write receipt and archive the stale attempt-1 marker")
    args = parser.parse_args()
    receipt = validate_inputs()
    if not args.apply:
        print(json.dumps({"decision": "READY_TO_RECONCILE",
                          "attempt1_coverage_credit": 0,
                          "attempt2_exact_hit_queries": 0,
                          "q1074_native_pids": receipt[
                              "concurrent_Q1074_snapshot"][
                                  "native_binary_open_pids"]}, sort_keys=True))
        return

    ARCHIVE_DIR.mkdir(exist_ok=True)
    pending = dict(receipt)
    pending["reconciliation"]["status"] = "marker_archive_pending"
    atomic_json(PENDING, pending)
    os.replace(MARKER, ARCHIVE_MARKER)
    if sha(ARCHIVE_MARKER) != receipt["attempt1"]["start_marker_sha256"]:
        raise RuntimeError("archived marker digest changed during move")
    receipt["reconciled_at_utc"] = datetime.now(timezone.utc).isoformat()
    receipt["reconciliation"]["status"] = (
        "attempt1_unknown_uncredited_retry2_terminal_zero_audited")
    atomic_json(FINAL, receipt)
    PENDING.unlink()
    print(json.dumps({"decision": "RECONCILED",
                      "receipt": str(FINAL),
                      "archived_marker": str(ARCHIVE_MARKER),
                      "archived_marker_sha256": sha(ARCHIVE_MARKER),
                      "q1074_native_pids": receipt[
                          "concurrent_Q1074_snapshot"][
                              "native_binary_open_pids"]}, sort_keys=True))


if __name__ == "__main__":
    main()
