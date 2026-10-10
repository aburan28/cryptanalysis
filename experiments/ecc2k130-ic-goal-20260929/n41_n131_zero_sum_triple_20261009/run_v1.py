#!/usr/bin/env python3
"""Run frozen native zero-sum triple control and public queries."""

import hashlib
import json
from pathlib import Path
import subprocess
import time

import psutil

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN"
    assert protocol["sha256"]["runner"] == sha(__file__)
    assert protocol["sha256"]["join_binary"] == sha(HERE / "join")
    for mode in ("control", "public"):
        input_path = HERE / f"input_{mode}.txt"
        assert protocol["sha256"][f"input_{mode}"] == sha(input_path)
        out = HERE / mode
        out.mkdir(exist_ok=True)
        terminal = out / "terminal.json"
        if terminal.exists():
            raise FileExistsError(terminal)
        command = [str(HERE / "join"), str(input_path), str(out / "result.json")]
        with (out / "stdout.txt").open("wb") as stdout, \
             (out / "stderr.txt").open("wb") as stderr:
            started = time.monotonic_ns()
            child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                     cwd=HERE)
            peak = 0
            guard = None
            while child.poll() is None:
                try:
                    peak = max(peak, psutil.Process(child.pid).memory_info().rss)
                except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError):
                    pass
                if peak >= protocol["limits"]["peak_rss_bytes"]:
                    guard = "PARENT_MEMORY_CAP"
                elif time.monotonic_ns() - started >= \
                        protocol["limits"]["parent_seconds"] * 10**9:
                    guard = "PARENT_WALL_CAP"
                if guard:
                    child.terminate()
                    try:
                        child.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        child.kill()
                    break
                time.sleep(0.05)
            code = child.wait()
            wall_ns = time.monotonic_ns() - started
        result_path = out / "result.json"
        result = json.loads(result_path.read_text()) if result_path.exists() else None
        status = guard or (result["status"] if code == 0 and result else
                           "PRODUCER_FAILURE")
        receipt = {
            "mode": mode, "status": status, "command": command,
            "returncode": code, "parent_wall_ns": wall_ns,
            "sampled_peak_rss_bytes": peak,
            "protocol_sha256": sha(HERE / "protocol.json"),
            "stdout_sha256": sha(out / "stdout.txt"),
            "stderr_sha256": sha(out / "stderr.txt"),
            "result_sha256": sha(result_path) if result else None,
        }
        terminal.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"mode": mode, "status": status,
                          "parent_wall_ns": wall_ns, "peak_rss_bytes": peak}),
              flush=True)
        if mode == "control" and status != "VERIFIED_RAW_ROW":
            break


if __name__ == "__main__":
    main()
