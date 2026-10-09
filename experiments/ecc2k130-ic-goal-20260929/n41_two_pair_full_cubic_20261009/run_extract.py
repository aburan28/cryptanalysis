#!/usr/bin/env python3
"""Run one bounded RREF extraction and retain timeout or memory status."""

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
    protocol = json.loads((HERE / "extract_protocol.json").read_text())
    for name, expected in protocol["input_sha256"].items():
        if digest(HERE / name) != expected:
            raise ValueError(f"extraction input changed: {name}")
    for name in ("extract.cpp", "extract"):
        if digest(HERE / name) != protocol["source_sha256"][name]:
            raise ValueError(f"extraction source changed: {name}")
    output = HERE / "equations.json"
    receipt = HERE / "extract_control.json"
    if output.exists() or receipt.exists():
        raise FileExistsError("preserve first extraction execution")
    start = time.monotonic()
    peak = 0
    status = "RUNNING"
    stdout_path, stderr_path = HERE / "extract.stdout", HERE / "extract.stderr"
    with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
        process = subprocess.Popen([str(HERE / "extract"), str(HERE / "rows.bin"),
                                    str(output)], cwd=HERE, stdout=stdout, stderr=stderr)
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
    if status == "EXIT_SUCCESS" and not output.exists():
        status = "MISSING_RESULT"
    record = {"status": status, "exit_code": exit_code,
              "wall_seconds": time.monotonic() - start,
              "observed_peak_rss_bytes": peak,
              "equations_sha256": digest(output) if output.exists() else None,
              "extract_protocol_sha256": digest(HERE / "extract_protocol.json"),
              "extract_binary_sha256": digest(HERE / "extract"),
              "runner_sha256": digest(Path(__file__)),
              "stdout_sha256": digest(stdout_path), "stderr_sha256": digest(stderr_path)}
    receipt.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    main()
