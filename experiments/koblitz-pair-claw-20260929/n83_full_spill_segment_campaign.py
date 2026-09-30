#!/usr/bin/env python3
"""Advance one guarded R27 segment of the frozen Q1062 M31 table search.

Eight terminal R27 segments cover one R30 query range. The existing Q1062
runner and native kernel are unchanged; every segment rebuilds the table and
gets its own receipt. The interrupted R30 attempt is charged separately.
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import n83_full_spill_campaign as full
import n83_full_spill_segment_work as segment_work
import n83_full_spill_work as work
from n83_identity_contract import validate_receipt, validate_reference

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
SCREEN = HERE / "n83_full_spill_screen.json"
SEGMENT_REPS = 1 << 27
SEGMENTS_PER_RANGE = full.R // SEGMENT_REPS


def plan():
    for range_index in range(1, 118):
        for segment in range(SEGMENTS_PER_RANGE):
            query_start = range_index * full.R + segment * SEGMENT_REPS
            name = ("n83_full_spill_k48194_chunk_M31_R27_tstart0_"
                    f"qstart{query_start}_b20_h10_rb8.json")
            yield {"range_index": range_index, "segment": segment,
                   "query_start": query_start, "receipt": RUNS / name}


def inspect(screen, completed_full_ranges, completed_other_segments):
    completed, failed, active, missing, solved, unverified = [], [], [], [], [], []
    for chunk in plan():
        attempt = 0
        failed_this_segment = False
        while True:
            path = full.attempt_path(chunk, attempt)
            marker = path.with_suffix(".started.json")
            if not path.exists() and not marker.exists():
                if (chunk["range_index"] not in completed_full_ranges and
                        chunk["query_start"] not in completed_other_segments):
                    missing.append(dict(chunk, receipt=path,
                                        needs_retry=attempt > 0))
                break
            if marker.exists() and not path.exists():
                active.append(path)
                break
            if marker.exists():
                raise ValueError(f"terminal segment retains start marker: {path}")
            row = json.loads(path.read_text())
            validate_receipt(screen, row)
            assert row["proposal_id"] == "Q1062"
            assert row["native_source_sha256"] == screen[
                "native_source_sha256"]
            assert row["native_pairs_sha256"] == screen[
                "native_pairs_sha256"]
            assert row["bloom_core_sha256"] == screen[
                "bloom_core_sha256"]
            assert row["table_start"] == 0
            assert row["table_descriptors"] == full.M
            assert row["query_start"] == chunk["query_start"]
            assert row["query_representatives"] == SEGMENT_REPS
            assert row["query_workers"] == 14
            assert row["representative_batch"] == 8
            assert row["bits_per_key"] == 20 and row["hashes"] == 10
            assert row["fast_keyer_enabled"] and row[
                "candidate_spill_enabled"]
            if row["kind"] == (
                    "n83_public_target_signed_x_query_k48194_chunk_failed"):
                assert row["native_phase_counts"] is None
                failed.append(path)
                failed_this_segment = True
            elif row["kind"] == (
                    "n83_public_target_signed_x_query_k48194_exact_replay_chunk"):
                assert attempt == 0 or failed_this_segment, (
                    "retry lacks failed attempt")
                completed.append(path)
                if row["verified_public_target_quotient_table_dlp"]:
                    solved.append(path)
                elif row["native_result"]["exact_hit_queries"]:
                    unverified.append(path)
                break
            else:
                raise ValueError(f"unexpected segment receipt: {path}")
            attempt += 1
    return completed, failed, active, missing, solved, unverified


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-next", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--acknowledge-failed-full-range", action="store_true")
    parser.add_argument("--spill-dir", type=Path, default=full.SPILL_DIR)
    args = parser.parse_args()
    assert args.spill_dir.is_absolute() and args.spill_dir.is_dir()
    screen = json.loads(SCREEN.read_text())
    validate_reference(screen)
    assert full.sha(full.RUNNER) == screen["runner_source_sha256"]
    assert full.sha(HERE / "native_n83_orbit_query_spill.cpp") == screen[
        "native_source_sha256"]
    assert full.sha(HERE / "native_n83_pairs.cpp") == screen[
        "native_pairs_sha256"]
    assert full.sha(HERE / "native_n83_bloom_core.hpp") == screen[
        "bloom_core_sha256"]
    full_done, full_failed, full_active, _, full_solved = full.inspect(screen)
    full_ranges = {json.loads(path.read_text())["query_start"] // full.R
                   for path in full_done}
    q1061_ci, failed_q1061_ci, incomplete_q1061_ci = (
        segment_work.portable_ci_rows(screen))
    portable_done = {row["query_start"] for _, row in q1061_ci}
    completed, failed, active, missing, solved, unverified = inspect(
        screen, full_ranges, portable_done)
    full_unverified = [path for path in full_done if
                       json.loads(path.read_text())["native_result"][
                           "exact_hit_queries"] and path not in full_solved]
    markers = sorted(str(path) for path in RUNS.glob("n83_*.started.json"))
    free = shutil.disk_usage("/").free
    spill_free = shutil.disk_usage(args.spill_dir).free
    swap = full.swapouts()
    next_chunk = missing[0] if missing else None
    q1060_rows, _ = work.load_terminal_rows(
        "n83_spill_lowmem_k48194_chunk_M28_R30_tstart*_qstart*_b20_h10_rb8*.json",
        "Q1060", screen)
    other_solved = [str(path) for path, row in q1060_rows if
                    row["verified_public_target_quotient_table_dlp"]]
    other_unverified = [str(path) for path, row in q1060_rows if
                        row["native_result"]["exact_hit_queries"] and not
                        row["verified_public_target_quotient_table_dlp"]]
    for path, row in q1061_ci:
        if row["native_result"]["exact_hit_queries"]:
            sage_path = path.with_name("sage_verify.json")
            if sage_path.exists():
                sage = json.loads(sage_path.read_text())
                assert sage["receipt_sha256"] == full.sha(path)
                assert sage["natural_public_target_relation_verified"]
                other_solved.append(str(path))
            else:
                other_unverified.append(str(path))
    print(json.dumps({
        "proposal_id": "Q1062", "candidate_id": None,
        "query_shape": "M31_R27_eight_segments_per_R30_range",
        "curve_id": screen["curve_id"],
        "factor_base_enumerated_set_sha256": screen["factor_base"][
            "enumerated_set_sha256"],
        "completed_segments": len(completed),
        "completed_portable_ci_segments": len(q1061_ci),
        "failed_segments_with_unknown_field_calls": len(failed),
        "failed_portable_ci_segments_with_unknown_field_calls": len(
            failed_q1061_ci),
        "incomplete_portable_ci_bundles": len(incomplete_q1061_ci),
        "active_segments": len(active),
        "remaining_segments": len(missing),
        "failed_full_ranges_with_unknown_field_calls": len(full_failed),
        "active_full_ranges": len(full_active),
        "verified_dlp_receipts": [str(path) for path in solved + full_solved],
        "unverified_exact_hit_receipts": ([str(path) for path in
                                           unverified + full_unverified] +
                                          other_unverified),
        "other_variant_verified_dlp_receipts": other_solved,
        "competing_start_markers": markers,
        "next_query_start": next_chunk["query_start"] if next_chunk else None,
        "next_needs_explicit_retry": next_chunk["needs_retry"]
        if next_chunk else None,
        "system_free_bytes": free,
        "minimum_system_free_bytes": full.MIN_SYSTEM_FREE,
        "stop_system_free_bytes": full.STOP_SYSTEM_FREE,
        "spill_volume_free_bytes": spill_free,
        "swapouts_pages": swap,
    }), flush=True)
    if not args.run_next:
        return
    if markers:
        raise RuntimeError("another n=83 search marker exists")
    if solved or full_solved or other_solved:
        raise RuntimeError("a verified n=83 quotient-table DLP already exists")
    if unverified or full_unverified or other_unverified:
        raise RuntimeError("an unverified exact hit requires review")
    if full_failed and not args.acknowledge_failed_full_range:
        raise RuntimeError("failed full range has unknown work; acknowledge it")
    if not next_chunk:
        raise RuntimeError("segmented Q1062 plan exhausted")
    if next_chunk["needs_retry"] and not args.retry_failed:
        raise RuntimeError("failed segment has unknown work; use --retry-failed")
    if free < full.MIN_SYSTEM_FREE or spill_free < full.MIN_SPILL_FREE:
        raise RuntimeError("system or spill volume lacks full-filter headroom")
    time.sleep(30)
    ready_free = shutil.disk_usage("/").free
    ready_spill = shutil.disk_usage(args.spill_dir).free
    ready_swap = full.swapouts()
    if (ready_free < full.MIN_SYSTEM_FREE or
            ready_spill < full.MIN_SPILL_FREE or
            ready_swap - swap > full.MAX_PREFLIGHT_SWAPOUT_PAGES or
            list(RUNS.glob("n83_*.started.json"))):
        raise RuntimeError("segment preflight resource or exclusivity check failed")
    path = next_chunk["receipt"]
    runtime_path = path.with_suffix(".runtime.json")
    runtime = subprocess.run([str(full.SAGE), "--runtime-info"], check=True,
                             capture_output=True, text=True).stdout
    runtime_path.write_text(runtime)
    assert json.loads(runtime)["status"] == "verified"
    if list(RUNS.glob("n83_*.started.json")):
        raise RuntimeError("another n=83 search started before launch")
    command = [
        str(full.SAGE), "-python", str(full.RUNNER),
        "--proposal-id", "Q1062",
        "--table-log2", "31", "--table-start", "0",
        "--query-reps-log2", "27", "--query-start",
        str(next_chunk["query_start"]),
        "--workers", "14", "--rep-batch", "8",
        "--bits-per-key", "20", "--hashes", "10",
        "--fast-keyer", "--spill-dir", str(args.spill_dir),
        "--runtime-info", str(runtime_path), "--out", str(path),
    ]
    child = subprocess.Popen(command, start_new_session=True)
    while child.poll() is None:
        time.sleep(15)
        current_free = shutil.disk_usage("/").free
        current_spill = shutil.disk_usage(args.spill_dir).free
        current_swap = full.swapouts()
        reason = ("system_volume" if current_free < full.STOP_SYSTEM_FREE else
                  "spill_volume" if current_spill < full.STOP_SPILL_FREE else
                  "swap_growth" if current_swap - ready_swap >
                  full.MAX_RUNNING_SWAPOUT_PAGES else None)
        if reason and child.poll() is None:
            os.killpg(child.pid, signal.SIGINT)
            child.wait()
            full.write_guard(next_chunk, reason=reason,
                             before_swap=ready_swap, after_swap=current_swap,
                             before_free=ready_free, after_free=current_free)
            raise RuntimeError(f"guard interrupted R27 segment: {reason}")
    if child.returncode:
        raise subprocess.CalledProcessError(child.returncode, command)
    row = json.loads(path.read_text())
    validate_receipt(screen, row)
    assert row["query_representatives"] == SEGMENT_REPS
    assert not path.with_suffix(".started.json").exists()


if __name__ == "__main__":
    main()
