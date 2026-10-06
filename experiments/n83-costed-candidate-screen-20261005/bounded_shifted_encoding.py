#!/usr/bin/env python3
"""Bound a checked-Sage shifted-S3 encoding build by wall and process-tree RSS."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import time

import psutil


HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "shifted_pdp_protocol.json"
BUILDER = HERE / "build_shifted_s3_circuit.py"
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(label: str, out: Path) -> int:
    out = out.resolve()
    runtime = out / "sage_runtime_info.json"
    if not out.is_dir() or not runtime.is_file():
        raise FileNotFoundError("save checked Sage runtime before this workload")
    if (out / "outer_receipt.json").exists():
        raise FileExistsError("bounded encoding receipt is immutable")
    protocol = json.loads(PROTOCOL.read_text())
    if label not in {option["label"] for option in protocol["options"]}:
        raise ValueError("unknown frozen option")
    command = [str(SAGE), "-python", str(BUILDER), label, str(out), str(runtime)]
    stdout_path, stderr_path = out / "builder.stdout.txt", out / "builder.stderr.txt"
    if stdout_path.exists() or stderr_path.exists():
        raise FileExistsError("builder output is immutable")
    start = time.perf_counter_ns()
    peak = 0
    guard = None
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                 start_new_session=True)
        root = psutil.Process(child.pid)
        while child.poll() is None:
            try:
                members = [root, *root.children(recursive=True)]
                rss = sum(process.memory_info().rss for process in members
                          if process.is_running())
                peak = max(peak, rss)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            if peak >= protocol["max_process_tree_rss_bytes"]:
                guard = "process_tree_rss_guard"
            elif (time.perf_counter_ns() - start) / 1e9 >= protocol["max_total_wall_seconds"]:
                guard = "total_wall_guard"
            if guard is not None:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            time.sleep(0.05)
        exit_code = child.wait()
    inner = out / "receipt.json"
    inner_data = json.loads(inner.read_text()) if inner.is_file() else None
    status = ("ENCODING_COMPLETE" if guard is None and exit_code == 0
              and inner_data is not None and inner_data["status"] == "ENCODING_COMPLETE"
              else "INCOMPLETE")
    receipt = {
        "schema_version": 1, "kind": "bounded_n83_shifted_s3_encoding",
        "status": status, "candidate_id": None,
        "label": label, "curve_id": protocol["curve_id"],
        "protocol_sha256": sha(PROTOCOL), "builder_source_sha256": sha(BUILDER),
        "watchdog_source_sha256": sha(Path(__file__)),
        "sage_runtime_info_sha256": sha(runtime),
        "architecture": platform.machine(), "os": platform.platform(),
        "argv": command, "external_wall_ns": time.perf_counter_ns() - start,
        "peak_process_tree_rss_bytes_sampled": peak,
        "max_process_tree_rss_bytes": protocol["max_process_tree_rss_bytes"],
        "max_total_wall_seconds": protocol["max_total_wall_seconds"],
        "guard": guard, "exit_code": exit_code,
        "inner_receipt_sha256": sha(inner) if inner.is_file() else None,
        "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path),
        "claim_boundary": protocol["claim_boundary"],
    }
    (out / "outer_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"label": label, "status": status, "guard": guard,
                      "peak_rss_bytes": peak}, sort_keys=True))
    return 0 if status == "ENCODING_COMPLETE" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    raise SystemExit(main(args.label, args.out))
