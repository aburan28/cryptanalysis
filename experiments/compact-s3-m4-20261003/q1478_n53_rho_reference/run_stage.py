#!/usr/bin/env python3
"""Run Q1478's frozen one-target rho workload once."""

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
    assert protocol == render(), "frozen Q1478 protocol changed"
    assert not RUN.exists(), "refuse to overwrite frozen rho run"
    RUN.mkdir(parents=True)
    command = [str(HERE / "rho_reference"),
               str(PARENT / "q1420_root_theory/n53_field.txt"),
               str(PARENT / "q1477_n53_online_target/target.txt")]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.monotonic_ns()
    try:
        completed = subprocess.run(command, capture_output=True,
                                   timeout=1850, check=False)
        stdout, stderr = completed.stdout, completed.stderr
        code = completed.returncode
        timed_out = False
    except subprocess.TimeoutExpired as error:
        stdout, stderr = error.stdout or b"", error.stderr or b""
        code, timed_out = None, True
    external_wall_ns = time.monotonic_ns() - start
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    (RUN / "stdout.json").write_bytes(stdout)
    (RUN / "stderr.txt").write_bytes(stderr)
    report = None
    try:
        report = json.loads(stdout)
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    status = ("verified" if code == 0 and report and
              report["status"] == "verified" else
              "censored" if code == 10 and report and
              report["status"] == "censored" else
              "external_timeout" if timed_out else "native_failure")
    receipt = {
        "kind": "q1478_one_target_rho_run", "proposal_id": "Q1478",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "rho_reference_id": protocol["rho_reference_id"],
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
        "native_stdout_sha256": sha(RUN / "stdout.json"),
        "native_stderr_sha256": sha(RUN / "stderr.txt"),
        "online_report_present": report is not None,
        "status": status,
    }
    (RUN / "receipt.json").write_text(json.dumps(receipt, sort_keys=True,
                                                  indent=2) + "\n")
    print(json.dumps({"status": status, "native_exit_code": code,
                      "online_report_present": report is not None}),
          flush=True)


if __name__ == "__main__":
    main()
