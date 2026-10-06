#!/usr/bin/env python3
"""Run one checked-Sage shifted SAT branch with a process-tree envelope."""

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
PROTOCOL = HERE / "shifted_sat_protocol.json"
BRANCH = HERE / "run_shifted_sat_branch.py"
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main(label: str, kind: str, index: int, out: Path,
         private: Path | None) -> int:
    out = out.resolve()
    if out.exists():
        raise FileExistsError("bounded SAT output is immutable")
    protocol = json.loads(PROTOCOL.read_text())
    assert label in {item["label"] for item in protocol["geometry"]}
    assert kind in ("planted", "ordinary") and index in range(4)
    if private is not None:
        private = private.resolve()
        assert kind == "planted" and private.is_file()
    out.mkdir(parents=True)
    runtime = out / "sage_runtime_info.json"
    runtime_result = subprocess.run([str(SAGE), "--runtime-info"],
                                    capture_output=True, check=True)
    runtime.write_bytes(runtime_result.stdout)
    command = [str(SAGE), "-python", str(BRANCH), label, kind, str(index), str(out)]
    if private is not None:
        command.extend(("--pin-private", str(private)))
    env = os.environ.copy()
    env["N83_SHIFTED_SAT_EXTERNAL_GUARD"] = "1"
    env["TMPDIR"] = "/Volumes/SSD990/llm/tmp"
    started = time.perf_counter_ns()
    peak, guard = 0, None
    stdout_path, stderr_path = out / "outer.stdout.txt", out / "outer.stderr.txt"
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                 start_new_session=True, env=env)
        root = psutil.Process(child.pid)
        while child.poll() is None:
            try:
                members = [root, *root.children(recursive=True)]
                rss = sum(process.memory_info().rss for process in members
                          if process.is_running())
                peak = max(peak, rss)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            if peak >= protocol["max_process_tree_rss_bytes_per_branch"]:
                guard = "process_tree_rss_guard"
            elif (time.perf_counter_ns() - started) / 1e9 >= \
                    protocol["external_wall_seconds_per_branch"]:
                guard = "external_wall_guard"
            if guard is not None:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            time.sleep(0.05)
        exit_code = child.wait()
    inner = out / "receipt.json"
    status = "COMPLETE" if guard is None and exit_code == 0 and inner.is_file() else "INCOMPLETE"
    receipt = {
        "schema_version": 1, "kind": "bounded_n83_shifted_sat_execution",
        "status": status, "candidate_id": None,
        "label": label, "target_kind": kind, "fiber_index": index,
        "mode": "pinned_all" if private else "unpinned",
        "protocol_sha256": sha(PROTOCOL), "branch_source_sha256": sha(BRANCH),
        "watchdog_source_sha256": sha(Path(__file__)),
        "checked_sage_runtime_info_sha256": sha(runtime),
        "private_fixture_sha256_local_only": sha(private) if private else None,
        "architecture": platform.machine(), "os": platform.platform(),
        "argv": command, "external_wall_ns": time.perf_counter_ns() - started,
        "peak_process_tree_rss_bytes_sampled": peak,
        "max_process_tree_rss_bytes": protocol["max_process_tree_rss_bytes_per_branch"],
        "max_total_wall_seconds": protocol["external_wall_seconds_per_branch"],
        "guard": guard, "exit_code": exit_code,
        "inner_receipt_sha256": sha(inner) if inner.is_file() else None,
        "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path),
        "claim_boundary": protocol["claim_boundary"],
    }
    save(out / "outer_receipt.json", receipt)
    print(json.dumps({"label": label, "kind": kind, "fiber": index,
                      "mode": receipt["mode"], "status": status,
                      "guard": guard,
                      "inner_status": json.loads(inner.read_text())["status"]
                      if inner.is_file() else None}, sort_keys=True), flush=True)
    return 0 if status == "COMPLETE" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("kind", choices=("planted", "ordinary"))
    parser.add_argument("fiber_index", type=int)
    parser.add_argument("out", type=Path)
    parser.add_argument("--pin-private", type=Path)
    args = parser.parse_args()
    raise SystemExit(main(args.label, args.kind, args.fiber_index,
                          args.out, args.pin_private))
