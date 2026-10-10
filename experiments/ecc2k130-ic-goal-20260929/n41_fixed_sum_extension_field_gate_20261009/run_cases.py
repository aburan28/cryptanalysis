#!/usr/bin/env python3
"""Bound checked-Sage Groebner processes and preserve all terminal states."""

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

import psutil

HERE = Path(__file__).resolve().parent
LAUNCHER = Path("/Volumes/SSD990/cryptanalysis/sage")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN"
    assert sha(HERE / "run_cases.py") == protocol["sha256"]["supervisor"]
    limit_ns = protocol["limits"]["per_case_seconds"] * 10**9
    rss_limit = protocol["limits"]["combined_rss_bytes"]
    for case in ("positive", "negative"):
        directory = HERE / case
        directory.mkdir(exist_ok=True)
        terminal = directory / "terminal.json"
        if terminal.exists():
            raise FileExistsError(terminal)
        command = [str(LAUNCHER), "-python", str(HERE / "solve.py"), case]
        stdout_path = directory / "stdout.txt"
        stderr_path = directory / "stderr.txt"
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            started = time.monotonic_ns()
            proc = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                    cwd=HERE, start_new_session=True)
            peak = 0
            guard = None
            while proc.poll() is None:
                try:
                    p = psutil.Process(proc.pid)
                    try:
                        family = [p] + p.children(recursive=True)
                    except (PermissionError, OSError):
                        # The managed macOS sandbox can deny global PID census.
                        # The checked launcher execs the Sage process in place.
                        family = [p]
                    rss = sum(x.memory_info().rss for x in family if x.is_running())
                    peak = max(peak, rss)
                except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError):
                    pass
                if peak >= rss_limit:
                    guard = "MEMORY_GUARD"
                elif time.monotonic_ns() - started >= limit_ns:
                    guard = "WALL_CAP"
                if guard:
                    try:
                        os.killpg(proc.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(proc.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    break
                time.sleep(0.05)
            returncode = proc.wait()
            wall_ns = time.monotonic_ns() - started
        result = directory / "result.json"
        if guard is not None:
            status = guard
        elif returncode != 0 or not result.exists():
            status = "PRODUCER_FAILURE"
        else:
            status = json.loads(result.read_text())["status"]
        receipt = {
            "case": case, "status": status, "command": command,
            "returncode": returncode, "launcher_wall_ns": wall_ns,
            "peak_sampled_family_rss_bytes": peak,
            "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path),
            "result_sha256": sha(result) if result.exists() else None,
            "protocol_sha256": sha(HERE / "protocol.json"),
        }
        terminal.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"case": case, "status": status,
                          "wall_ns": wall_ns, "peak_rss_bytes": peak}), flush=True)


if __name__ == "__main__":
    main()
