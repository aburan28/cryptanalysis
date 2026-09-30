#!/usr/bin/env python3
"""Inspect or advance one guarded Q1062 full-filter n=83 rectangle.

The first R30 range was completed under Q1051. Q1062 covers each later
R30 query range with one M31 table filter and SSD-spooled candidates.
Earlier Q1060 shards remain charged historical work, including the
intentional overlap with Q1062's first full range.
"""

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
SCREEN = HERE / "n83_full_spill_screen.json"
RUNNER = HERE / "run_n83_full_spill_chunk.py"
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")
SPILL_DIR = Path("/Volumes/SSD990/llm/tmp")
M = 1 << 31
R = 1 << 30
MIN_SYSTEM_FREE = 12 << 30
STOP_SYSTEM_FREE = 4 << 30
MIN_SPILL_FREE = 1 << 30
STOP_SPILL_FREE = 512 << 20
MAX_PREFLIGHT_SWAPOUT_PAGES = 128
MAX_RUNNING_SWAPOUT_PAGES = 1024


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def swapouts():
    output = subprocess.run(["vm_stat"], check=True, capture_output=True,
                            text=True).stdout
    for line in output.splitlines():
        if line.startswith("Swapouts:"):
            return int(line.split(":", 1)[1].strip().rstrip("."))
    raise RuntimeError("vm_stat omitted Swapouts")


def plan():
    for index in range(1, 118):
        query_start = index * R
        name = ("n83_full_spill_k48194_chunk_M31_R30_tstart0_"
                f"qstart{query_start}_b20_h10_rb8.json")
        yield {"query_start": query_start, "receipt": RUNS / name}


def attempt_path(chunk, attempt):
    path = chunk["receipt"]
    return (path if attempt == 0 else
            path.with_name(f"{path.stem}.retry{attempt}.json"))


def inspect(screen):
    completed, failed, active, missing, solved = [], [], [], [], []
    for chunk in plan():
        success = False
        attempt = 0
        while True:
            path = attempt_path(chunk, attempt)
            marker = path.with_suffix(".started.json")
            if not path.exists() and not marker.exists():
                if not success:
                    missing.append(dict(chunk, receipt=path,
                                        needs_retry=attempt > 0))
                break
            if marker.exists() and not path.exists():
                active.append(path)
                break
            if marker.exists():
                raise ValueError(f"terminal receipt retains start marker: {path}")
            row = json.loads(path.read_text())
            assert row["proposal_id"] == "Q1062"
            assert row["candidate_id"] is None
            assert row["curve_id"] == screen["curve_id"]
            assert row["isogeny"] == "none"
            assert row["public_target"] == screen["public_target"]
            base_digest = (row["factor_base"]["enumerated_set_sha256"]
                           if "factor_base" in row else
                           row["factor_base_enumerated_set_sha256"])
            assert base_digest == screen["factor_base"][
                "enumerated_set_sha256"]
            assert row["native_source_sha256"] == screen[
                "native_source_sha256"]
            assert row["native_pairs_sha256"] == screen[
                "native_pairs_sha256"]
            assert row["bloom_core_sha256"] == screen[
                "bloom_core_sha256"]
            if "wrapper_source_sha256" in row:
                assert row["wrapper_source_sha256"] == screen[
                    "runner_source_sha256"]
            assert row["table_start"] == 0
            assert row["table_descriptors"] == M
            assert row["query_start"] == chunk["query_start"]
            assert row["query_representatives"] == R
            assert row["query_workers"] == 14
            assert row["representative_batch"] == 8
            assert row["bits_per_key"] == 20 and row["hashes"] == 10
            assert row["fast_keyer_enabled"]
            assert row["candidate_spill_enabled"]
            if row["kind"] == (
                    "n83_public_target_signed_x_query_k48194_chunk_failed"):
                assert row["native_phase_counts"] is None
                failed.append(path)
            elif row["kind"] == (
                    "n83_public_target_signed_x_query_k48194_exact_replay_chunk"):
                assert not success, f"multiple successful attempts: {path}"
                assert row["native_result"]["candidate_store_mode"] == (
                    "unlinked_file")
                completed.append(path)
                success = True
                if row["verified_public_target_quotient_table_dlp"]:
                    solved.append(path)
            else:
                raise ValueError(f"unexpected terminal receipt: {path}")
            attempt += 1
    return completed, failed, active, missing, solved


def q1060_solved():
    # Include explicit retry receipts as well as first attempts.
    paths = RUNS.glob("n83_spill_lowmem_k48194_chunk_M28_R30_*.json")
    return [str(path) for path in paths
            if json.loads(path.read_text()).get(
                "verified_public_target_quotient_table_dlp", False)]


def write_guard(chunk, *, reason, before_swap, after_swap,
                before_free, after_free):
    terminal = chunk["receipt"]
    guard = terminal.with_suffix(".guard.json")
    row = {
        "kind": "n83_full_spill_resource_guard_interruption",
        "proposal_id": "Q1062", "candidate_id": None,
        "curve_id": "EC1N83Ckb1h876c2921cb64", "isogeny": "none",
        "query_start": chunk["query_start"], "reason": reason,
        "initial_swapouts_pages": before_swap,
        "final_swapouts_pages": after_swap,
        "initial_system_free_bytes": before_free,
        "final_system_free_bytes": after_free,
        "terminal_receipt_sha256": sha(terminal) if terminal.exists() else None,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "campaign_source_sha256": sha(Path(__file__)),
    }
    guard.write_text(json.dumps(row, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-next", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--spill-dir", type=Path, default=SPILL_DIR)
    args = parser.parse_args()
    assert args.spill_dir.is_absolute() and args.spill_dir.is_dir()
    screen = json.loads(SCREEN.read_text())
    assert screen["proposal_id"] == "Q1062"
    assert screen["candidate_id"] is None and screen["isogeny"] == "none"
    assert sha(RUNNER) == screen["runner_source_sha256"]
    assert sha(HERE / "native_n83_orbit_query_spill.cpp") == screen[
        "native_source_sha256"]
    assert sha(HERE / "native_n83_pairs.cpp") == screen[
        "native_pairs_sha256"]
    assert sha(HERE / "native_n83_bloom_core.hpp") == screen[
        "bloom_core_sha256"]
    completed, failed, active, missing, solved = inspect(screen)
    competing = sorted(str(path) for path in RUNS.glob("n83_*.started.json")
                       if path not in {p.with_suffix(".started.json")
                                       for p in active})
    free = shutil.disk_usage("/").free
    spill_free = shutil.disk_usage(args.spill_dir).free
    swap = swapouts()
    next_chunk = missing[0] if missing else None
    other_solved = q1060_solved()
    print(json.dumps({
        "proposal_id": "Q1062", "candidate_id": None,
        "curve_id": screen["curve_id"],
        "factor_base_enumerated_set_sha256": screen["factor_base"][
            "enumerated_set_sha256"],
        "completed_full_ranges": len(completed),
        "failed_attempts_with_unknown_work": len(failed),
        "active_full_ranges": len(active),
        "remaining_full_ranges": len(missing),
        "verified_dlp_receipts": [str(path) for path in solved],
        "other_variant_verified_dlp_receipts": other_solved,
        "competing_start_markers": competing,
        "next_query_start": next_chunk["query_start"] if next_chunk else None,
        "next_needs_explicit_retry": next_chunk["needs_retry"]
        if next_chunk else None,
        "system_free_bytes": free,
        "spill_volume_free_bytes": spill_free,
        "swapouts_pages": swap,
    }), flush=True)
    if not args.run_next:
        return
    if active or competing:
        raise RuntimeError("another n=83 search marker exists; inspect its process")
    if solved or other_solved:
        raise RuntimeError("a verified n=83 quotient-table DLP already exists")
    if not next_chunk:
        raise RuntimeError("Q1062 full-range plan exhausted")
    if next_chunk["needs_retry"] and not args.retry_failed:
        raise RuntimeError("failed range has unknown work; use explicit --retry-failed")
    if free < MIN_SYSTEM_FREE or spill_free < MIN_SPILL_FREE:
        raise RuntimeError("system or spill volume lacks full-filter headroom")
    time.sleep(30)
    ready_free = shutil.disk_usage("/").free
    ready_spill = shutil.disk_usage(args.spill_dir).free
    ready_swap = swapouts()
    if (ready_free < MIN_SYSTEM_FREE or ready_spill < MIN_SPILL_FREE or
            ready_swap - swap > MAX_PREFLIGHT_SWAPOUT_PAGES or
            list(RUNS.glob("n83_*.started.json"))):
        raise RuntimeError("full-filter preflight resource or exclusivity check failed")
    chunk = next_chunk
    runtime_path = chunk["receipt"].with_suffix(".runtime.json")
    runtime = subprocess.run([str(SAGE), "--runtime-info"], check=True,
                             capture_output=True, text=True).stdout
    runtime_path.write_text(runtime)
    assert json.loads(runtime)["status"] == "verified"
    if list(RUNS.glob("n83_*.started.json")):
        raise RuntimeError("another n=83 search started before launch")
    command = [
        str(SAGE), "-python", str(RUNNER),
        "--proposal-id", "Q1062",
        "--table-log2", "31", "--table-start", "0",
        "--query-reps-log2", "30", "--query-start",
        str(chunk["query_start"]),
        "--workers", "14", "--rep-batch", "8",
        "--bits-per-key", "20", "--hashes", "10",
        "--fast-keyer", "--spill-dir", str(args.spill_dir),
        "--runtime-info", str(runtime_path),
        "--out", str(chunk["receipt"]),
    ]
    child = subprocess.Popen(command, start_new_session=True)
    while child.poll() is None:
        time.sleep(15)
        current_free = shutil.disk_usage("/").free
        current_spill = shutil.disk_usage(args.spill_dir).free
        current_swap = swapouts()
        reason = ("system_volume" if current_free < STOP_SYSTEM_FREE else
                  "spill_volume" if current_spill < STOP_SPILL_FREE else
                  "swap_growth" if current_swap - ready_swap >
                  MAX_RUNNING_SWAPOUT_PAGES else None)
        if reason and child.poll() is None:
            os.killpg(child.pid, signal.SIGINT)
            child.wait()
            write_guard(chunk, reason=reason, before_swap=ready_swap,
                        after_swap=current_swap, before_free=ready_free,
                        after_free=current_free)
            raise RuntimeError(f"guard interrupted full-filter search: {reason}")
    if child.returncode:
        raise subprocess.CalledProcessError(child.returncode, command)


if __name__ == "__main__":
    main()
