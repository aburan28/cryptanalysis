#!/usr/bin/env python3
"""Frozen 2048/8192-pair batch screen on selected and holdout complements."""
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent


def main():
    p = run.read(HERE / "protocol.json")
    screen = run.read(HERE / "batch_screen.json")
    assert run.sha(run.BASE) == p["factor_base_file_sha256"]
    assert run.sha(run.BINARY) == p["binary_sha256"]
    assert run.sha(HERE / "native_joint.cpp") == p["source_sha256"]
    for label, batch in screen["panel_order"]:
        assert label in ("selected", "holdout") and batch in (2048, 8192)
        input_file = run.Q1521 / f"{label}_xy.txt"
        assert run.sha(input_file) == p["input_sha256"][label]
        key = f"{label}_{batch}"
        folder = HERE / "runs" / key
        folder.mkdir(parents=True, exist_ok=False)
        command = [str(run.BINARY), str(run.BASE), str(input_file), "15488796",
                   str(batch), "28", "4"]
        start = time.monotonic()
        reason = None
        out, err = folder / "stdout.txt", folder / "stderr.txt"
        with out.open("wb") as stdout, err.open("wb") as stderr:
            child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                     preexec_fn=run.limit_cpu)
            terminated = None
            while True:
                pid, status, usage = os.wait4(child.pid, os.WNOHANG)
                if pid:
                    child.returncode = os.waitstatus_to_exitcode(status)
                    break
                now = time.monotonic()
                if terminated is None and now - start >= screen["wall_seconds"]:
                    reason = "WALL_CAP"
                    child.terminate()
                    terminated = now
                elif terminated is not None and now - terminated >= 5:
                    child.kill()
                time.sleep(0.05)
        lines = out.read_text(errors="replace").splitlines()
        native = [json.loads(line) for line in lines if line.startswith("{")]
        status = ("COMPLETE" if child.returncode == 0 and len(native) == 4 else
                  "WALL_CAP" if reason else
                  "CPU_CAP" if child.returncode in (-signal.SIGXCPU, -signal.SIGKILL) else
                  "PROCESS_FAILURE")
        receipt = {"label": label, "batch_pairs": batch, "status": status,
                   "command": command, "return_code": child.returncode,
                   "termination_reason": reason, "native": native,
                   "hit_lines": [line for line in lines if line.startswith("hit ")],
                   "wall_seconds_exploratory": time.monotonic() - start,
                   "child_user_cpu_seconds": usage.ru_utime,
                   "child_system_cpu_seconds": usage.ru_stime,
                   "child_peak_rss_bytes_darwin": usage.ru_maxrss,
                   "stdout_sha256": run.sha(out), "stderr_sha256": run.sha(err)}
        run.save(folder / "receipt.json", receipt)
        print(key, status, [x["hits"] for x in native], flush=True)


if __name__ == "__main__":
    main()
