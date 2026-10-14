#!/usr/bin/env python3
"""Advance bounded Q1062 ranges sequentially, preserving every terminal row.

The one-range campaign remains the authority for resource and exclusivity
guards. This supervisor never retries a failed range, removes a start marker,
or treats an exact but unverified hit as a solved discrete logarithm.
"""

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from n83_full_spill_campaign import (RUNS, SAGE, SCREEN, inspect,
                                     q1060_solved)
from n83_identity_contract import validate_receipt, validate_reference

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE / "n83_full_spill_campaign.py"
EXACT_KIND = "n83_public_target_signed_x_query_k48194_exact_replay_chunk"


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_report(path, report):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    os.replace(temporary, path)


def state(screen):
    completed, failed, active, missing, solved = inspect(screen)
    competing = sorted(str(path) for path in RUNS.glob("n83_*.started.json")
                       if path not in {p.with_suffix(".started.json")
                                       for p in active})
    return {
        "completed_full_ranges": len(completed),
        "failed_attempts_with_unknown_work": [str(p) for p in failed],
        "active_full_ranges": [str(p) for p in active],
        "competing_start_markers": competing,
        "remaining_full_ranges": len(missing),
        "next_receipt": str(missing[0]["receipt"]) if missing else None,
        "next_needs_explicit_retry": missing[0]["needs_retry"] if missing else None,
        "verified_dlp_receipts": [str(p) for p in solved],
        "other_variant_verified_dlp_receipts": q1060_solved(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true",
                        help="advance up to --max-ranges; default is read-only")
    parser.add_argument("--max-ranges", type=int, default=1)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    assert 1 <= args.max_ranges <= 117
    screen = json.loads(SCREEN.read_text())
    validate_reference(screen)
    assert screen["proposal_id"] == "Q1062"
    initial = state(screen)
    print(json.dumps({"proposal_id": "Q1062", "candidate_id": None,
                      "curve_id": screen["curve_id"], "isogeny": "none",
                      **initial}), flush=True)
    if not args.run:
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = args.report or RUNS / f"n83_full_spill_supervisor_{stamp}_{os.getpid()}.json"
    assert report_path.is_absolute() or report_path.parent == RUNS
    report_path = report_path.resolve()
    assert report_path.parent == RUNS.resolve(), "report must live in runs/"
    assert not report_path.exists(), "refusing to overwrite supervisor report"
    log_path = report_path.with_suffix(".log")
    assert not log_path.exists(), "refusing to overwrite supervisor log"
    report = {
        "kind": "n83_q1062_guarded_sequential_supervisor",
        "proposal_id": "Q1062", "candidate_id": None, "run_id": None,
        "curve_id": screen["curve_id"], "isogeny": "none",
        "curve_identity_record": screen["curve_identity_record"],
        "factor_base_enumerated_set_sha256": screen["factor_base"][
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": screen["factor_base"][
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": screen["factor_base"][
            "signed_frobenius_columns"],
        "public_target": screen["public_target"],
        "max_ranges": args.max_ranges,
        "started_at_utc": now(),
        "initial_state": initial,
        "ranges": [],
        "outcome": "running",
        "supervisor_source_sha256": sha(Path(__file__)),
        "campaign_source_sha256": sha(CAMPAIGN),
        "identity_contract_source_sha256": sha(HERE / "n83_identity_contract.py"),
        "screen_sha256": sha(SCREEN),
        "log_path": str(log_path),
    }
    write_report(report_path, report)
    print(json.dumps({"supervisor_report": str(report_path),
                      "supervisor_log": str(log_path)}), flush=True)
    try:
        for _ in range(args.max_ranges):
            assert sha(CAMPAIGN) == report["campaign_source_sha256"]
            assert sha(SCREEN) == report["screen_sha256"]
            assert sha(HERE / "n83_identity_contract.py") == report[
                "identity_contract_source_sha256"]
            before = state(screen)
            if before["verified_dlp_receipts"] or before[
                    "other_variant_verified_dlp_receipts"]:
                report["outcome"] = "verified_dlp_already_present"
                break
            if before["next_needs_explicit_retry"]:
                report["outcome"] = "failed_attempt_requires_explicit_review"
                break
            if before["active_full_ranges"] or before["competing_start_markers"]:
                report["outcome"] = "another_n83_search_is_active"
                break
            if not before["next_receipt"]:
                report["outcome"] = "finite_range_plan_exhausted"
                break
            destination = Path(before["next_receipt"])
            command = [str(SAGE), "-python", str(CAMPAIGN), "--run-next"]
            entry = {"receipt": str(destination), "started_at_utc": now(),
                     "campaign_command": command,
                     "campaign_returncode": None, "terminal_receipt_sha256": None}
            report["ranges"].append(entry)
            write_report(report_path, report)
            with log_path.open("a") as log:
                child = subprocess.Popen(command, cwd=HERE.parents[1],
                                         stdout=log, stderr=subprocess.STDOUT,
                                         start_new_session=True)
                entry["campaign_pid"] = child.pid
                write_report(report_path, report)
                entry["campaign_returncode"] = child.wait()
            entry["finished_at_utc"] = now()
            entry["terminal_receipt_sha256"] = (
                sha(destination) if destination.exists() else None)
            write_report(report_path, report)
            if entry["campaign_returncode"]:
                report["outcome"] = "campaign_refused_or_failed"
                break
            assert destination.exists(), "campaign returned zero without terminal receipt"
            row = json.loads(destination.read_text())
            validate_receipt(screen, row)
            assert row["proposal_id"] == "Q1062" and row["kind"] == EXACT_KIND
            assert not destination.with_suffix(".started.json").exists()
            entry["exact_hit_queries"] = row["native_result"]["exact_hit_queries"]
            entry["verified_dlp"] = row["verified_public_target_quotient_table_dlp"]
            write_report(report_path, report)
            if entry["verified_dlp"]:
                report["outcome"] = "verified_quotient_table_dlp"
                break
            if entry["exact_hit_queries"]:
                report["outcome"] = "unverified_exact_hit_requires_review"
                break
        else:
            report["outcome"] = "max_ranges_completed_without_hit"
    except KeyboardInterrupt:
        report["outcome"] = "supervisor_interrupted_child_may_continue"
    except BaseException as exc:
        report["outcome"] = "supervisor_error_requires_review"
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        report["finished_at_utc"] = now()
        try:
            report["final_state"] = state(screen)
        except BaseException as exc:
            report["final_state_error"] = f"{type(exc).__name__}: {exc}"
        write_report(report_path, report)
        print(json.dumps({"supervisor_report": str(report_path),
                          "outcome": report["outcome"],
                          "completed_this_session": sum(
                              item.get("campaign_returncode") == 0
                              for item in report["ranges"])}), flush=True)


if __name__ == "__main__":
    main()
