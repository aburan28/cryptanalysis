#!/usr/bin/env python3
"""Run the frozen conflict-limited normal4 two/five Gaussian pair."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys
import tempfile
import time


HERE = Path(__file__).resolve().parent
CONFIG = HERE / "CONFIG.json"
COUNT = HERE.parent / "ecc2k130-equalb-gauss-count-20261010"
SOURCE = HERE.parent / "ecc2k130-equalb-gauss-gate-20261010"
sys.path.insert(0, str(SOURCE))
import run_gate as source_runner  # noqa: E402


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_config() -> dict:
    config = json.loads(CONFIG.read_text())
    if config["schema"] != "ecc2k130-equalb-normal4-conflict-gate-v1":
        raise ValueError("unknown config schema")
    if digest(COUNT / "CONFIG.json") != config["parent_config_sha256"]:
        raise ValueError("parent config changed")
    if digest(COUNT / "run_count.py") != config["parent_dispatch_sha256"]:
        raise ValueError("parent dispatcher changed")
    if digest(SOURCE / "run_gate.py") != config["source_runner_sha256"]:
        raise ValueError("source runner changed")
    prior = json.loads((COUNT / "CONFIG.json").read_text())
    for key in ("curve_id", "actual_usable_points_B", "ordinary_query_index",
                "summands", "target_lifts", "input_prefix_sha256",
                "solver_sha256", "solver_version", "threads", "rss_cap_bytes"):
        if config[key] != prior[key]:
            raise ValueError(f"frozen source differs: {key}")
    if config["formulas"]["normal4_counter"]["raw_sha256"] != \
            prior["formulas"]["normal4_counter"]["raw_sha256"]:
        raise ValueError("frozen formula differs")
    if config["run_order"] != [["normal4_counter", "two"],
                               ["normal4_counter", "five"]]:
        raise ValueError("run order differs")
    if config["run_ids"] != ["R1"]:
        raise ValueError("unregistered run")
    expected_flags = [
        "--threads=1", "--maxtime=210", "--maxconfl=80000", "--verb=1",
        "--printsol=1", "--maxmatrixrows=9000", "--maxmatrixcols=14000",
        "--autodisablegauss=0",
    ]
    if config["base_flags"] != expected_flags or config["variants"] != {
            "two": ["--maxnummatrices=2"],
            "five": ["--maxnummatrices=5"]}:
        raise ValueError("solver policy differs")
    if (config["solver_maxtime_seconds"] != 210
            or config["solver_max_conflicts"] != 80000
            or config["external_wall_cap_seconds"] != 240
            or config["sigint_grace_seconds"] != 10
            or config["rss_cap_bytes"] != 4294967296):
        raise ValueError("resource envelope differs")
    return config


def inspect_output(output: str) -> dict:
    restarts = [line for line in output.splitlines()
                if line.lstrip().startswith("c rst ")]
    recovered = [int(value) for value in
                 re.findall(r"Using (\d+) matrices recovered", output)]
    good = []
    for line in output.splitlines():
        match = re.search(r"Good\s+matrix\s+\d+\s+(\d+)\s+x\s*(\d+)", line)
        if match:
            good.append((int(match[1]), int(match[2])))
    calls = re.findall(r"elim called\s*:\s*(\d+[KM]?)", output)
    active = (any(int(value.rstrip("KM")) > 0 for value in calls)
              if calls else None)
    return {
        "matrix_recovery_counts": recovered,
        "largest_good_matrix": list(max(good)) if good else None,
        "elimination_call_lines": calls,
        "active_elimination": active,
        "live_restart_rows": len(restarts),
        "last_live_restart_row": restarts[-1] if restarts else None,
        "last_restart_conflict_label":
            restarts[-1].split()[6] if restarts else None,
    }


def classify(output: str, guard: str | None, error: str | None) -> str:
    if error:
        return "PRODUCER_FAILURE"
    if "s SATISFIABLE" in output:
        return "SAT_UNVERIFIED"
    if "s UNSATISFIABLE" in output:
        return "UNSAT_UNVERIFIED"
    if guard == "RSS_CAP":
        return "OOM_GUARD"
    if guard == "WALL_CAP" or "s INDETERMINATE" in output or \
            "s UNKNOWN" in output:
        return "BOUNDED_UNKNOWN"
    return "PRODUCER_FAILURE"


def signal_group(process: subprocess.Popen, sig: int) -> None:
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        pass


def run_cell(config: dict, source: dict, solver: dict, variant: str,
             outdir: Path) -> dict:
    stem = f"normal4_counter_{variant}"
    stdout_path = outdir / f"{stem}.stdout.txt"
    stderr_path = outdir / f"{stem}.stderr.txt"
    receipt_path = outdir / f"{stem}.json"
    if any(path.exists() for path in (stdout_path, stderr_path, receipt_path)):
        raise FileExistsError(f"refusing to overwrite {stem}")
    command = ([solver["solver"]] + config["base_flags"]
               + config["variants"][variant] + [source["raw_path"]])
    started = time.perf_counter()
    peak_rss = 0
    samples = 0
    guard = None
    signal_sent = None
    signal_at_seconds = None
    forced_kill = False
    producer_error = None
    exit_code = None
    process = None
    with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
        try:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                       start_new_session=True)
            grace_deadline = None
            while process.poll() is None:
                observed = source_runner.rss_bytes(process.pid)
                if observed is None and process.poll() is None:
                    raise RuntimeError("RSS observation unavailable")
                if observed is not None:
                    samples += 1
                    peak_rss = max(peak_rss, observed)
                now = time.perf_counter()
                if peak_rss > config["rss_cap_bytes"]:
                    guard = "RSS_CAP"
                    signal_sent = "SIGKILL"
                    forced_kill = True
                    signal_at_seconds = now - started
                    signal_group(process, signal.SIGKILL)
                    break
                if (grace_deadline is None and
                        now - started >= config["external_wall_cap_seconds"]):
                    guard = "WALL_CAP"
                    signal_sent = "SIGINT"
                    signal_at_seconds = now - started
                    signal_group(process, signal.SIGINT)
                    grace_deadline = now + config["sigint_grace_seconds"]
                if grace_deadline is not None and now >= grace_deadline:
                    signal_sent = "SIGINT_THEN_SIGKILL"
                    forced_kill = True
                    signal_group(process, signal.SIGKILL)
                    break
                time.sleep(0.25)
            exit_code = process.wait()
        except Exception as error:
            producer_error = f"{type(error).__name__}: {error}"
            if process is not None:
                if process.poll() is None:
                    signal_group(process, signal.SIGKILL)
                    forced_kill = True
                exit_code = process.wait()
    wall_seconds = time.perf_counter() - started
    output = stdout_path.read_text(errors="replace")
    status = classify(output, guard, producer_error)
    receipt = {
        "schema": "ecc2k130-equalb-normal4-conflict-cell-v1",
        "candidate_id": None, "formula": "normal4_counter",
        "variant": variant, "status": status,
        "verified_relation": False, "novel_rank": None,
        "command": command, "source": source, "solver": solver,
        "config_sha256": digest(CONFIG),
        "runner_sha256": digest(Path(__file__)),
        "source_runner_sha256": config["source_runner_sha256"],
        "platform": platform.platform(), "logical_cpu_count": os.cpu_count(),
        "host_isolation": "unverified",
        "wall_seconds": wall_seconds,
        "peak_observed_rss_bytes": peak_rss, "rss_sample_count": samples,
        "solver_maxtime_seconds": config["solver_maxtime_seconds"],
        "solver_max_conflicts": config["solver_max_conflicts"],
        "external_wall_cap_seconds": config["external_wall_cap_seconds"],
        "sigint_grace_seconds": config["sigint_grace_seconds"],
        "rss_cap_bytes": config["rss_cap_bytes"],
        "guard": guard, "signal_sent": signal_sent,
        "signal_at_seconds": signal_at_seconds,
        "forced_kill": forced_kill, "exit_code": exit_code,
        "producer_error": producer_error,
        "stdout_sha256": digest(stdout_path),
        "stderr_sha256": digest(stderr_path),
        "stderr_tail": stderr_path.read_text(errors="replace")[-2000:],
        **inspect_output(output),
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--run", action="store_true")
    parser.add_argument("--run-id", default="R1")
    args = parser.parse_args()
    config = load_config()
    if args.run_id not in config["run_ids"]:
        parser.error("run ID is not frozen")
    outdir = HERE / "runs" / args.run_id
    if args.run and outdir.exists():
        raise FileExistsError(f"refusing to overwrite {outdir}")
    if args.run:
        outdir.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="ecc2k130-normal4-conflict-") as tmp:
        try:
            sources, solver = source_runner.source_check(config, Path(tmp))
            item = config["formulas"]["normal4_counter"]
            if sources["normal4_counter"]["formula_receipt_sha256"] != \
                    item["formula_receipt_sha256"]:
                raise ValueError("formula receipt changed")
            preflight = {
                "status": "SOURCE_CHECK_PASS",
                "config_sha256": digest(CONFIG),
                "runner_sha256": digest(Path(__file__)),
                "source_runner_sha256": config["source_runner_sha256"],
                "source_hashes": {
                    name: row["raw_sha256"] for name, row in sources.items()},
                "solver_sha256": solver["solver_sha256"],
            }
        except Exception as error:
            preflight = {"status": "PRODUCER_FAILURE",
                         "config_sha256": digest(CONFIG),
                         "error": f"{type(error).__name__}: {error}"}
            if args.run:
                (outdir / "preflight.json").write_text(
                    json.dumps(preflight, indent=2, sort_keys=True) + "\n")
            print(json.dumps(preflight, sort_keys=True), flush=True)
            raise
        if args.check:
            print(json.dumps(preflight, sort_keys=True))
            return
        (outdir / "preflight.json").write_text(
            json.dumps(preflight, indent=2, sort_keys=True) + "\n")
        rows = []
        for name, variant in config["run_order"]:
            receipt = run_cell(config, sources[name], solver, variant, outdir)
            rows.append({key: receipt[key] for key in (
                "formula", "variant", "status", "wall_seconds",
                "peak_observed_rss_bytes", "rss_sample_count", "guard",
                "exit_code", "matrix_recovery_counts", "largest_good_matrix",
                "active_elimination", "live_restart_rows",
                "last_restart_conflict_label")})
            print(json.dumps(rows[-1], sort_keys=True), flush=True)
        (outdir / "summary.json").write_text(json.dumps({
            "schema": "ecc2k130-equalb-normal4-conflict-summary-v1",
            "config_sha256": digest(CONFIG),
            "runner_sha256": digest(Path(__file__)),
            "cells": rows,
        }, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
