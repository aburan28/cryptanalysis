#!/usr/bin/env python3
"""Build one full exceptional-control XCNF under frozen external guards."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import build_control as circuit


HERE = Path(__file__).resolve().parent
ref = circuit.ref


def process_rss_bytes(pid):
    result = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                            text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError("RSS sampler unavailable: " + result.stderr.strip())
    return int(result.stdout.strip()) * 1024 if result.stdout.strip() else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=circuit.parent.POLICIES, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    config = ref.read(HERE / "CONFIG.json")
    if (config["formula_build_external_wall_cap_seconds_each"] != 300
            or config["formula_build_peak_rss_cap_bytes"] != 4 * (1 << 30)):
        raise ValueError("frozen formula build limits changed")
    if process_rss_bytes(os.getpid()) <= 0:
        raise RuntimeError("RSS preflight returned no data")
    stem = args.out_dir / (args.policy + "_control_base")
    formula = stem.with_suffix(".xcnf")
    receipt_path = stem.with_suffix(".json")
    map_path = stem.with_suffix(".inputs.json")
    guard_path = stem.with_suffix(".build_guard.json")
    stdout_path = stem.with_suffix(".build_stdout.txt")
    stderr_path = stem.with_suffix(".build_stderr.txt")
    if any(path.exists() for path in
           (formula, receipt_path, map_path, guard_path, stdout_path,
            stderr_path)):
        parser.error("refusing to overwrite build evidence")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(HERE / "build_control.py"),
               "--policy", args.policy, "--out", str(formula)]
    started = time.perf_counter()
    peak_rss = 0
    guard = None
    with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        try:
            while process.poll() is None:
                rss = process_rss_bytes(process.pid)
                peak_rss = max(peak_rss, rss)
                if rss > config["formula_build_peak_rss_cap_bytes"]:
                    guard = "RSS_CAP"
                if (time.perf_counter() - started
                        > config["formula_build_external_wall_cap_seconds_each"]):
                    guard = "WALL_CAP"
                if guard:
                    os.killpg(process.pid, signal.SIGKILL)
                    break
                time.sleep(0.1)
            exit_code = process.wait()
        except BaseException:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise
    elapsed = time.perf_counter() - started
    receipt = ref.read(receipt_path) if receipt_path.exists() else None
    status = ("PASS_CONTROL_FORMULA_BUILT_WITH_EXTERNAL_GUARD"
              if exit_code == 0 and guard is None and receipt
              and receipt["status"] == "CONTROL_FORMULA_BUILT"
              and receipt["formula_sha256"] == ref.sha(formula)
              and receipt["input_vars_sha256"] == ref.sha(map_path)
              else "PRODUCER_FAILURE")
    result = {
        "schema": "ecc2k130-263-projective-s3-sat-build-guard-v1",
        "status": status,
        "policy": args.policy,
        "command": command,
        "builder_sha256": ref.sha(HERE / "build_control.py"),
        "config_sha256": ref.sha(HERE / "CONFIG.json"),
        "formula_sha256": ref.sha(formula) if formula.exists() else None,
        "formula_receipt_sha256": ref.sha(receipt_path) if receipt else None,
        "input_vars_sha256": ref.sha(map_path) if map_path.exists() else None,
        "stdout_sha256": ref.sha(stdout_path),
        "stderr_sha256": ref.sha(stderr_path),
        "wall_seconds": elapsed,
        "peak_sampled_rss_bytes": peak_rss,
        "external_wall_cap_seconds": config[
            "formula_build_external_wall_cap_seconds_each"],
        "external_rss_cap_bytes": config["formula_build_peak_rss_cap_bytes"],
        "guard": guard,
        "exit_code": exit_code,
        "runner_sha256": ref.sha(Path(__file__)),
    }
    guard_path.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("policy", "status", "wall_seconds",
                       "peak_sampled_rss_bytes", "guard", "exit_code")},
                     sort_keys=True), flush=True)
    if status != "PASS_CONTROL_FORMULA_BUILT_WITH_EXTERNAL_GUARD":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
