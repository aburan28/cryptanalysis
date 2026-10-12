#!/usr/bin/env python3
"""Reproduce the frozen native-XOR Gaussian-matrix stage gate."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import tempfile
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def source_check(config: dict, scratch: Path) -> tuple[dict, dict]:
    solver_name = shutil.which("cryptominisat5")
    if solver_name is None:
        raise FileNotFoundError("cryptominisat5 is unavailable")
    solver = Path(solver_name).resolve()
    if sha(solver) != config["solver_sha256"]:
        raise ValueError("solver binary digest differs from frozen config")
    version = subprocess.run([str(solver), "--version"], capture_output=True,
                             text=True, check=True).stdout.strip()
    if config["solver_version"] not in version:
        raise ValueError("solver version differs from frozen config")
    verified: dict[str, dict] = {}
    lifts = None
    for name, entry in config["formulas"].items():
        archive = ROOT / entry["archive"]
        receipt_path = ROOT / entry["formula_receipt"]
        if sha(archive) != entry["archive_sha256"]:
            raise ValueError(f"archive digest mismatch: {name}")
        receipt = json.loads(receipt_path.read_text())
        if (receipt["formula_sha256"] != entry["raw_sha256"]
                or receipt["actual_usable_points_B"] != config["actual_usable_points_B"]
                or receipt["ordinary_query_index"] != config["ordinary_query_index"]
                or receipt["summands"] != config["summands"]
                or receipt["input_prefix_sha256"] != config["input_prefix_sha256"]
                or receipt["source_curve_id"] != config["curve_id"]
                or len(receipt["target_x_choices"]) != config["target_lifts"]):
            raise ValueError(f"formula receipt mismatch: {name}")
        if lifts is not None and lifts != receipt["target_x_choices"]:
            raise ValueError("formula target lifts differ")
        lifts = receipt["target_x_choices"]
        raw = scratch / f"{name}.xcnf"
        start = time.perf_counter()
        with gzip.open(archive, "rb") as inp, raw.open("xb") as out:
            shutil.copyfileobj(inp, out)
        if sha(raw) != entry["raw_sha256"]:
            raise ValueError(f"raw formula digest mismatch: {name}")
        verified[name] = {
            "raw_path": str(raw),
            "archive_sha256": sha(archive),
            "raw_sha256": sha(raw),
            "formula_receipt_sha256": sha(receipt_path),
            "input_load_wall_seconds": time.perf_counter() - start,
            "stats": receipt["stats"],
        }
    return verified, {"solver": str(solver), "solver_sha256": sha(solver),
                      "solver_version": version, "target_x_choices": lifts}


def rss_bytes(pid: int) -> int | None:
    probe = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                           capture_output=True, text=True, check=False)
    if probe.returncode != 0:
        return None
    value = probe.stdout.strip()
    return int(value) * 1024 if value.isdigit() else None


def run_cell(config: dict, source: dict, solver: dict, name: str,
             variant: str, outdir: Path) -> dict:
    stem = f"{name}_{variant}"
    stdout_path = outdir / f"{stem}.stdout.txt"
    stderr_path = outdir / f"{stem}.stderr.txt"
    receipt_path = outdir / f"{stem}.json"
    if any(path.exists() for path in (stdout_path, stderr_path, receipt_path)):
        raise FileExistsError(f"refusing to overwrite {stem}")
    command = ([solver["solver"]] + config["base_flags"]
               + config["variants"][variant] + [source["raw_path"]])
    start = time.perf_counter()
    peak_rss = 0
    guard = None
    producer_error = None
    with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        try:
            while process.poll() is None:
                observed = rss_bytes(process.pid)
                if observed is None and process.poll() is None:
                    raise RuntimeError("RSS observation unavailable")
                peak_rss = max(peak_rss, observed or 0)
                if peak_rss > config["rss_cap_bytes"]:
                    guard = "RSS_CAP"
                if time.perf_counter() - start > config["external_wall_cap_seconds"]:
                    guard = "WALL_CAP"
                if guard:
                    os.killpg(process.pid, signal.SIGKILL)
                    break
                time.sleep(0.25)
            exit_code = process.wait()
        except Exception as error:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            exit_code = process.wait()
            producer_error = f"{type(error).__name__}: {error}"
    wall = time.perf_counter() - start
    output = stdout_path.read_text(errors="replace")
    errors = stderr_path.read_text(errors="replace")
    if producer_error:
        status = "PRODUCER_FAILURE"
    elif guard == "RSS_CAP":
        status = "OOM_GUARD"
    elif guard == "WALL_CAP":
        status = "BOUNDED_UNKNOWN"
    elif "s SATISFIABLE" in output:
        status = "SAT_UNVERIFIED"
    elif "s UNSATISFIABLE" in output:
        status = "UNSAT_UNVERIFIED"
    elif "s INDETERMINATE" in output or "s UNKNOWN" in output:
        status = "BOUNDED_UNKNOWN"
    else:
        status = "PRODUCER_FAILURE"
    restart_rows = [line for line in output.splitlines()
                    if line.lstrip().startswith("c rst")]
    used = re.findall(r"Using (\d+) matrices recovered", output)
    matrix_lines = [line for line in output.splitlines()
                    if "[matrix]" in line and
                    ("Good" in line or "UNused" in line or "Using" in line)]
    receipt = {
        "schema": "ecc2k130-equalb-gauss-gate-cell-v1",
        "candidate_id": None, "formula": name, "variant": variant,
        "status": status, "verified_relation": False, "novel_rank": None,
        "command": command, "source": source, "solver": solver,
        "config_sha256": sha(CONFIG), "runner_sha256": sha(Path(__file__)),
        "host_isolation": "unverified", "platform": platform.platform(),
        "logical_cpu_count": os.cpu_count(), "wall_seconds": wall,
        "peak_observed_rss_bytes": peak_rss,
        "solver_maxtime_seconds": config["solver_maxtime_seconds"],
        "external_wall_cap_seconds": config["external_wall_cap_seconds"],
        "rss_cap_bytes": config["rss_cap_bytes"],
        "exit_code": exit_code, "guard": guard,
        "producer_error": producer_error,
        "matrix_recovery_counts": [int(x) for x in used],
        "matrix_lines": matrix_lines,
        "live_restart_rows": len(restart_rows),
        "last_live_restart_row": restart_rows[-1] if restart_rows else None,
        "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path),
        "stderr_tail": errors[-2000:],
    }
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--run", action="store_true")
    parser.add_argument("--run-id", default="R1")
    args = parser.parse_args()
    if re.fullmatch(r"R[1-9][0-9]*", args.run_id) is None:
        parser.error("run ID must be R followed by a positive decimal integer")
    config = json.loads(CONFIG.read_text())
    if config["schema"] != "ecc2k130-equalb-gauss-gate-config-v1":
        raise ValueError("unknown config schema")
    outdir = HERE / "runs" / args.run_id
    if args.run and outdir.exists():
        raise FileExistsError(f"refusing to reuse {args.run_id}")
    with tempfile.TemporaryDirectory(prefix="ecc2k130-gauss-gate-") as tmp:
        sources, solver = source_check(config, Path(tmp))
        if args.check:
            print(json.dumps({"status": "SOURCE_CHECK_PASS", "sources": sources,
                              "solver": solver}, sort_keys=True))
            return
        outdir.mkdir(parents=True)
        results = []
        for name, variant in config["run_order"]:
            receipt = run_cell(config, sources[name], solver, name, variant, outdir)
            results.append({"formula": name, "variant": variant,
                            "status": receipt["status"],
                            "wall_seconds": receipt["wall_seconds"],
                            "peak_observed_rss_bytes": receipt["peak_observed_rss_bytes"],
                            "matrix_recovery_counts": receipt["matrix_recovery_counts"],
                            "live_restart_rows": receipt["live_restart_rows"]})
            print(json.dumps(results[-1], sort_keys=True), flush=True)
        (outdir / "summary.json").write_text(json.dumps({
            "schema": "ecc2k130-equalb-gauss-gate-summary-v1",
            "config_sha256": sha(CONFIG), "runner_sha256": sha(Path(__file__)),
            "results": results}, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
