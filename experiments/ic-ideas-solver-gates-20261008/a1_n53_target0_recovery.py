#!/usr/bin/env python3
"""Bounded direct decomposition and scalar replay for frozen public N53 Q0."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE / "a1_n53_closure"
BINARY = PACKAGE / "target/release/target_probe"
TARGET = HERE / "a1_n53_target0.json"
LOGS = HERE / "a1_n53_rank_replay.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    out = HERE / "a1_n53_target0_recovery.json"
    raw = HERE / "a1_n53_target0_recovery_raw.json"
    progress = HERE / "a1_n53_target0_recovery_progress.json"
    if any(path.exists() for path in (out, raw, progress)):
        raise FileExistsError("preserve prior target recovery artifacts")
    logs = json.loads(LOGS.read_text())
    assert logs["full_rank"] and len(logs["solved_seed_logs"]) == 60
    target = json.loads(TARGET.read_text())
    assert len(target) == 2
    env = os.environ.copy()
    env["A1_PAIR_PROGRESS_PATH"] = str(progress)
    command = [str(BINARY), "closure", "600", str(TARGET), str(LOGS), str(raw)]
    started = time.perf_counter_ns()
    try:
        process = subprocess.run(command, env=env, capture_output=True,
                                 text=True, timeout=1200)
        status = "process_complete" if process.returncode == 0 else "process_error"
        exit_code = process.returncode
        stderr_tail = process.stderr[-2000:]
    except subprocess.TimeoutExpired as error:
        status = "timeout_1200s"
        exit_code = None
        stderr_tail = error.stderr or b""
        if isinstance(stderr_tail, bytes):
            stderr_tail = stderr_tail[-2000:].decode(errors="replace")
    record = json.loads(raw.read_text()) if raw.exists() else None
    checkpoint = json.loads(progress.read_text()) if progress.exists() else None
    if record is not None:
        assert record["target_point"] == target
        assert record["actual_usable_B"] == 63_600
        assert record["independent_log_columns"] == 60
        assert record["charged_online_ns_exploratory"] == sum(
            record["phase_ns_exploratory"].values())
        status = record["status"]
    answer = {"schema_version": 1, "proposal_id": "A1",
              "candidate_id": None, "run_id": None,
              "scope": "one frozen public-point target descent with precomputed closure logs",
              "status": status,
              "target_point": target,
              "recovered_scalar": record.get("recovered_scalar") if record else None,
              "witness_indices": record.get("witness_indices") if record else None,
              "target_lookups": record.get("lookups") if record else None,
              "charged_online_ns_exploratory":
                  record.get("charged_online_ns_exploratory") if record else None,
              "phase_ns_exploratory":
                  record.get("phase_ns_exploratory") if record else None,
              "process_wall_ns_exploratory": time.perf_counter_ns()-started,
              "timeout_seconds": 1200,
              "process_exit_code": exit_code, "stderr_tail": stderr_tail,
              "checkpoint": checkpoint,
              "raw_record": raw.name if raw.exists() else None,
              "raw_sha256": sha(raw) if raw.exists() else None,
              "progress_record": progress.name if progress.exists() else None,
              "progress_sha256": sha(progress) if progress.exists() else None,
              "target_sha256": sha(TARGET), "log_receipt_sha256": sha(LOGS),
              "source_sha256": sha(Path(__file__)),
              "target_source_sha256": sha(PACKAGE / "src/bin/target_probe.rs"),
              "shared_source_sha256": sha(PACKAGE / "src/main.rs"),
              "build_source_sha256": sha(PACKAGE / "build.rs"),
              "cargo_lock_sha256": sha(PACKAGE / "Cargo.lock"),
              "binary_sha256": sha(BINARY)}
    out.write_text(json.dumps(answer, sort_keys=True, indent=2) + "\n")
    print(json.dumps({key: answer[key] for key in
                      ("status", "recovered_scalar", "target_lookups",
                       "charged_online_ns_exploratory")}))


if __name__ == "__main__":
    main()
