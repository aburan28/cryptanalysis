#!/usr/bin/env python3
"""Freeze exact work for an unsuccessful, checkpointed n83 rho attempt."""

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from verify_n83_public_target_rho import CURVE_ID, digest, worker_result

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-log", type=Path, action="append", required=True)
    parser.add_argument("--worker-binary", type=Path, action="append", required=True)
    parser.add_argument("--worker-driver-source", type=Path, action="append",
                        required=True)
    parser.add_argument("--worker-dp", type=Path, action="append", required=True)
    parser.add_argument("--worker-checkpoint", type=Path, action="append",
                        required=True)
    parser.add_argument("--worker-run-id", type=int, action="append",
                        required=True)
    parser.add_argument("--merge-log", type=Path, required=True)
    parser.add_argument("--rho-source", type=Path, required=True)
    parser.add_argument("--generated-header", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    groups = (args.worker_log, args.worker_binary,
              args.worker_driver_source, args.worker_dp,
              args.worker_checkpoint, args.worker_run_id)
    if len(set(map(len, groups))) != 1 or len(set(args.worker_run_id)) != len(
            args.worker_run_id):
        raise SystemExit("each distinct worker needs all five artifacts and a run ID")
    reference_path = HERE / "runs" / "n83_perf_prefix.json"
    reference = json.loads(reference_path.read_text())
    assert reference["curve_id"] == CURVE_ID
    target = reference["workload"]["target"]
    workers = []
    for log, binary, driver, dp, checkpoint, run_id in zip(*groups):
        worker = worker_result(log, binary, driver, run_id)
        assert worker["status"] == "stopped"
        assert "  k = " not in log.read_text()
        size = dp.stat().st_size
        assert size % 32 == 0
        assert size // 32 == worker["distinguished_points"]
        worker["dp_records"] = size // 32
        worker["dp_corpus_sha256"] = digest(dp)
        worker["checkpoint_bytes"] = checkpoint.stat().st_size
        worker["checkpoint_sha256"] = digest(checkpoint)
        workers.append(worker)
    merge = args.merge_log.read_text()
    match = re.search(r"reloaded (\d+) points from (\d+) file\(s\), "
                      r"(\d+) distinct orbits", merge)
    assert match is not None
    reloaded, files, distinct = map(int, match.groups())
    assert files == len(workers)
    assert reloaded == distinct == sum(w["dp_records"] for w in workers)
    assert "collision found" not in merge and "  k = " not in merge
    assert "finished:" in merge
    total = sum(int(w["walk_iterations"]) for w in workers)
    workload = {
        "curve_id": CURVE_ID,
        "target": target,
        "target_count": 1,
        "walk": "signed-Frobenius rho CPU engine",
        "worker_run_ids": args.worker_run_id,
        "dp_weight": 22,
        "threads_per_worker": 4,
        "steps_per_launch": 512,
    }
    workload_id = hashlib.sha256(json.dumps(
        workload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12]
    report = {
        "kind": "n83_public_target_rho_stopped_attempt",
        "scope": "exact charged rho walk iterations, all DP records, complete cross-worker corpus merge; no recovered scalar or IC relation",
        "curve_id": CURVE_ID,
        "curve_identity_record": reference["curve_identity_record"],
        "isogeny": "none",
        "workload_id": workload_id,
        "workload": workload,
        "public_generator": reference["curve_identity_record"]["curve"][
            "generator"],
        "public_target": target,
        "subgroup_order": reference["subgroup_order"],
        "workers": workers,
        "total_rho_walk_iterations": str(total),
        "total_rho_walk_iterations_log2": math.log2(total),
        "distinct_dp_orbits_after_full_merge": distinct,
        "full_merge_log_sha256": digest(args.merge_log),
        "recovered_scalar": None,
        "verified_single_target_dlp": False,
        "ordinary_factor_base_relation_yield": None,
        "complete_IC_work_log2": None,
        "work_boundary": "all three workers' walk iterations, including failed work; excludes corpus hashing, setup and replay; no solved-log work claim",
        "reference_sha256": digest(reference_path),
        "rho_source_sha256": digest(args.rho_source),
        "generated_header_sha256": digest(args.generated_header),
        "portable_driver_source_sha256": digest(
            HERE / "n83_public_target_rho.cpp"),
        "source_sha256": digest(Path(__file__)),
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"workload_id": workload_id,
                      "walk_iterations": str(total),
                      "walk_iterations_log2": report[
                          "total_rho_walk_iterations_log2"],
                      "distinct_dp_orbits": distinct,
                      "verified_single_target_dlp": False}))


if __name__ == "__main__":
    main()
