#!/usr/bin/env python3
"""Run one frozen rank method with a parent wall and RSS guard."""

import json
import subprocess
import sys
import time
from pathlib import Path

import psutil
import freeze

HERE = Path(__file__).resolve().parent


def main(method):
    if method not in ("rank", "audit_rank"):
        raise ValueError("method must be rank or audit_rank")
    protocol_path = HERE / "rank_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    if (protocol["status"] != "FROZEN" or
            protocol["sample_sha256"] != freeze.sha(HERE / "sample.bin") or
            any(freeze.sha(HERE / name) != expected
                for name, expected in protocol["source_sha256"].items())):
        raise ValueError("frozen rank source or sample changed")
    result_path = HERE / f"{method}_result.json"
    control_path = HERE / f"{method}_control.json"
    if method == "rank":
        result_path = HERE / "rank_result.json"
    if result_path.exists() or control_path.exists():
        raise FileExistsError("preserve first frozen rank method result")
    stdout_path = HERE / f"{method}.stdout"
    stderr_path = HERE / f"{method}.stderr"
    start = time.monotonic()
    status = "RUNNING"
    peak = 0
    with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
        process = subprocess.Popen([str(HERE / method), str(HERE / "sample.bin"),
                                    str(result_path)], cwd=HERE, stdout=stdout,
                                   stderr=stderr)
        observed = psutil.Process(process.pid)
        while True:
            exit_code = process.poll()
            if exit_code is not None:
                status = "EXIT_SUCCESS" if exit_code == 0 else "EXIT_FAILURE"
                break
            try:
                peak = max(peak, observed.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            if peak > protocol["rss_cap_bytes"]:
                status = "MEMORY_CAP"
                process.kill()
                exit_code = process.wait()
                break
            if time.monotonic() - start > protocol["per_method_wall_cap_seconds"]:
                status = "TIME_CAP"
                process.kill()
                exit_code = process.wait()
                break
            time.sleep(0.1)
    if status == "EXIT_SUCCESS" and not result_path.exists():
        status = "MISSING_RESULT"
    control = {"status": status, "method": method, "exit_code": exit_code,
               "wall_seconds": time.monotonic() - start,
               "observed_peak_rss_bytes": peak,
               "result_sha256": freeze.sha(result_path) if result_path.exists() else None,
               "binary_sha256": freeze.sha(HERE / method),
               "protocol_sha256": freeze.sha(protocol_path),
               "runner_sha256": freeze.sha(Path(__file__)),
               "stdout_sha256": freeze.sha(stdout_path),
               "stderr_sha256": freeze.sha(stderr_path)}
    control_path.write_text(json.dumps(control, indent=2, sort_keys=True) + "\n")
    print(json.dumps(control, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: run_rank.py rank|audit_rank")
    main(sys.argv[1])
