#!/usr/bin/env python3
"""Advance one guarded Q1054 rectangle after the Q1051 completed prefix."""

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
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")
RUNNER = HERE / "run_n83_signed_x_chunk.py"
FIRST_Q1051 = RUNS / (
    "n83_orbit_k48194_chunk_M31_R30_tstart0_qstart0_b20_h14_rb8.json")
SCREEN = HERE / "n83_signed_x_screen.json"
M = 1 << 31
R = 1 << 30
PLANNED_CHUNKS = 118
MIN_SYSTEM_FREE_BYTES = 12 << 30
STOP_SYSTEM_FREE_BYTES = 512 << 20
MAX_SWAPOUT_GROWTH_PAGES = 1024
MAX_PREFLIGHT_SWAPOUT_GROWTH_PAGES = 128


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def swapouts():
    output = subprocess.run(["vm_stat"], check=True, capture_output=True,
                            text=True).stdout
    for line in output.splitlines():
        if line.startswith("Swapouts:"):
            return int(line.split(":", 1)[1].strip().rstrip("."))
    raise RuntimeError("vm_stat omitted Swapouts")


def chunks():
    for index in range(1, PLANNED_CHUNKS):
        query_start = index * R
        name = (f"n83_signed_x_k48194_chunk_M31_R30_tstart0_"
                f"qstart{query_start}_b20_h14_rb8.json")
        yield {"query_start": query_start, "receipt": RUNS / name}


def attempt_path(chunk, attempt):
    base = chunk["receipt"]
    return (base if attempt == 0 else
            base.with_name(f"{base.stem}.retry{attempt}.json"))


def inspect(plan, screen):
    completed, failed, active, missing, solved = [], [], [], [], []
    selected_markers = set()
    for chunk in plan:
        successful = []
        attempt = 0
        while True:
            path = attempt_path(chunk, attempt)
            marker = path.with_suffix(".started.json")
            if not path.exists() and not marker.exists():
                if not successful:
                    missing.append(dict(chunk, receipt=path))
                break
            selected_markers.add(marker)
            if not path.exists():
                active.append(dict(chunk, receipt=path, marker=marker))
                break
            if marker.exists():
                raise ValueError(f"terminal receipt retains start marker: {path}")
            record = json.loads(path.read_text())
            assert record["proposal_id"] == "Q1054"
            assert record["candidate_id"] is None
            assert record["curve_id"] == screen["curve_id"]
            assert record["isogeny"] == "none"
            assert record["public_target"] == screen["public_target"]
            assert record["native_source_sha256"] == screen[
                "native_source_sha256"]
            assert record["table_start"] == 0
            assert record["table_descriptors"] == M
            assert record["query_start"] == chunk["query_start"]
            assert record["query_representatives"] == R
            assert record["query_workers"] == 14
            assert record["representative_batch"] == 8
            assert record["bits_per_key"] == 20
            assert record["hashes"] == 14
            base_digest = (record["factor_base"]["enumerated_set_sha256"]
                           if "factor_base" in record else
                           record["factor_base_enumerated_set_sha256"])
            assert base_digest == screen[
                "factor_base_enumerated_set_sha256"]
            if record["kind"] == (
                    "n83_public_target_signed_x_query_k48194_chunk_failed"):
                failed.append(path)
            elif record["kind"] == (
                    "n83_public_target_signed_x_query_k48194_exact_replay_chunk"):
                successful.append(path)
                if record["verified_public_target_quotient_table_dlp"]:
                    solved.append(path)
            else:
                raise ValueError(f"unexpected terminal receipt: {path}")
            attempt += 1
        if len(successful) > 1:
            raise ValueError(f"multiple completed attempts for {chunk['receipt']}")
        completed.extend(successful)
    return completed, failed, active, missing, solved, selected_markers


def write_guard_receipt(chunk, *, reason, initial_swap, final_swap,
                        initial_free, final_free):
    path = chunk["receipt"].with_suffix(".guard.json")
    terminal = chunk["receipt"]
    report = {
        "kind": "n83_signed_x_resource_guard_interruption",
        "proposal_id": "Q1054", "candidate_id": None,
        "reason": reason,
        "query_start": chunk["query_start"],
        "initial_swapouts_pages": initial_swap,
        "final_swapouts_pages": final_swap,
        "initial_system_free_bytes": initial_free,
        "final_system_free_bytes": final_free,
        "terminal_receipt_sha256": sha(terminal) if terminal.exists() else None,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "campaign_source_sha256": sha(Path(__file__)),
    }
    path.write_text(json.dumps(report, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-next", action="store_true",
                        help="run exactly one missing guarded rectangle")
    args = parser.parse_args()
    screen = json.loads(SCREEN.read_text())
    first = json.loads(FIRST_Q1051.read_text())
    assert screen["proposal_id"] == "Q1054"
    assert screen["candidate_id"] is None
    assert first["proposal_id"] == "Q1051"
    assert first["candidate_id"] is None
    assert first["curve_id"] == screen["curve_id"]
    assert first["isogeny"] == screen["isogeny"] == "none"
    assert first["factor_base"]["enumerated_set_sha256"] == screen[
        "factor_base_enumerated_set_sha256"]
    assert first["public_target"] == screen["public_target"]
    assert first["table_descriptors"] == M
    assert first["query_start"] == 0
    assert first["query_representatives"] == R
    assert first["native_result"]["exact_hit_queries"] == 0
    assert first["verified_public_target_quotient_table_dlp"] is False
    plan = list(chunks())
    completed, failed, active, missing, solved, markers = inspect(
        plan, screen)
    competing = sorted(set(RUNS.glob("n83_*.started.json")) - markers)
    free = shutil.disk_usage("/").free
    swap = swapouts()
    summary = {
        "curve_id": screen["curve_id"],
        "proposal_id": "Q1054", "candidate_id": None,
        "prior_Q1051_completed_receipt_sha256": sha(FIRST_Q1051),
        "planned_followup_rectangles": len(plan),
        "completed_followup_rectangles": len(completed),
        "failed_followup_attempts": [str(path) for path in failed],
        "active_markers": [str(item["marker"]) for item in active],
        "competing_markers": [str(path) for path in competing],
        "verified_dlp_receipts": [str(path) for path in solved],
        "next_missing": str(missing[0]["receipt"]) if missing else None,
        "system_volume_free_bytes": free,
        "minimum_system_volume_free_bytes_to_launch":
            MIN_SYSTEM_FREE_BYTES,
        "swapouts_pages": swap,
    }
    print(json.dumps(summary), flush=True)
    if not args.run_next:
        return
    if active or competing:
        raise RuntimeError("a search marker exists; inspect its process handle")
    if solved:
        raise RuntimeError("a verified public-target DLP already exists")
    if not missing:
        raise RuntimeError("bounded Q1054 prefix exhausted without a relation")
    if free < MIN_SYSTEM_FREE_BYTES:
        raise RuntimeError("system volume lacks full-size search headroom")
    time.sleep(30)
    ready_free = shutil.disk_usage("/").free
    ready_swap = swapouts()
    if (ready_free < MIN_SYSTEM_FREE_BYTES or
            ready_swap - swap > MAX_PREFLIGHT_SWAPOUT_GROWTH_PAGES):
        raise RuntimeError("preflight root space or swap stability failed")
    if list(RUNS.glob("n83_*.started.json")):
        raise RuntimeError("another n=83 search started during preflight")
    chunk = missing[0]
    runtime_path = chunk["receipt"].with_suffix(".runtime.json")
    runtime = subprocess.run([str(SAGE), "--runtime-info"], check=True,
                             capture_output=True, text=True).stdout
    runtime_path.write_text(runtime)
    assert json.loads(runtime)["status"] == "verified"
    if list(RUNS.glob("n83_*.started.json")):
        raise RuntimeError("another n=83 search started before launch")
    command = [
        str(SAGE), "-python", str(RUNNER),
        "--table-log2", "31", "--table-start", "0",
        "--query-reps-log2", "30",
        "--query-start", str(chunk["query_start"]),
        "--workers", "14", "--rep-batch", "8",
        "--bits-per-key", "20", "--hashes", "14",
        "--runtime-info", str(runtime_path),
        "--out", str(chunk["receipt"]),
    ]
    child = subprocess.Popen(command, start_new_session=True)
    while child.poll() is None:
        time.sleep(15)
        current_free = shutil.disk_usage("/").free
        current_swap = swapouts()
        reason = ("system_volume" if current_free < STOP_SYSTEM_FREE_BYTES
                  else "swap_growth" if current_swap - ready_swap >
                  MAX_SWAPOUT_GROWTH_PAGES else None)
        if reason and child.poll() is None:
            os.killpg(child.pid, signal.SIGINT)
            child.wait()
            write_guard_receipt(chunk, reason=reason,
                                initial_swap=ready_swap,
                                final_swap=current_swap,
                                initial_free=ready_free,
                                final_free=current_free)
            raise RuntimeError(f"guard interrupted search: {reason}")
    if child.returncode:
        raise subprocess.CalledProcessError(child.returncode, command)


if __name__ == "__main__":
    main()
