#!/usr/bin/env python3
"""Bound the frozen public-point quadratic filter and preserve all outputs."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
HELPER = HERE / "../n131_w18_four_pairs/native_join/frozen_source/helper.cpp"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    frozen = json.loads((HERE / "query_protocol.json").read_text())
    for name, expected in frozen["input_sha256"].items():
        if sha(HERE / name) != expected:
            raise ValueError(f"query input changed: {name}")
    for name in ("query_filter.cpp", "query_filter", "make_input.py"):
        if sha(HERE / name) != frozen["source_sha256"][name]:
            raise ValueError(f"query source changed: {name}")
    if sha(HELPER) != frozen["helper_sha256"]:
        raise ValueError("arithmetic helper changed")
    public = json.loads((HERE / "public_input_receipt.json").read_text())
    if (public["query_protocol_sha256"] != sha(HERE / "query_protocol.json") or
            public["public_input_sha256"] != sha(HERE / "public_input.txt")):
        raise ValueError("public input changed")
    residual_file = HERE / "residuals.bin"
    result_file = HERE / "query_result.json"
    control_file = HERE / "query_control.json"
    if any(path.exists() for path in (residual_file, result_file, control_file)):
        raise FileExistsError("preserve first frozen query execution")
    start = time.monotonic()
    peak = 0
    status = "RUNNING"
    stdout_path, stderr_path = HERE / "query.stdout", HERE / "query.stderr"
    with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
        process = subprocess.Popen([
            str(HERE / "query_filter"), str(HERE / "public_input.txt"),
            str(HERE / "filters.bin"), str(frozen["valid_prefix_cap"]),
            str(residual_file), str(result_file)],
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
            if time.monotonic() - start >= frozen["limits"]["query_wall_seconds"] + 5:
                status = "TIME_CAP"
                process.kill()
                exit_code = process.wait()
                break
            time.sleep(0.25)
    if status == "EXIT_SUCCESS" and not (residual_file.exists() and result_file.exists()):
        status = "MISSING_OUTPUT"
    receipt = {
        "status": status, "exit_code": exit_code,
        "wall_seconds_including_setup": time.monotonic() - start,
        "observed_peak_rss_bytes": peak,
        "residuals_sha256": sha(residual_file) if residual_file.exists() else None,
        "query_result_sha256": sha(result_file) if result_file.exists() else None,
        "public_input_sha256": sha(HERE / "public_input.txt"),
        "query_binary_sha256": sha(HERE / "query_filter"),
        "query_protocol_sha256": sha(HERE / "query_protocol.json"),
        "runner_sha256": sha(Path(__file__)),
        "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path),
    }
    control_file.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
