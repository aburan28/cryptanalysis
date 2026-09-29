#!/usr/bin/env python3
"""Advance the n=83 pair-orbit search by one bounded rectangle."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
SCREEN = HERE / "n83_query_orbit_reuse_screen.json"
RUNNER = HERE / "run_n83_orbit_chunk.py"
AGGREGATOR = HERE / "aggregate_n83_orbit_chunks.py"
AGGREGATE = RUNS / "n83_orbit_campaign_aggregate.json"


def expected_chunks(screen):
    m = 1 << 32
    r = screen["query_representatives_per_chunk"]
    count = screen[
        "query_chunks_per_table_shard_for_95pct_model"]
    assert r == 1 << 31 and count == 22
    assert screen["total_chunk_runs_for_95pct_model"] == 2 * count
    assert screen["representative_prefix_per_shard"] == count * r
    for query_index in range(count):
        for shard_index in range(2):
            table_start = shard_index * m
            query_start = query_index * r
            name = (f"n83_orbit_chunk_M32_R31_tstart{table_start}_"
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
    args = parser.parse_args()
    screen = json.loads(SCREEN.read_text())
    assert screen["proposal_id"] == "Q1050"
    assert screen["candidate_id"] is None
    assert screen["isogeny"] == "none"
    chunks = list(expected_chunks(screen))
    assert len(chunks) == 44
    completed, started, failed, missing, solved = inspect(chunks, screen)
    competing_markers = list(RUNS.glob(
        "n83_bloom_chunk_M32_Q38_*.started.json"))
    summary = {
        "curve_id": screen["curve_id"],
        "proposal_id": "Q1050", "candidate_id": None,
        "completed": len(completed),
        "started_markers": [str(item["started"]) for item in started],
        "competing_direct_shard_markers": [
            str(path) for path in competing_markers],
        "failed": [str(item["receipt"]) for item in failed],
        "verified_quotient_table_dlp_receipts": [
            str(item["receipt"]) for item in solved],
        "next_missing": str(missing[0]["receipt"]) if missing else None,
    }
    print(json.dumps(summary), flush=True)
    if args.aggregate and completed:
        subprocess.run([sys.executable, str(AGGREGATOR),
                        *[str(item["receipt"]) for item in completed],
                        "--out", str(AGGREGATE)], check=True)
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
        chunk = missing[0]
        subprocess.run([
            sys.executable, str(RUNNER),
            "--table-log2", "32",
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
