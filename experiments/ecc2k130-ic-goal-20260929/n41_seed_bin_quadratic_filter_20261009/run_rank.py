#!/usr/bin/env python3
"""Bound one frozen M4RI bin-rank execution and preserve its status."""

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
    protocol = json.loads((HERE / "rank_protocol.json").read_text())
    for name, expected in protocol["input_sha256"].items():
        if sha(HERE / name) != expected:
            raise ValueError(f"rank input changed: {name}")
    for name in ("rank_filter.cpp", "rank_filter"):
        if sha(HERE / name) != protocol["source_sha256"][name]:
            raise ValueError(f"rank source changed: {name}")
    filter_file = HERE / "filters.bin"
    result_file = HERE / "rank_result.json"
    control_file = HERE / "rank_control.json"
    if any(path.exists() for path in (filter_file, result_file, control_file)):
        raise FileExistsError("preserve first frozen rank execution")
    start = time.monotonic()
    peak = 0
    status = "RUNNING"
    stdout_path, stderr_path = HERE / "rank.stdout", HERE / "rank.stderr"
    with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
        process = subprocess.Popen([str(HERE / "rank_filter"), str(HERE / "x_orbits.bin"),
                                    str(filter_file), str(result_file)],
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
            if peak >= protocol["limits"]["rss_bytes"]:
                status = "MEMORY_CAP"
                process.kill()
                exit_code = process.wait()
                break
            if time.monotonic() - start >= protocol["limits"]["wall_seconds"]:
                status = "TIME_CAP"
                process.kill()
                exit_code = process.wait()
                break
            time.sleep(0.25)
    if status == "EXIT_SUCCESS" and not (filter_file.exists() and result_file.exists()):
        status = "MISSING_OUTPUT"
    receipt = {"status": status, "exit_code": exit_code,
               "wall_seconds": time.monotonic() - start,
               "observed_peak_rss_bytes": peak,
               "filters_sha256": sha(filter_file) if filter_file.exists() else None,
               "rank_result_sha256": sha(result_file) if result_file.exists() else None,
               "rank_binary_sha256": sha(HERE / "rank_filter"),
               "rank_protocol_sha256": sha(HERE / "rank_protocol.json"),
               "runner_sha256": sha(Path(__file__)),
               "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path)}
    control_file.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
