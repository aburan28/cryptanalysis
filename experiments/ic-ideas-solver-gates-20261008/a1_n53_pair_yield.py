#!/usr/bin/env python3
"""Bounded N53 ordinary three-summand yield with a Frobenius pair index."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PACKAGE = HERE / "a1_n53_closure"
BINARY = PACKAGE / "target/release/pair_probe"
GEOMETRY = REPO / "experiments/ic-ideas-20261007/results/a1_n53_k600_followup_final.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wilson(successes: int, trials: int) -> list[float]:
    z = 1.959963984540054
    p = successes / trials
    denominator = 1 + z*z/trials
    center = (p + z*z/(2*trials)) / denominator
    radius = z * math.sqrt(p*(1-p)/trials + z*z/(4*trials*trials)) / denominator
    return [center-radius, center+radius]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", choices=("seed", "closure"), required=True)
    parser.add_argument("--columns", type=int, default=600)
    parser.add_argument("--queries", type=int, default=64)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    args = parser.parse_args()
    if args.columns < 1 or args.queries < 1 or args.timeout_seconds < 1:
        parser.error("columns, queries, and timeout must be positive")
    if args.policy == "closure" and args.columns % 10:
        parser.error("closure geometry requires a multiple of ten columns")
    prefix = f"a1_n53_pair_{args.policy}_k{args.columns}_q{args.queries}"
    out = HERE / f"{prefix}.json"
    raw = HERE / f"{prefix}_raw.json"
    progress = HERE / f"{prefix}_progress.json"
    if any(path.exists() for path in (out, raw, progress)):
        raise FileExistsError("preserve prior pair-index artifacts")
    geometry = json.loads(GEOMETRY.read_text())
    assert geometry["seed_folded_columns"] == 600
    assert geometry["seed_actual_usable_B"] == 63_600
    environment = os.environ.copy()
    environment["A1_PAIR_PROGRESS_PATH"] = str(progress)
    command = [str(BINARY), args.policy, str(args.columns),
               str(args.queries), str(raw)]
    started = time.perf_counter_ns()
    try:
        process = subprocess.run(command, env=environment, capture_output=True,
                                 text=True, timeout=args.timeout_seconds)
        status = "completed" if process.returncode == 0 else "process_error"
        exit_code = process.returncode
        stderr_tail = process.stderr[-2000:]
    except subprocess.TimeoutExpired as error:
        status = "timeout"
        exit_code = None
        stderr_tail = error.stderr or b""
        if isinstance(stderr_tail, bytes):
            stderr_tail = stderr_tail[-2000:].decode(errors="replace")
    wall_ns = time.perf_counter_ns() - started
    record = json.loads(raw.read_text()) if raw.exists() else None
    checkpoint = json.loads(progress.read_text()) if progress.exists() else None
    if record is not None:
        assert record["policy"] == args.policy
        assert record["geometric_columns"] == args.columns
        assert record["actual_usable_B"] == args.columns * 106
        assert record["independent_log_columns"] == (
            args.columns if args.policy == "seed" else args.columns//10)
        assert record["query_count"] == args.queries
        assert len(record["rows"]) == args.queries
        assert sum(row["hit"] for row in record["rows"]) == record["verified_hits"]
        assert sum(row["novel_row"] for row in record["rows"]) == record["rank"]
        status = "completed_verified"
    answer = {"schema_version": 1, "proposal_id": "A1",
              "candidate_id": None, "run_id": None,
              "scope": "N53 ordinary three-summand relation yield at equal point geometry",
              "status": status, "policy": args.policy,
              "geometric_columns": args.columns,
              "independent_log_columns": args.columns if args.policy == "seed" else args.columns//10,
              "actual_usable_B": args.columns*106,
              "query_count_cap": args.queries,
              "queries_completed": record["query_count"] if record else
                  (checkpoint.get("queries_completed") if checkpoint else None),
              "verified_hits": record["verified_hits"] if record else
                  (checkpoint.get("hits") if checkpoint else None),
              "novel_rows": record["novel_rows"] if record else
                  (checkpoint.get("rank") if checkpoint else None),
              "wilson95": wilson(record["verified_hits"], args.queries)
                  if record else None,
              "checkpoint": checkpoint,
              "process_wall_ns_exploratory": wall_ns,
              "timeout_seconds": args.timeout_seconds,
              "process_exit_code": exit_code, "stderr_tail": stderr_tail,
              "raw_record": raw.name if raw.exists() else None,
              "raw_sha256": sha(raw) if raw.exists() else None,
              "progress_record": progress.name if progress.exists() else None,
              "progress_sha256": sha(progress) if progress.exists() else None,
              "source_sha256": sha(Path(__file__)),
              "pair_source_sha256": sha(PACKAGE / "src/bin/pair_probe.rs"),
              "shared_source_sha256": sha(PACKAGE / "src/main.rs"),
              "build_source_sha256": sha(PACKAGE / "build.rs"),
              "cargo_lock_sha256": sha(PACKAGE / "Cargo.lock"),
              "binary_sha256": sha(BINARY),
              "geometry_receipt_sha256": sha(GEOMETRY)}
    out.write_text(json.dumps(answer, sort_keys=True, indent=2) + "\n")
    print(json.dumps({key: answer[key] for key in
                      ("policy", "status", "queries_completed", "verified_hits",
                       "novel_rows")}))


if __name__ == "__main__":
    main()
