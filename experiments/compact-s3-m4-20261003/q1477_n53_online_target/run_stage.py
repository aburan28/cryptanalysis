#!/usr/bin/env python3
"""Run the frozen Q1477 native one-target workload once."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import time
from pathlib import Path

from freeze_protocol import render

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
RUN = HERE / "runs/primary"
PROTOCOL = HERE / "protocol.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    assert args.run
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol == render(), "frozen Q1477 protocol changed"
    assert not RUN.exists(), "refuse to rerun or overwrite frozen result"
    RUN.mkdir(parents=True)
    command = [
        str(HERE / "online_oracle"),
        str(PARENT / "q1420_root_theory/n53_field.txt"),
        str(PARENT / "q1468_n53_pair_oracle/inputs/base_points.txt"),
        str(HERE / "base_logs.txt"), str(HERE / "target.txt"),
        str(protocol["per_query_wall_cap_seconds"]),
        str(protocol["online_wall_cap_seconds"]),
    ]
    start = time.monotonic_ns()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    try:
        completed = subprocess.run(command, capture_output=True,
                                   timeout=1260, check=False)
        stdout, stderr = completed.stdout, completed.stderr
        code = completed.returncode
        timed_out = False
    except subprocess.TimeoutExpired as error:
        stdout, stderr = error.stdout or b"", error.stderr or b""
        code = None
        timed_out = True
    external_wall_ns = time.monotonic_ns() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    (RUN / "stdout.ndjson").write_bytes(stdout)
    (RUN / "stderr.txt").write_bytes(stderr)
    rows = []
    try:
        rows = [json.loads(line) for line in stdout.splitlines()]
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    result = rows[-1] if rows and rows[-1].get("mode") == "online" else None
    receipt = {
        "kind": "q1477_n53_one_target_run", "proposal_id": "Q1477",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "stage_config_id": protocol["stage_config_id"],
        "stage_run_id": protocol["stage_run_id"],
        "workload_id": protocol["workload_id"],
        "protocol_sha256": sha(PROTOCOL),
        "runner_source_sha256": sha(Path(__file__)),
        "command": command, "native_exit_code": code,
        "external_safeguard_timeout": timed_out,
        "external_wall_ns_exploratory": external_wall_ns,
        "peak_child_rss_raw": after.ru_maxrss,
        "peak_child_rss_units": "bytes on macOS; platform-specific raw ru_maxrss otherwise",
        "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
        "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
        "native_stdout_sha256": sha(RUN / "stdout.ndjson"),
        "native_stderr_sha256": sha(RUN / "stderr.txt"),
        "setup_report": rows[0] if rows and rows[0].get("mode") ==
            "setup" else None,
        "online_report_present": result is not None,
        "status": "verified" if code == 0 and result and
            result["status"] == "verified" else
            "unsolved" if code == 0 and result else
            "timeout" if timed_out else "native_failure",
    }
    (RUN / "receipt.json").write_text(json.dumps(receipt, sort_keys=True,
                                                  indent=2) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "native_exit_code": code,
                      "online_report_present": result is not None}),
          flush=True)


if __name__ == "__main__":
    main()
