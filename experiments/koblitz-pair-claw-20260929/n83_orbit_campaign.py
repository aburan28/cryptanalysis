#!/usr/bin/env python3
"""Advance the n=83 pair-orbit search by one bounded rectangle."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
SCREEN = HERE / "n83_query_orbit_reuse_screen.json"
RUNNER = HERE / "run_n83_orbit_chunk.py"
AGGREGATOR = HERE / "aggregate_n83_orbit_chunks.py"
PLANS = {
    "m31": (31, 4, 22),
    "m32": (32, 2, 22),
}
MIN_SYSTEM_FREE_BYTES = 4 * (1 << 30)


def expected_chunks(screen, plan):
    table_log2, shard_count, count = PLANS[plan]
    m = 1 << table_log2
    r = screen["query_representatives_per_chunk"]
    assert r == 1 << 31 and count == 22
    assert shard_count * m == 1 << 33
    assert screen["representative_prefix_per_shard"] == count * r
    assert screen["model_success_probability_at_prefix"] >= 0.95
    if plan == "m31":
        assert screen["four_2pow31_shards_95pct_total_chunk_runs"] == 88
    else:
        assert screen["total_chunk_runs_for_95pct_model"] == 44
    for query_index in range(count):
        for shard_index in range(shard_count):
            table_start = shard_index * m
            query_start = query_index * r
            name = (f"n83_orbit_chunk_M{table_log2}_R31_tstart{table_start}_"
                    f"qstart{query_start}_b20_h14_rb8.json")
            receipt = RUNS / name
            yield {
                "table_start": table_start,
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
            assert record["proposal_id"] == "Q1050"
            assert record["candidate_id"] is None
            assert record["isogeny"] == "none"
            for key in ("table_start", "table_descriptors",
                        "query_start", "query_representatives"):
                assert record[key] == chunk[key], (path, key)
            if record["kind"] == "n83_public_target_orbit_query_chunk_failed":
                failed.append(chunk)
            elif record["kind"] == "n83_public_target_orbit_query_exact_replay_chunk":
                assert record["factor_base"]["enumerated_set_sha256"] == screen[
                    "factor_base_enumerated_set_sha256"]
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
    parser.add_argument("--plan", choices=PLANS, default="m31",
                        help="m31 is the lower-memory four-shard plan; m32 is read-only")
    args = parser.parse_args()
    screen = json.loads(SCREEN.read_text())
    assert screen["proposal_id"] == "Q1050"
    assert screen["candidate_id"] is None
    assert screen["isogeny"] == "none"
    chunks = list(expected_chunks(screen, args.plan))
    assert len(chunks) == PLANS[args.plan][1] * PLANS[args.plan][2]
    completed, started, failed, missing, solved = inspect(chunks, screen)
    selected_markers = {item["started"] for item in chunks}
    competing_markers = sorted(
        set(RUNS.glob("n83_bloom_chunk_*.started.json")) |
        (set(RUNS.glob("n83_orbit_chunk_*.started.json")) -
         selected_markers))
    system_free_bytes = shutil.disk_usage("/").free
    summary = {
        "curve_id": screen["curve_id"],
        "proposal_id": "Q1050", "candidate_id": None,
        "plan": args.plan,
        "table_descriptors_per_shard": 1 << PLANS[args.plan][0],
        "total_planned_rectangles": len(chunks),
        "completed": len(completed),
        "started_markers": [str(item["started"]) for item in started],
        "competing_search_markers": [
            str(path) for path in competing_markers],
        "system_volume_free_bytes": system_free_bytes,
        "minimum_system_volume_free_bytes_to_launch":
            MIN_SYSTEM_FREE_BYTES,
        "failed": [str(item["receipt"]) for item in failed],
        "verified_quotient_table_dlp_receipts": [
            str(item["receipt"]) for item in solved],
        "next_missing": str(missing[0]["receipt"]) if missing else None,
    }
    print(json.dumps(summary), flush=True)
    if args.aggregate and completed:
        subprocess.run([sys.executable, str(AGGREGATOR),
                        *[str(item["receipt"]) for item in completed],
                        "--out", str(RUNS /
                                     f"n83_orbit_campaign_{args.plan}_aggregate.json")],
                       check=True)
    if args.run_next:
        if args.plan != "m31":
            raise RuntimeError("the m32 plan is read-only after host swap pressure")
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
        subprocess.run([
            sys.executable, str(RUNNER),
            "--table-log2", str(PLANS[args.plan][0]),
            "--table-start", str(chunk["table_start"]),
            "--query-reps-log2", "31",
            "--query-start", str(chunk["query_start"]),
            "--workers", "8",
            "--rep-batch", "8",
            "--bits-per-key", "20",
            "--hashes", "14",
        ], check=True)


if __name__ == "__main__":
    main()
