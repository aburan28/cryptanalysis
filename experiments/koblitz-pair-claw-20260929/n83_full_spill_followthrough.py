#!/usr/bin/env python3
"""After the first full Q1062 receipt, continue only a validated zero-hit run.

The first full range is a resource and correctness gate. This watcher leaves
an exact hit, a failed attempt, a mismatched identity, or excess peak RSS for
review. Later ranges still use the one-range campaign's resource guards.
"""

import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from n83_full_spill_campaign import SAGE, SCREEN
from n83_identity_contract import validate_receipt, validate_reference

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
FIRST = RUNS / (
    "n83_full_spill_k48194_chunk_M31_R30_tstart0_"
    "qstart1073741824_b20_h10_rb8.json")
REPORT = RUNS / "n83_full_spill_followthrough_from_first.json"
LOG = RUNS / "n83_full_spill_followthrough_from_first.log"
SUPERVISOR = HERE / "n83_full_spill_supervisor.py"
WAIT_SECONDS = 8 * 3600
MAX_FIRST_PEAK_RSS = 10 << 30
EXACT_KIND = "n83_public_target_signed_x_query_k48194_exact_replay_chunk"


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(report):
    temporary = REPORT.with_name(REPORT.name + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    os.replace(temporary, REPORT)


def classify_first(screen, row):
    validate_receipt(screen, row)
    assert row["proposal_id"] == "Q1062"
    assert row["table_start"] == 0
    assert row["table_descriptors"] == 1 << 31
    assert row["query_start"] == 1 << 30
    assert row["query_representatives"] == 1 << 30
    assert row["query_workers"] == 14 and row["representative_batch"] == 8
    assert row["bits_per_key"] == 20 and row["hashes"] == 10
    assert row["native_source_sha256"] == screen["native_source_sha256"]
    assert row["native_pairs_sha256"] == screen["native_pairs_sha256"]
    assert row["bloom_core_sha256"] == screen["bloom_core_sha256"]
    if "wrapper_source_sha256" in row:
        assert row["wrapper_source_sha256"] == screen[
            "runner_source_sha256"]
    if row["kind"] != EXACT_KIND:
        assert row["kind"] == (
            "n83_public_target_signed_x_query_k48194_chunk_failed")
        return "failed_first_range_requires_review"
    native = row["native_result"]
    assert native["table_start"] == row["table_start"]
    assert native["table_descriptors"] == row["table_descriptors"]
    assert native["query_start"] == row["query_start"]
    assert native["query_representatives"] == row["query_representatives"]
    assert native["query_workers"] == row["query_workers"]
    assert native["representative_batch"] == row["representative_batch"]
    assert row["native_field_add_mul_sqr_call_model"] == screen[
        "modeled_field_calls_per_full_range"]
    assert native["candidate_store_mode"] == "unlinked_file"
    assert native["bloom_positive_queries"] == (
        native["false_positive_queries"] + native["exact_hit_queries"])
    assert native["candidate_spill_bytes"] == (
        24 * native["bloom_positive_queries"])
    assert native["peak_rss_bytes"] >= native["bloom_bytes"]
    assert row["native_child_cpu_total_seconds"] > 0
    assert row["wrapper_subprocess_wall_seconds"] > 0
    if row["verified_public_target_quotient_table_dlp"]:
        assert row["verified_public_target_relations"]
        assert native["exact_hit_queries"] > 0
        return "verified_quotient_table_dlp"
    if native["exact_hit_queries"]:
        return "unverified_exact_hit_requires_review"
    if native["peak_rss_bytes"] > MAX_FIRST_PEAK_RSS:
        return "first_range_peak_rss_requires_review"
    return "validated_zero_hit_continue"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait-seconds", type=int, default=WAIT_SECONDS)
    args = parser.parse_args()
    assert 0 < args.wait_seconds <= WAIT_SECONDS
    assert not REPORT.exists() and not LOG.exists(), "handoff already recorded"
    marker = FIRST.with_suffix(".started.json")
    assert marker.exists() or FIRST.exists(), "first Q1062 range not found"
    screen = json.loads(SCREEN.read_text())
    validate_reference(screen)
    screen_sha = sha(SCREEN)
    report = {
        "kind": "n83_q1062_validated_first_range_followthrough",
        "proposal_id": "Q1062", "candidate_id": None, "run_id": None,
        "curve_id": screen["curve_id"], "isogeny": "none",
        "factor_base_enumerated_set_sha256": screen["factor_base"][
            "enumerated_set_sha256"],
        "actual_usable_points_B_before_folding": screen["factor_base"][
            "actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": screen["factor_base"][
            "signed_frobenius_columns"],
        "public_target": screen["public_target"],
        "began_waiting_at_utc": now(),
        "first_receipt": str(FIRST),
        "first_receipt_sha256": None,
        "first_outcome": None,
        "supervisor_launch_attempted": False,
        "supervisor_max_ranges": 116,
        "supervisor_command": None,
        "supervisor_pid": None,
        "supervisor_returncode": None,
        "log_path": str(LOG),
        "Q1062_screen_sha256": screen_sha,
        "followthrough_source_sha256": sha(Path(__file__)),
        "supervisor_source_sha256": sha(SUPERVISOR),
        "identity_contract_source_sha256": sha(
            HERE / "n83_identity_contract.py"),
        "maximum_first_peak_rss_bytes_for_automatic_continuation":
            MAX_FIRST_PEAK_RSS,
    }
    save(report)
    deadline = time.monotonic() + args.wait_seconds
    while not (FIRST.exists() and not marker.exists()):
        if time.monotonic() >= deadline:
            report["outcome"] = "first_range_wait_timeout_not_a_search_result"
            report["finished_at_utc"] = now()
            save(report)
            raise TimeoutError("first Q1062 range did not reach a cleared terminal receipt")
        time.sleep(30)
    assert sha(SCREEN) == screen_sha
    assert sha(SUPERVISOR) == report["supervisor_source_sha256"]
    row = json.loads(FIRST.read_text())
    report["first_receipt_sha256"] = sha(FIRST)
    report["first_outcome"] = classify_first(screen, row)
    report["first_peak_rss_bytes"] = (row.get("native_result") or {}).get(
        "peak_rss_bytes")
    report["first_exact_hit_queries"] = (row.get("native_result") or {}).get(
        "exact_hit_queries")
    save(report)
    if report["first_outcome"] != "validated_zero_hit_continue":
        report["outcome"] = report["first_outcome"]
        report["finished_at_utc"] = now()
        save(report)
        print(json.dumps(report), flush=True)
        return
    command = [str(SAGE), "-python", str(SUPERVISOR), "--run",
               "--max-ranges", "116"]
    report["supervisor_launch_attempted"] = True
    report["supervisor_command"] = command
    report["supervisor_launch_attempted_at_utc"] = now()
    save(report)
    try:
        with LOG.open("x") as log:
            child = subprocess.Popen(command, cwd=HERE.parents[1],
                                     stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            report["supervisor_pid"] = child.pid
            save(report)
            print(json.dumps({"followthrough_report": str(REPORT),
                              "supervisor_pid": child.pid,
                              "supervisor_log": str(LOG)}), flush=True)
            report["supervisor_returncode"] = child.wait()
        report["outcome"] = (
            "supervisor_completed" if report["supervisor_returncode"] == 0
            else "supervisor_failed_requires_review")
    except KeyboardInterrupt:
        report["outcome"] = "watcher_interrupted_supervisor_may_continue"
    finally:
        report["finished_at_utc"] = now()
        save(report)
        print(json.dumps({"followthrough_report": str(REPORT),
                          "outcome": report["outcome"],
                          "supervisor_pid": report["supervisor_pid"]}), flush=True)


if __name__ == "__main__":
    main()
