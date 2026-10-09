#!/usr/bin/env python3
"""Paired N53 ordinary-query yield at 600 geometric columns and 63,600 points."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BINARY = HERE / "a1_n53_closure/target/release/a1_n53_closure"
SOURCE = HERE / "a1_n53_closure/src/main.rs"
TARGETS = (REPO / "experiments/koblitz-n53-fastindex4-streaming-cert-20260930-v3-rho-online-accounting"
           / "input/target_points.jsonl")
GEOMETRY = (REPO / "experiments/ic-ideas-20261007/results"
            / "a1_n53_k600_followup_final.json")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", choices=("seed", "closure"), required=True)
    parser.add_argument("--queries", type=int, default=64)
    args = parser.parse_args()
    policy = args.policy
    if args.queries < 1:
        parser.error("positive query count required")
    receipt_path = HERE / f"a1_n53_matched_{policy}_q{args.queries}.json"
    raw_path = HERE / f"a1_n53_matched_{policy}_q{args.queries}_raw.jsonl"
    progress_path = HERE / f"a1_n53_matched_{policy}_q{args.queries}_progress.json"
    target_path = HERE / "a1_n53_target0.json"
    if any(path.exists() for path in (receipt_path, raw_path, progress_path)):
        raise FileExistsError("preserve prior matched N53 artifacts")
    target = json.loads(TARGETS.read_text().splitlines()[0])
    assert json.loads(target_path.read_text()) == target
    geometry = json.loads(GEOMETRY.read_text())
    assert geometry["seed_folded_columns"] == 600
    assert geometry["seed_actual_usable_B"] == 63_600
    assert geometry["multiplier_classes_after_sign_frobenius"] == 10
    env = os.environ.copy()
    env.update({"A1_BASE_POLICY": policy,
                "A1_SKIP_TARGET_EXTRACT": "1",
                "A1_MAX_RELATION_ATTEMPTS": str(args.queries),
                "A1_PROGRESS_PATH": str(progress_path)})
    command = [str(BINARY), "53", "0", "600", "20261008",
               str(target_path), str(raw_path), "1"]
    started = time.perf_counter_ns()
    try:
        proc = subprocess.run(command, env=env, capture_output=True,
                              text=True, timeout=600)
        status = "process_complete" if proc.returncode == 0 else "process_error"
        exit_code = proc.returncode
        stderr_tail = proc.stderr[-2000:]
    except subprocess.TimeoutExpired as error:
        status = "timeout_600s"
        exit_code = None
        stderr_tail = (error.stderr or b"")[-2000:]
        if isinstance(stderr_tail, bytes):
            stderr_tail = stderr_tail.decode(errors="replace")
    wall_ns = time.perf_counter_ns() - started
    record = (json.loads(raw_path.read_text().splitlines()[-1])
              if raw_path.exists() and raw_path.stat().st_size else None)
    progress = (json.loads(progress_path.read_text())
                if progress_path.exists() else None)
    if record is not None:
        assert record["n"] == 53 and record["a"] == 0
        assert record["factor_base_policy"] == policy
        assert record["geometric_folded_columns"] == 600
        assert record["orbit_columns"] == (600 if policy == "seed" else 60)
        assert record["factor_base_points"] == 63_600
        assert record["rank_attempts_completed"] == args.queries
        assert record["skip_target_extract_stage_probe"] is True
        status = "completed_query_cap"
    result = record or progress or {}
    answer = {"schema_version": 1, "proposal_id": "A1",
              "candidate_id": None, "run_id": None,
              "scope": "paired N53 ordinary known-scalar relation-yield stage at equal geometry",
              "status": status, "policy": policy,
              "query_count_cap": args.queries, "workers": 1,
              "relation_seed": 20261008, "target_point": target,
              "factor_base_geometric_columns": 600,
              "factor_base_usable_B": 63_600,
              "independent_log_columns": 600 if policy == "seed" else 60,
              "query_attempts_completed": result.get("rank_attempts_completed"),
              "verified_relations": result.get("rank_verified_relations",
                                               result.get("verified_relations")),
              "novel_rows": result.get("rank_new_rows", result.get("novel_rows")),
              "final_rank": result.get("rank"),
              "index_build_ms_exploratory":
                  record.get("timing_ms", {}).get("index_build") if record else None,
              "peak_rss_bytes": record.get("peak_rss_bytes") if record else None,
              "process_wall_ns_exploratory": wall_ns,
              "timeout_seconds": 600, "process_exit_code": exit_code,
              "stderr_tail": stderr_tail,
              "raw_result_path": raw_path.name,
              "raw_result_sha256": sha(raw_path) if raw_path.exists() else None,
              "progress_path": progress_path.name,
              "progress_sha256": sha(progress_path) if progress_path.exists() else None,
              "source_sha256": sha(Path(__file__)),
              "solver_source_sha256": sha(SOURCE),
              "solver_binary_sha256": sha(BINARY),
              "geometry_receipt_sha256": sha(GEOMETRY),
              "frozen_target_list_sha256": sha(TARGETS)}
    receipt_path.write_text(json.dumps(answer, sort_keys=True, indent=2)+"\n")
    print(json.dumps({k: answer[k] for k in
                      ("policy", "status", "query_attempts_completed",
                       "verified_relations", "novel_rows", "final_rank")}))


if __name__ == "__main__":
    main()
