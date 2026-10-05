#!/usr/bin/env python3
"""Enforce a wall/RSS envelope around one checked-Sage N83 SAT branch."""

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
PROTOCOL = HERE / "n83_w34_sat_protocol.json"
BRANCH = HERE / "run_n83_w34_sat_branch.py"
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")
TOTAL_WALL_LIMIT_SECONDS = 240


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(public: Path, out: Path, branch_x: int, runtime: Path,
         private: Path | None) -> int:
    public, out, runtime = public.resolve(), out.resolve(), runtime.resolve()
    private = private.resolve() if private is not None else None
    if out.exists():
        raise FileExistsError("bounded branch output is immutable")
    if not runtime.is_file():
        raise FileNotFoundError("save checked Sage --runtime-info before workload")
    protocol = json.loads(PROTOCOL.read_text())
    limit = protocol["max_rss_bytes_per_branch"]
    assert SAGE.is_file() and sha(public)
    command = [str(SAGE), "-python", str(BRANCH), str(public), str(out), str(branch_x)]
    if private is not None:
        command.extend(("--pin-private", str(private.resolve())))
    env = os.environ.copy()
    env["N83_SAT_EXTERNAL_RSS_GUARD"] = "1"
    env["TMPDIR"] = "/Volumes/SSD990/llm/tmp"
    stdout_path = out.with_name(out.name + ".outer.stdout.txt")
    stderr_path = out.with_name(out.name + ".outer.stderr.txt")
    begin = time.perf_counter_ns()
    peak = 0
    guard = None
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        child = subprocess.Popen(
            command, stdout=stdout, stderr=stderr,
            start_new_session=True, env=env,
        )
        root = psutil.Process(child.pid)
        while child.poll() is None:
            try:
                members = [root, *root.children(recursive=True)]
                rss = sum(process.memory_info().rss for process in members
                          if process.is_running())
                peak = max(peak, rss)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            if peak >= limit:
                guard = "process_tree_rss_guard"
            elif (time.perf_counter_ns() - begin) / 1e9 >= TOTAL_WALL_LIMIT_SECONDS:
                guard = "total_wall_guard"
            if guard is not None:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            time.sleep(0.05)
        exit_code = child.wait()
    out.mkdir(parents=True, exist_ok=True)
    inner = out / "receipt.json"
    status = "COMPLETE" if guard is None and exit_code == 0 and inner.is_file() else "INCOMPLETE"
    receipt = {
        "schema_version": 1,
        "kind": "bounded_n83_w34_sat_branch_execution",
        "status": status,
        "curve_id": protocol["curve_id"],
        "mode": "pinned" if private is not None else "unpinned",
        "branch_target_x_decimal": str(branch_x),
        "public_input_sha256": sha(public),
        "private_fixture_sha256_local_only": sha(private) if private is not None else None,
        "protocol_sha256": sha(PROTOCOL),
        "branch_source_sha256": sha(BRANCH),
        "watchdog_source_sha256": sha(Path(__file__)),
        "checked_sage_runtime_info_sha256": sha(runtime),
        "architecture": platform.machine(),
        "os": platform.platform(),
        "argv": command,
        "external_wall_ns": time.perf_counter_ns() - begin,
        "peak_process_tree_rss_bytes_sampled": peak,
        "max_process_tree_rss_bytes": limit,
        "max_total_wall_seconds": TOTAL_WALL_LIMIT_SECONDS,
        "guard": guard,
        "exit_code": exit_code,
        "inner_receipt_sha256": sha(inner) if inner.is_file() else None,
        "stdout_sha256": sha(stdout_path),
        "stderr_sha256": sha(stderr_path),
        "claim_boundary": protocol["claim_boundary"],
    }
    (out / "outer_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status, "guard": guard,
                      "exit_code": exit_code, "peak_rss_bytes": peak}, sort_keys=True))
    return 0 if status == "COMPLETE" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("public_input", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("branch_x", type=int)
    parser.add_argument("runtime_info", type=Path)
    parser.add_argument("--pin-private", type=Path)
    args = parser.parse_args()
    raise SystemExit(main(args.public_input, args.out, args.branch_x,
                          args.runtime_info, args.pin_private))
