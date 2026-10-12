#!/usr/bin/env python3
"""Advance the bounded n=83 two-shard search by one terminal chunk."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
SCREEN = HERE / "n83_bloom_shard_screen.json"
RUNNER = HERE / "run_n83_bloom_chunk.py"
AGGREGATOR = HERE / "aggregate_n83_bloom_chunks.py"
AGGREGATE = RUNS / "n83_bloom_campaign_aggregate.json"


def expected_chunks(screen):
    m = screen["shard_table_descriptors"]
    q = screen["first_query_count"]
    bits = screen["bits_per_key"]
    hashes = screen["hashes"]
    assert m == 1 << 32 and q == 1 << 38
    assert bits == 20 and hashes == 14
    count = screen["bounded_95pct_chunks_per_shard"]
    assert count == 29
    assert screen["bounded_95pct_total_chunk_runs"] == 2 * count
    assert screen["bounded_95pct_query_prefix_each_shard"] == count * q
    for query_index in range(count):
        for shard_index in range(2):
            table_start = shard_index * m
            query_start = query_index * q
            name = (f"n83_bloom_chunk_M32_Q38_tstart{table_start}_"
                    f"qstart{query_start}_b{bits}_h{hashes}.json")
            yield {
                "table_start": table_start,
                "query_start": query_start,
                "table_descriptors": m,
                "query_count": q,
                "bits_per_key": bits,
                "hashes": hashes,
                "receipt": RUNS / name,
                "started": (RUNS / name).with_suffix(".started.json"),
            }


def inspect(chunks, screen):
    completed = []
    running = []
    failed = []
    missing = []
    solved = []
    for chunk in chunks:
        receipt_path = chunk["receipt"]
        started_path = chunk["started"]
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text())
            assert receipt["curve_id"] == screen["curve_id"]
            for key in ("table_start", "query_start", "table_descriptors",
                        "query_count", "bits_per_key", "hashes"):
                assert receipt[key] == chunk[key], (receipt_path, key)
            if receipt["kind"] == "n83_public_target_bloom_chunk_failed":
                failed.append(chunk)
            elif receipt["kind"] == "n83_public_target_bloom_exact_replay_chunk":
                assert receipt["factor_base"]["enumerated_set_sha256"] == screen[
                    "factor_base_enumerated_set_sha256"]
                completed.append(chunk)
                if receipt["verified_public_target_quotient_table_dlp"]:
                    solved.append(chunk)
            else:
                raise ValueError(f"unexpected terminal receipt: {receipt_path}")
            if started_path.exists():
                raise ValueError(f"both terminal and started receipts: {receipt_path}")
        elif started_path.exists():
            running.append(chunk)
        else:
            missing.append(chunk)
    return completed, running, failed, missing, solved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-next", action="store_true",
                        help="launch exactly one missing chunk; refuses an active marker or failure")
    parser.add_argument("--aggregate", action="store_true",
                        help="write cumulative completed-chunk accounting")
    args = parser.parse_args()
    screen = json.loads(SCREEN.read_text())
    assert screen["proposal_id"] == "Q1049"
    assert screen["candidate_id"] is None
    assert screen["isogeny"] == "none"
    chunks = list(expected_chunks(screen))
    assert len(chunks) == 58
    completed, running, failed, missing, solved = inspect(chunks, screen)
    summary = {
        "curve_id": screen["curve_id"],
        "proposal_id": "Q1049",
        "candidate_id": None,
        "completed": len(completed),
        "started_markers": [str(item["started"]) for item in running],
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
        if running:
            raise RuntimeError("a chunk has a start marker; verify its live process before advancing")
        if failed:
            raise RuntimeError("a terminal failed chunk needs work accounting before advancing")
        if solved:
            raise RuntimeError("a verified quotient-table DLP already exists")
        if not missing:
            raise RuntimeError("bounded campaign exhausted without a verified relation")
        next_chunk = missing[0]
        subprocess.run([
            sys.executable, str(RUNNER),
            "--table-log2", "32",
            "--table-start", str(next_chunk["table_start"]),
            "--query-count-log2", "38",
            "--query-start", str(next_chunk["query_start"]),
            "--workers", "8",
            "--bits-per-key", "20",
            "--hashes", "14",
        ], check=True)


if __name__ == "__main__":
    main()
