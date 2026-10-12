#!/usr/bin/env python3
"""Frozen Q1524 four-complement joint-inversion control and ordinary panel."""
from __future__ import annotations

import hashlib
import json
import os
import resource
import signal
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1521 = PARENT / "q20261012_q1521_fused_complements"
BASE = PARENT / "bases/n83_weight5_full_point_orbits.bin"
BINARY = Path("/Volumes/SSD990/llm/tmp/q1524-native-joint")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text())


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def limit_cpu() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (60, 65))


def main() -> None:
    protocol = read(HERE / "protocol.json")
    assert sha(BASE) == protocol["factor_base_file_sha256"]
    assert sha(Q1521 / "result.json") == protocol["baseline_result_sha256"]
    assert sha(Q1521 / "native_fused.cpp") == protocol["baseline_source_sha256"]
    assert sha(HERE / "native_joint.cpp") == protocol["source_sha256"]
    assert sha(BINARY) == protocol["binary_sha256"]
    for label in protocol["panel_order"]:
        batch = protocol["batch_pairs"][label]
        input_file = Q1521 / f"{label}_xy.txt"
        assert sha(input_file) == protocol["input_sha256"][label]
        pair_limit = 1 if label == "control" else 15_488_796
        command = [str(BINARY), str(BASE), str(input_file), str(pair_limit),
                   str(batch), "28", "4"]
        folder = HERE / "runs" / label
        folder.mkdir(parents=True, exist_ok=False)
        out, err = folder / "stdout.txt", folder / "stderr.txt"
        start = time.monotonic()
        reason = None
        with out.open("wb") as stdout, err.open("wb") as stderr:
            child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                     preexec_fn=limit_cpu)
            terminated = None
            while True:
                pid, status, usage = os.wait4(child.pid, os.WNOHANG)
                if pid:
                    child.returncode = os.waitstatus_to_exitcode(status)
                    break
                now = time.monotonic()
                if terminated is None and now - start >= 180:
                    reason = "WALL_CAP"
                    child.terminate()
                    terminated = now
                elif terminated is not None and now - terminated >= 5:
                    child.kill()
                time.sleep(0.05)
        lines = out.read_text(errors="replace").splitlines()
        native = [json.loads(line) for line in lines if line.startswith("{")]
        hit_lines = [line for line in lines if line.startswith("hit ")]
        status = ("COMPLETE" if child.returncode == 0 and len(native) == 4 else
                  "WALL_CAP" if reason else
                  "CPU_CAP" if child.returncode in (-signal.SIGXCPU, -signal.SIGKILL) else
                  "PROCESS_FAILURE")
        receipt = {
            "label": label, "status": status, "command": command,
            "return_code": child.returncode, "termination_reason": reason,
            "native": native, "hit_lines": hit_lines,
            "wall_seconds_exploratory": time.monotonic() - start,
            "child_user_cpu_seconds": usage.ru_utime,
            "child_system_cpu_seconds": usage.ru_stime,
            "child_peak_rss_bytes_darwin": usage.ru_maxrss,
            "stdout_sha256": sha(out), "stderr_sha256": sha(err),
        }
        save(folder / "receipt.json", receipt)
        print(label, status, "hits", [x["hits"] for x in native], flush=True)
        if label == "control":
            assert status == "COMPLETE" and len(hit_lines) == 4
            assert all(x["hits"] == 1 for x in native)
        if status != "COMPLETE":
            break


if __name__ == "__main__":
    main()
