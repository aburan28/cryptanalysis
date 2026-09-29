#!/usr/bin/env python3
"""Inspect or advance one guarded Q1058/Q1059/Q1060 n=83 rectangle.

The first M31/R30 range was completed under Q1051. Each remaining range is
queried against eight disjoint M28 table shards. A run never silently retries
or overlaps another active n=83 search.
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
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")
RUNNER = HERE / "run_n83_signed_x_chunk.py"
SOURCE = HERE / "native_n83_orbit_query_signed_x.cpp"
SPILL_SOURCE = HERE / "native_n83_orbit_query_spill.cpp"
PAIRS = HERE / "native_n83_pairs.cpp"
CORE = HERE / "native_n83_bloom_core.hpp"
SCREENS = {
    "Q1058": HERE / "n83_low_memory_screen.json",
    "Q1059": HERE / "n83_fast_low_memory_screen.json",
    "Q1060": HERE / "n83_spill_low_memory_screen.json",
}
FIRST = RUNS / "n83_orbit_k48194_chunk_M31_R30_tstart0_qstart0_b20_h14_rb8.json"
M = 1 << 28
R = 1 << 30
MIN_SYSTEM_FREE_BYTES = 4 << 30
STOP_SYSTEM_FREE_BYTES = 2 << 30
MIN_SPILL_SYSTEM_FREE_BYTES = 1536 << 20
STOP_SPILL_SYSTEM_FREE_BYTES = 768 << 20
MIN_SPILL_VOLUME_FREE_BYTES = 1 << 30
SPILL_DIR = Path("/Volumes/SSD990/llm/tmp")
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


def plan(proposal_id="Q1058"):
    prefix = {"Q1058": "n83_lowmem_",
              "Q1059": "n83_fast_lowmem_",
              "Q1060": "n83_spill_lowmem_"}[proposal_id]
    for query_index in range(1, 118):
        for shard in range(8):
            table_start = shard * M
            query_start = query_index * R
            name = (f"{prefix}k48194_chunk_M28_R30_tstart{table_start}_"
                    f"qstart{query_start}_b20_h10_rb8.json")
            yield {"table_start": table_start, "query_start": query_start,
                   "receipt": RUNS / name}


def attempt_path(chunk, attempt):
    base = chunk["receipt"]
    return (base if attempt == 0 else
            base.with_name(f"{base.stem}.retry{attempt}.json"))


def inspect(screen):
    completed, failed, active, missing, solved, unresolved = [], [], [], [], [], []
    selected_markers = set()
    proposal_id = screen["proposal_id"]
    for chunk in plan(proposal_id):
        successful = []
        chunk_failed = []
        next_missing = None
        attempt = 0
        while True:
            path = attempt_path(chunk, attempt)
            marker = path.with_suffix(".started.json")
            if not path.exists() and not marker.exists():
                if not successful:
                    next_missing = dict(chunk, receipt=path)
                    missing.append(next_missing)
                break
            selected_markers.add(marker)
            if not path.exists():
                active.append(dict(chunk, receipt=path, marker=marker))
                break
            if marker.exists():
                raise ValueError(f"terminal receipt retains start marker: {path}")
            row = json.loads(path.read_text())
            assert row["proposal_id"] == proposal_id
            assert row["candidate_id"] is None
            assert row["curve_id"] == screen["curve_id"]
            assert row["isogeny"] == "none"
            assert row["public_target"] == screen["public_target"]
            base_digest = (row["factor_base"]["enumerated_set_sha256"]
                           if "factor_base" in row else
                           row["factor_base_enumerated_set_sha256"])
            assert base_digest == screen["factor_base_enumerated_set_sha256"]
            assert row["native_source_sha256"] == screen["native_source_sha256"]
            assert row["native_pairs_sha256"] == screen["native_pairs_sha256"]
            assert row["bloom_core_sha256"] == screen["bloom_core_sha256"]
            if "wrapper_source_sha256" in row:
                assert row["wrapper_source_sha256"] == screen[
                    "runner_source_sha256"]
            assert row["table_start"] == chunk["table_start"]
            assert row["table_descriptors"] == M
            assert row["query_start"] == chunk["query_start"]
            assert row["query_representatives"] == R
            assert row["query_workers"] == 14
            assert row["representative_batch"] == 8
            assert row["bits_per_key"] == 20
            assert row["hashes"] == 10
            assert row.get("fast_keyer_enabled", False) == (
                proposal_id in ("Q1059", "Q1060"))
            assert row.get("candidate_spill_enabled", False) == (
                proposal_id == "Q1060")
            if proposal_id == "Q1060":
                assert Path(row["candidate_spill_directory"]).is_absolute()
            if row["kind"] == (
                    "n83_public_target_signed_x_query_k48194_chunk_failed"):
                assert row["native_phase_counts"] is None
                failed.append(path)
                chunk_failed.append(path)
            elif row["kind"] == (
                    "n83_public_target_signed_x_query_k48194_exact_replay_chunk"):
                if proposal_id == "Q1060":
                    assert row["native_result"]["candidate_store_mode"] == (
                        "unlinked_file")
                successful.append(path)
                if row["verified_public_target_quotient_table_dlp"]:
                    solved.append(path)
            else:
                raise ValueError(f"unexpected terminal receipt: {path}")
            attempt += 1
        if len(successful) > 1:
            raise ValueError(f"multiple completed attempts: {chunk['receipt']}")
        if chunk_failed and next_missing is not None:
            unresolved.append(next_missing)
        completed.extend(successful)
    return completed, failed, active, missing, solved, unresolved, selected_markers


def write_guard_receipt(chunk, *, proposal_id, reason, initial_swap, final_swap,
                        initial_free, final_free):
    terminal = chunk["receipt"]
    path = terminal.with_suffix(".guard.json")
    row = {
        "kind": "n83_low_memory_resource_guard_interruption",
        "proposal_id": proposal_id, "candidate_id": None,
        "reason": reason,
        "table_start": chunk["table_start"],
        "query_start": chunk["query_start"],
        "initial_swapouts_pages": initial_swap,
        "final_swapouts_pages": final_swap,
        "initial_system_free_bytes": initial_free,
        "final_system_free_bytes": final_free,
        "terminal_receipt_sha256": sha(terminal) if terminal.exists() else None,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "campaign_source_sha256": sha(Path(__file__)),
    }
    path.write_text(json.dumps(row, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-next", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--proposal-id", choices=tuple(SCREENS),
                        default="Q1058")
    parser.add_argument("--spill-dir", type=Path, default=SPILL_DIR)
    args = parser.parse_args()
    if args.proposal_id == "Q1060":
        assert args.spill_dir.is_absolute(), "candidate spill path must be absolute"
    spill_dir = args.spill_dir
    screen = json.loads(SCREENS[args.proposal_id].read_text())
    assert screen["proposal_id"] == args.proposal_id
    assert screen["candidate_id"] is None and screen["isogeny"] == "none"
    native_source = SPILL_SOURCE if args.proposal_id == "Q1060" else SOURCE
    assert sha(native_source) == screen["native_source_sha256"]
    assert sha(PAIRS) == screen["native_pairs_sha256"]
    assert sha(CORE) == screen["bloom_core_sha256"]
    assert sha(RUNNER) == screen["runner_source_sha256"]
    assert sha(FIRST) == screen["first_completed_Q1051_receipt_sha256"]
    rectangles = [(item["table_start"], item["query_start"])
                  for item in plan(args.proposal_id)]
    assert len(rectangles) == len(set(rectangles)) == 936
    assert rectangles[0] == (0, R)
    assert rectangles[-1] == (7 * M, 117 * R)
    completed, failed, active, missing, solved, unresolved, selected = inspect(screen)
    other_completed, other_failed, other_active, other_solved = [], [], [], []
    for other_id, other_path in SCREENS.items():
        if other_id == args.proposal_id:
            continue
        other_screen = json.loads(other_path.read_text())
        c, f, a, _, s, _, _ = inspect(other_screen)
        other_completed.extend(c)
        other_failed.extend(f)
        other_active.extend(a)
        other_solved.extend(s)
    competing = sorted(set(RUNS.glob("n83_*.started.json")) - selected)
    free = shutil.disk_usage("/").free
    spill_free = (shutil.disk_usage(spill_dir).free
                  if args.proposal_id == "Q1060" and spill_dir.is_dir()
                  else None)
    swap = swapouts()
    min_start_free = (MIN_SPILL_SYSTEM_FREE_BYTES if args.proposal_id == "Q1060"
                      else MIN_SYSTEM_FREE_BYTES)
    min_running_free = (STOP_SPILL_SYSTEM_FREE_BYTES if args.proposal_id == "Q1060"
                        else STOP_SYSTEM_FREE_BYTES)
    next_chunk = (unresolved[0] if args.retry_failed and unresolved else
                  missing[0] if missing else None)
    print(json.dumps({
        "proposal_id": args.proposal_id, "candidate_id": None,
        "curve_id": screen["curve_id"],
        "factor_base_enumerated_set_sha256": screen[
            "factor_base_enumerated_set_sha256"],
        "completed_rectangles": len(completed),
        "failed_attempts_with_unknown_native_work": len(failed),
        "unresolved_failed_rectangles": len(unresolved),
        "active_rectangles": len(active),
        "remaining_rectangles": len(missing),
        "verified_dlp_receipts": [str(path) for path in solved],
        "other_variant_completed_rectangles": len(other_completed),
        "other_variant_failed_attempts": len(other_failed),
        "other_variant_verified_dlp_receipts": [str(path) for path in other_solved],
        "competing_start_markers": [str(path) for path in competing],
        "next_rectangle": ({"table_start": next_chunk["table_start"],
                            "query_start": next_chunk["query_start"]}
                           if next_chunk else None),
        "system_free_bytes": free,
        "minimum_system_free_bytes_to_launch": min_start_free,
        "spill_volume_free_bytes": spill_free,
        "candidate_spill_directory": (str(spill_dir) if
                                      args.proposal_id == "Q1060" else None),
        "minimum_spill_volume_free_bytes_to_launch": (
            MIN_SPILL_VOLUME_FREE_BYTES if args.proposal_id == "Q1060" else None),
        "swapouts_pages": swap,
    }), flush=True)
    if not args.run_next:
        return
    if active or other_active or competing:
        raise RuntimeError("an n=83 search marker exists; inspect its process")
    if solved or other_solved:
        raise RuntimeError("a verified public-target DLP already exists")
    if other_completed or other_failed:
        raise RuntimeError("the other low-memory variant has completed or failed rectangles; reconcile coverage before switching")
    if unresolved and not args.retry_failed:
        raise RuntimeError("a failed rectangle has unknown work; inspect its receipt before an explicit --retry-failed")
    if not missing:
        raise RuntimeError("low-memory plan exhausted without a relation")
    if free < min_start_free:
        raise RuntimeError("system volume lacks M28/R30 search headroom")
    if args.proposal_id == "Q1060" and (
            spill_free is None or spill_free < MIN_SPILL_VOLUME_FREE_BYTES):
        raise RuntimeError("candidate spill volume lacks headroom")
    time.sleep(30)
    ready_free = shutil.disk_usage("/").free
    ready_spill_free = (shutil.disk_usage(spill_dir).free
                        if args.proposal_id == "Q1060" else None)
    ready_swap = swapouts()
    if (ready_free < min_start_free or ready_swap - swap >
            MAX_PREFLIGHT_SWAPOUT_GROWTH_PAGES):
        raise RuntimeError("preflight root space or swap stability failed")
    if args.proposal_id == "Q1060" and ready_spill_free < (
            MIN_SPILL_VOLUME_FREE_BYTES):
        raise RuntimeError("preflight candidate spill volume lacks headroom")
    if list(RUNS.glob("n83_*.started.json")):
        raise RuntimeError("another n=83 search started during preflight")
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
        "--proposal-id", args.proposal_id,
        "--table-log2", "28", "--table-start", str(chunk["table_start"]),
        "--query-reps-log2", "30", "--query-start", str(chunk["query_start"]),
        "--workers", "14", "--rep-batch", "8",
        "--bits-per-key", "20", "--hashes", "10",
        "--runtime-info", str(runtime_path),
        "--out", str(chunk["receipt"]),
    ]
    if args.proposal_id in ("Q1059", "Q1060"):
        command.append("--fast-keyer")
    if args.proposal_id == "Q1060":
        command.extend(["--spill-dir", str(spill_dir)])
    child = subprocess.Popen(command, start_new_session=True)
    while child.poll() is None:
        time.sleep(15)
        current_free = shutil.disk_usage("/").free
        current_swap = swapouts()
        current_spill_free = (shutil.disk_usage(spill_dir).free
                              if args.proposal_id == "Q1060" and
                              spill_dir.is_dir() else None)
        reason = ("system_volume" if current_free < min_running_free
                  else "swap_growth" if current_swap - ready_swap >
                  MAX_SWAPOUT_GROWTH_PAGES else "spill_volume" if
                  args.proposal_id == "Q1060" and
                  (current_spill_free is None or current_spill_free <
                   MIN_SPILL_VOLUME_FREE_BYTES // 2) else None)
        if reason and child.poll() is None:
            os.killpg(child.pid, signal.SIGINT)
            child.wait()
            write_guard_receipt(chunk, proposal_id=args.proposal_id,
                                reason=reason,
                                initial_swap=ready_swap,
                                final_swap=current_swap,
                                initial_free=ready_free,
                                final_free=current_free)
            raise RuntimeError(f"guard interrupted search: {reason}")
    if child.returncode:
        raise subprocess.CalledProcessError(child.returncode, command)


if __name__ == "__main__":
    main()
