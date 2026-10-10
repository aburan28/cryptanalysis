#!/usr/bin/env python3
"""Run one frozen exact six-block join and retain every terminal outcome."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

from freeze import source_paths

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    if (protocol["status"] != "FROZEN" or
            protocol["source_sha256"] != {
                key: sha(path) for key, path in source_paths().items()}):
        raise ValueError("frozen source changed")
    receipt_path = HERE / "run_receipt.json"
    result_path = HERE / "result.json"
    stdout_path, stderr_path = HERE / "join.stdout.txt", HERE / "join.stderr.txt"
    if any(path.exists() for path in
           (receipt_path, result_path, stdout_path, stderr_path)):
        raise FileExistsError("preserve first frozen run")
    command = [str(HERE / "join"), str(HERE / "input.txt"),
               str(result_path), str(protocol["wall_cap_seconds"])]
    started = time.monotonic_ns()
    with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, cwd=HERE)
        try:
            exit_code = process.wait(timeout=protocol["wall_cap_seconds"] + 5)
            guard = "EXIT"
        except subprocess.TimeoutExpired:
            process.kill()
            exit_code = process.wait()
            guard = "PARENT_WALL_CAP"
    elapsed = time.monotonic_ns() - started
    result = json.loads(result_path.read_text()) if result_path.exists() else None
    status = result["status"] if result and exit_code == 0 else "PRODUCER_FAILURE"
    receipt = {"status": status, "exit_code": exit_code, "terminal_guard": guard,
               "process_wall_ns": elapsed, "command": command,
               "protocol_sha256": sha(HERE / "protocol.json"),
               "source_sha256": protocol["source_sha256"],
               "result_sha256": sha(result_path) if result else None,
               "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path)}
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status, "exit_code": exit_code,
                      "process_wall_ns": elapsed,
                      "native_result": result}, sort_keys=True))


if __name__ == "__main__":
    main()
