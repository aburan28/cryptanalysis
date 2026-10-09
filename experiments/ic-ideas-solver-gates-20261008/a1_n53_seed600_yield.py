#!/usr/bin/env python3
"""Bounded ordinary-query relation-yield run for the frozen N53 600-column base."""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CRYPTO = Path("/Volumes/SSD990/crypto")
SOURCE = CRYPTO / "examples/koblitz_orbit_dlp_slice_ic_fastindex.rs"
BINARY = CRYPTO / "target/release/examples/koblitz_orbit_dlp_slice_ic_fastindex"
TARGETS = (REPO / "experiments/koblitz-n53-fastindex4-streaming-cert-20260930-v3-rho-online-accounting"
           / "input/target_points.jsonl")
GEOMETRY = (REPO / "experiments/ic-ideas-20261007/results"
            / "a1_n53_k600_followup_final.json")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    receipt_path = HERE / "a1_n53_seed600_yield.json"
    target_path = HERE / "a1_n53_target0.json"
    raw_path = HERE / "a1_n53_seed600_raw.jsonl"
    if any(path.exists() for path in (receipt_path, target_path, raw_path)):
        raise FileExistsError("preserve prior N53 run artifacts")
    geometry = json.loads(GEOMETRY.read_text())
    assert geometry["seed_folded_columns"] == 600
    target = json.loads(TARGETS.read_text().splitlines()[0])
    assert isinstance(target, list) and len(target) == 2
    target_path.write_text(json.dumps(target, separators=(",", ":")) + "\n")
    command = [str(BINARY), "53", "0", "600", "20261008",
               str(target_path), str(raw_path), "1"]
    started = time.perf_counter_ns()
    try:
        proc = subprocess.run(command, capture_output=True, text=True,
                              timeout=600)
        exit_code = proc.returncode
        stderr_tail = proc.stderr[-2000:]
        run_status = "process_complete" if exit_code == 0 else "process_error"
    except subprocess.TimeoutExpired as error:
        exit_code = None
        stderr_tail = (error.stderr or b"")[-2000:]
        if isinstance(stderr_tail, bytes):
            stderr_tail = stderr_tail.decode(errors="replace")
        run_status = "timeout_600s"
    wall_ns = time.perf_counter_ns()-started
    record = None
    if raw_path.exists() and raw_path.stat().st_size:
        record = json.loads(raw_path.read_text().splitlines()[-1])
    if record is not None:
        assert record["n"] == 53 and record["a"] == 0
        assert record["orbit_columns"] == 600
        assert record["factor_base_points"] == geometry["seed_actual_usable_B"]
        assert record["target"] == target
        run_status = ("completed_verified" if record.get("group_verified") is True
                      else "completed_unverified")
    answer = {"schema_version": 1, "proposal_id": "A1",
              "candidate_id": None, "run_id": None,
              "scope": "N53 frozen 600-column seed-base ordinary-query yield stage",
              "status": run_status, "process_exit_code": exit_code,
              "process_wall_ns_exploratory": wall_ns,
              "timeout_seconds": 600, "workers": 1,
              "target_point": target, "relation_seed": 20261008,
              "factor_base_folded_columns": 600,
              "factor_base_usable_B": geometry["seed_actual_usable_B"],
              "rank_attempts": record.get("rank_attempts") if record else None,
              "verified_relations": record.get("rank_verified_relations") if record else None,
              "novel_rows": record.get("rank_new_rows") if record else None,
              "final_rank": record.get("rank") if record else None,
              "target_relation_found": record.get("target_relation_found") if record else None,
              "group_verified": record.get("group_verified") if record else None,
              "peak_rss_bytes": record.get("peak_rss_bytes") if record else None,
              "stderr_tail": stderr_tail,
              "raw_result_path": raw_path.name,
              "raw_result_sha256": sha(raw_path) if raw_path.exists() else None,
              "target_fixture_sha256": sha(target_path),
              "frozen_target_list_sha256": sha(TARGETS),
              "geometry_receipt_sha256": sha(GEOMETRY),
              "source_sha256": sha(Path(__file__)),
              "solver_source_sha256": sha(SOURCE),
              "solver_binary_sha256": sha(BINARY)}
    receipt_path.write_text(json.dumps(answer, sort_keys=True, indent=2)+"\n")
    print(json.dumps({k: answer[k] for k in ("status", "rank_attempts",
                                               "verified_relations", "novel_rows",
                                               "final_rank", "group_verified")}))


if __name__ == "__main__":
    main()
