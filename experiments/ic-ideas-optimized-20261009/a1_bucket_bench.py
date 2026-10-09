#!/usr/bin/env python3
"""Matched index-layout controls with per-child CPU and RSS accounting."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import signal
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "ic-ideas-solver-gates-20261008"
TARGET = PRIOR / "a1_n53_target0.json"
LOGS = PRIOR / "a1_n53_rank_replay.json"
RUNS = HERE / "a1_bucket_runs"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def one(label: str, sequence: int) -> dict:
    binary = HERE / f"{label}_target_probe"
    raw = RUNS / f"{sequence:02d}_{label}.json"
    stdout = RUNS / f"{sequence:02d}_{label}.stdout"
    stderr = RUNS / f"{sequence:02d}_{label}.stderr"
    for path in (raw, stdout, stderr):
        if path.exists():
            raise FileExistsError(path)
    command = [str(binary), "closure", "600", str(TARGET), str(LOGS), str(raw)]
    with stdout.open("w") as out, stderr.open("w") as err:
        started = time.perf_counter_ns()
        process = subprocess.Popen(command, stdout=out, stderr=err)
        deadline = time.monotonic() + 180
        timed_out = False
        while True:
            pid, status, usage = os.wait4(process.pid, os.WNOHANG)
            if pid:
                break
            if time.monotonic() >= deadline:
                process.send_signal(signal.SIGKILL)
                pid, status, usage = os.wait4(process.pid, 0)
                timed_out = True
                break
            time.sleep(0.05)
        wall = time.perf_counter_ns() - started
        code = os.waitstatus_to_exitcode(status)
        process.returncode = code
    payload = json.loads(raw.read_text()) if raw.exists() else None
    rss = usage.ru_maxrss * (1024 if platform.system() == "Linux" else 1)
    return {"label": label, "sequence": sequence,
            "status": "timeout_180s" if timed_out else
                      "process_complete" if code == 0 else "process_error",
            "exit_code": code, "process_wall_ns_exploratory": wall,
            "user_cpu_s_exploratory": usage.ru_utime,
            "system_cpu_s_exploratory": usage.ru_stime,
            "peak_rss_bytes": rss, "binary_sha256": sha(binary),
            "raw_path": raw.name if raw.exists() else None,
            "raw_sha256": sha(raw) if raw.exists() else None,
            "result": payload, "stderr_tail": stderr.read_text()[-1000:]}


def main() -> None:
    output = HERE / "a1_bucket_bench.json"
    if output.exists():
        raise FileExistsError(output)
    RUNS.mkdir(exist_ok=True)
    rows = []
    for sequence, label in enumerate(("control", "bucket", "bucket", "control")):
        rows.append(one(label, sequence))
        (HERE / "a1_bucket_bench.partial.json").write_text(
            json.dumps({"runs": rows}, sort_keys=True, indent=2) + "\n")
        row = rows[-1]
        print(json.dumps({"sequence": sequence, "label": label,
                          "status": row["status"],
                          "index_ms": row["result"].get(
                              "index_build_ms_exploratory") if row["result"] else None,
                          "user_cpu_s": row["user_cpu_s_exploratory"]}), flush=True)
    assert all(row["status"] == "process_complete" for row in rows)
    results = [row["result"] for row in rows]
    for key in ("base_hash_blake3", "target_point", "recovered_scalar",
                "pair_sums", "distinct_pair_x_orbit_keys", "duplicate_pair_keys",
                "actual_usable_B", "independent_log_columns"):
        assert len({json.dumps(result[key], sort_keys=True) for result in results}) == 1, key
    assert all(result["status"] == "verified_recovery" for result in results)
    answer = {"schema_version": 1, "proposal_id": "A1",
              "candidate_id": None, "run_id": None,
              "status": "matched_correctness_pass",
              "timing_class": "exploratory_unisolated",
              "control_source_sha256": sha(HERE / "a1_n53_control/src/bin/target_probe.rs"),
              "bucket_source_sha256": sha(HERE / "a1_n53_bucket_index/src/bin/target_probe.rs"),
              "shared_arithmetic_sha256": sha(HERE / "a1_n53_control/src/main.rs"),
              "target_sha256": sha(TARGET), "logs_sha256": sha(LOGS),
              "driver_sha256": sha(Path(__file__)), "runs": rows}
    output.write_text(json.dumps(answer, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
