#!/usr/bin/env python3
"""Peak RSS for the equal-size N53 pair indexes under a 300-second cap."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BINARY = HERE / "a1_n53_closure/target/release/pair_probe"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", choices=("seed", "closure"), required=True)
    args = parser.parse_args()
    out = HERE / f"a1_n53_memory_{args.policy}.json"
    raw = HERE / f"a1_n53_memory_{args.policy}_raw.json"
    progress = HERE / f"a1_n53_memory_{args.policy}_progress.json"
    if any(path.exists() for path in (out, raw, progress)):
        raise FileExistsError("preserve prior memory probe artifacts")
    env = os.environ.copy()
    env["A1_PAIR_PROGRESS_PATH"] = str(progress)
    started = time.perf_counter_ns()
    try:
        process = subprocess.run([str(BINARY), args.policy, "600", "1", str(raw)],
                                 env=env, capture_output=True, text=True,
                                 timeout=300)
        status = "completed" if process.returncode == 0 else "process_error"
        exit_code = process.returncode
        stderr_tail = process.stderr[-2000:]
    except subprocess.TimeoutExpired as error:
        status = "timeout_300s"
        exit_code = None
        stderr_tail = error.stderr or b""
        if isinstance(stderr_tail, bytes):
            stderr_tail = stderr_tail[-2000:].decode(errors="replace")
    peak_rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    record = json.loads(raw.read_text()) if raw.exists() else None
    if record is not None:
        assert record["policy"] == args.policy
        assert record["geometric_columns"] == 600
        assert record["actual_usable_B"] == 63_600
        status = "completed_verified"
    answer = {"schema_version": 1, "proposal_id": "A1",
              "candidate_id": None, "run_id": None,
              "policy": args.policy, "status": status,
              "geometric_columns": 600, "actual_usable_B": 63_600,
              "query_count": 1,
              "peak_rss_bytes": peak_rss,
              "process_wall_ns_exploratory": time.perf_counter_ns()-started,
              "index_build_ms_exploratory":
                  record.get("index_build_ms_exploratory") if record else None,
              "distinct_pair_x_orbit_keys":
                  record.get("distinct_pair_x_orbit_keys") if record else None,
              "process_exit_code": exit_code,
              "stderr_tail": stderr_tail,
              "raw_record": raw.name if raw.exists() else None,
              "raw_sha256": sha(raw) if raw.exists() else None,
              "progress_record": progress.name if progress.exists() else None,
              "progress_sha256": sha(progress) if progress.exists() else None,
              "source_sha256": sha(Path(__file__)),
              "pair_source_sha256": sha(
                  HERE / "a1_n53_closure/src/bin/pair_probe.rs"),
              "binary_sha256": sha(BINARY)}
    out.write_text(json.dumps(answer, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"policy": args.policy, "status": status,
                      "peak_rss_bytes": peak_rss}))


if __name__ == "__main__":
    main()
