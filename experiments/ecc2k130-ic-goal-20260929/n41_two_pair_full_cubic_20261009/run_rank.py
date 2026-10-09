#!/usr/bin/env python3
"""Bound the frozen rank binary and preserve its exit status and resource peak."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    control_path = HERE / "rank_control.json"
    result_path = HERE / "rank.json"
    if control_path.exists() or result_path.exists():
        raise FileExistsError("preserve first frozen rank result")
    protocol = json.loads((HERE / "protocol.json").read_text())
    production = json.loads((HERE / "production.json").read_text())
    rows_path = HERE / "rows.bin"
    binary = HERE / "rank"
    if (digest(binary) != protocol["source_sha256"]["rank"] or
            digest(rows_path) != production["rows_sha256"] or
            production["rows"] != protocol["row_count"] or
            production["source_sha256"]["protocol"] != digest(HERE / "protocol.json")):
        raise ValueError("rank input or binary differs from frozen receipt")
    start = time.monotonic()
    deadline = start + protocol["limits"]["rank_wall_seconds"]
    rss_cap = protocol["limits"]["rss_bytes"]
    peak = 0
    status = "RUNNING"
    out_path, err_path = HERE / "rank.stdout", HERE / "rank.stderr"
    with out_path.open("x") as stdout, err_path.open("x") as stderr:
        process = subprocess.Popen([str(binary), str(rows_path), str(result_path)],
                                   cwd=HERE, stdout=stdout, stderr=stderr)
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
            if peak >= rss_cap:
                status = "MEMORY_CAP"
                process.kill()
                exit_code = process.wait()
                break
            if time.monotonic() >= deadline:
                status = "TIME_CAP"
                process.kill()
                exit_code = process.wait()
                break
            time.sleep(0.25)
    if status == "EXIT_SUCCESS" and not result_path.exists():
        status = "MISSING_RESULT"
    receipt = {"status": status, "exit_code": exit_code,
               "wall_seconds": time.monotonic() - start,
               "observed_peak_rss_bytes": peak,
               "rank_result_sha256": digest(result_path) if result_path.exists() else None,
               "rows_sha256": digest(rows_path), "binary_sha256": digest(binary),
               "runner_sha256": digest(Path(__file__)),
               "stdout_sha256": digest(out_path), "stderr_sha256": digest(err_path)}
    control_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
