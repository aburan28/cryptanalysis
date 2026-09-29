#!/usr/bin/env python3
"""Advance the extended-base n=83 search by one frozen rectangle."""

import argparse
import json
import os
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
SCREEN = HERE / "n83_large_knownlog_base_screen.json"
RUNNER = HERE / "run_n83_orbit_chunk_k48194.py"
AGGREGATOR = HERE / "aggregate_n83_large_orbit_chunks.py"
AGGREGATE = RUNS / "n83_large_orbit_campaign_aggregate.json"
TABLE_LOG2 = 31
MIN_SYSTEM_FREE_BYTES = 1 << 30
STOP_SYSTEM_FREE_BYTES = 512 << 20
MAX_SWAPOUT_GROWTH_PAGES = 1024


def swapouts():
    output = subprocess.run(["vm_stat"], check=True, capture_output=True,
                            text=True).stdout
    for line in output.splitlines():
        if line.startswith("Swapouts:"):
            return int(line.split(":", 1)[1].strip().rstrip("."))
    raise RuntimeError("vm_stat omitted Swapouts")


def expected_chunks(screen):
    m = 1 << TABLE_LOG2
    r = screen["query_representatives_per_chunk"]
    count = screen["query_chunks_for_95pct_model"]
    assert r == 1 << 31 and count == 59
    assert screen["table_descriptors"] == m
    assert screen["table_shards"] == 1
    assert screen["query_lifted_pairs_for_95pct_model"] == count * r * 166
    assert screen["model_success_probability_at_prefix"] >= 0.95
    for query_index in range(count):
        query_start = query_index * r
        name = (f"n83_orbit_k48194_chunk_M31_R31_tstart0_"
                f"qstart{query_start}_b20_h14_rb8.json")
        receipt = RUNS / name
        yield {
            "table_start": 0,
            "table_descriptors": m,
            "query_start": query_start,
            "query_representatives": r,
            "receipt": receipt,
            "started": receipt.with_suffix(".started.json"),
        }


def inspect(chunks, screen):
    completed = []
    started = []
    failed = []
    missing = []
    solved = []
    for chunk in chunks:
        path = chunk["receipt"]
        marker = chunk["started"]
        if path.exists():
            record = json.loads(path.read_text())
            assert record["curve_id"] == screen["curve_id"]
            assert record["proposal_id"] == "Q1051"
            assert record["candidate_id"] is None
            assert record["isogeny"] == "none"
            for key in ("table_start", "table_descriptors",
                        "query_start", "query_representatives"):
                assert record[key] == chunk[key], (path, key)
            if record["kind"] == "n83_public_target_orbit_query_k48194_chunk_failed":
                failed.append(chunk)
            elif record["kind"] == "n83_public_target_orbit_query_k48194_exact_replay_chunk":
                assert record["factor_base"]["enumerated_set_sha256"] == screen[
                    "factor_base"]["enumerated_set_sha256"]
                completed.append(chunk)
                if record["verified_public_target_quotient_table_dlp"]:
                    solved.append(chunk)
            else:
                raise ValueError(f"unexpected terminal receipt: {path}")
            if marker.exists():
                raise ValueError(f"both terminal and start marker: {path}")
        elif marker.exists():
            started.append(chunk)
        else:
            missing.append(chunk)
    return completed, started, failed, missing, solved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-next", action="store_true",
                        help="run exactly one missing rectangle")
    parser.add_argument("--aggregate", action="store_true",
                        help="write cumulative accounting for completed rectangles")
    args = parser.parse_args()
    screen = json.loads(SCREEN.read_text())
    assert screen["proposal_id"] == "Q1051"
    assert screen["candidate_id"] is None
    assert screen["isogeny"] == "none"
    assert screen["campaign_query_workers"] == 14
    chunks = list(expected_chunks(screen))
    assert len(chunks) == 59
    completed, started, failed, missing, solved = inspect(chunks, screen)
    selected_markers = {item["started"] for item in chunks}
    competing_markers = sorted(
        set(RUNS.glob("n83_bloom_chunk_*.started.json")) |
        set(RUNS.glob("n83_orbit_chunk_*.started.json")) |
        (set(RUNS.glob("n83_orbit_k48194_chunk_*.started.json")) -
         selected_markers))
    system_free_bytes = shutil.disk_usage("/").free
    current_swapouts = swapouts()
    summary = {
        "curve_id": screen["curve_id"],
        "proposal_id": "Q1051", "candidate_id": None,
        "actual_usable_points_B_before_folding": screen[
            "factor_base"]["actual_usable_points_B_before_folding"],
        "signed_frobenius_columns": screen[
            "factor_base"]["signed_frobenius_columns"],
        "table_descriptors": 1 << TABLE_LOG2,
        "query_workers": screen["campaign_query_workers"],
        "total_planned_rectangles": len(chunks),
        "completed": len(completed),
        "started_markers": [str(item["started"]) for item in started],
        "competing_search_markers": [
            str(path) for path in competing_markers],
        "system_volume_free_bytes": system_free_bytes,
        "minimum_system_volume_free_bytes_to_launch":
            MIN_SYSTEM_FREE_BYTES,
        "stop_system_volume_free_bytes": STOP_SYSTEM_FREE_BYTES,
        "swapouts_pages_before_launch": current_swapouts,
        "maximum_swapout_growth_pages_before_interrupt":
            MAX_SWAPOUT_GROWTH_PAGES,
        "failed": [str(item["receipt"]) for item in failed],
        "verified_quotient_table_dlp_receipts": [
            str(item["receipt"]) for item in solved],
        "next_missing": str(missing[0]["receipt"]) if missing else None,
    }
    print(json.dumps(summary), flush=True)
    if args.aggregate and completed:
        subprocess.run([sys.executable, str(AGGREGATOR),
                        *[str(item["receipt"]) for item in completed],
                        "--out", str(AGGREGATE)],
                       check=True)
    if args.run_next:
        if started or competing_markers:
            raise RuntimeError(
                "a start marker exists; verify the original process handle before advancing")
        if failed:
            raise RuntimeError("a terminal failed chunk needs work accounting")
        if solved:
            raise RuntimeError("a verified quotient-table DLP already exists")
        if not missing:
            raise RuntimeError("bounded campaign exhausted without a relation")
        if system_free_bytes < MIN_SYSTEM_FREE_BYTES:
            raise RuntimeError(
                "system volume has insufficient free space for swap safety")
        chunk = missing[0]
        command = [
            sys.executable, str(RUNNER),
            "--table-log2", str(TABLE_LOG2),
            "--table-start", str(chunk["table_start"]),
            "--query-reps-log2", "31",
            "--query-start", str(chunk["query_start"]),
            "--workers", str(screen["campaign_query_workers"]),
            "--rep-batch", "8",
            "--bits-per-key", "20",
            "--hashes", "14",
        ]
        child = subprocess.Popen(command, start_new_session=True)
        while child.poll() is None:
            time.sleep(15)
            current_free = shutil.disk_usage("/").free
            current_swap = swapouts()
            if (current_free < STOP_SYSTEM_FREE_BYTES or
                    current_swap - current_swapouts >
                    MAX_SWAPOUT_GROWTH_PAGES):
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGINT)
                    child.wait()
                    raise RuntimeError(
                        "search interrupted after system disk or swap "
                        "pressure; inspect its terminal receipt and "
                        "charged-work status")
        if child.returncode:
            raise subprocess.CalledProcessError(child.returncode, command)


if __name__ == "__main__":
    main()
