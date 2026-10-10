#!/usr/bin/env python3
"""Bound the frozen 80,000-by-64,859 M4RI rank run."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    frozen = json.loads((HERE / "rank_protocol.json").read_text())
    for name, expected in frozen["input_sha256"].items():
        if sha(HERE / name) != expected:
            raise ValueError(f"rank input changed: {name}")
    for name, expected in frozen["source_sha256"].items():
        if sha(HERE / name) != expected:
            raise ValueError(f"rank source changed: {name}")
    result_file = HERE / "rank_result.json"
    control_file = HERE / "rank_control.json"
    if result_file.exists() or control_file.exists():
        raise FileExistsError("preserve first frozen bidegree-rank run")
    start = time.monotonic()
    peak = 0
    status = "RUNNING"
    stdout_path, stderr_path = HERE / "rank.stdout", HERE / "rank.stderr"
    with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
        process = subprocess.Popen([
            str(HERE / "rank"), str(HERE / "sample.bin"), str(result_file)],
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
            if peak >= frozen["limits"]["rss_bytes"]:
                status = "MEMORY_CAP"
                process.kill()
                exit_code = process.wait()
                break
            if time.monotonic() - start >= frozen["limits"]["rank_wall_seconds"]:
                status = "TIME_CAP"
                process.kill()
                exit_code = process.wait()
                break
            time.sleep(0.25)
    if status == "EXIT_SUCCESS" and not result_file.exists():
        status = "MISSING_OUTPUT"
    receipt = {
        "status": status, "exit_code": exit_code,
        "wall_seconds": time.monotonic() - start,
        "observed_peak_rss_bytes": peak,
        "rank_result_sha256": sha(result_file) if result_file.exists() else None,
        "rank_binary_sha256": sha(HERE / "rank"),
        "rank_protocol_sha256": sha(HERE / "rank_protocol.json"),
        "runner_sha256": sha(Path(__file__)),
        "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path),
    }
    control_file.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
