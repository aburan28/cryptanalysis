#!/usr/bin/env python3
"""Build and run frozen x-only and z-only leaf SAT cells."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "ecc2k130-263-projective-s3-frontier-20261010"
sys.path.insert(0, str(PARENT))
import frontier as prior  # noqa: E402


ref = prior.ref
RUN = HERE / "runs/R1"


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, row):
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, sort_keys=True, indent=2) + "\n")


def config():
    cfg = ref.read(HERE / "CONFIG.json")
    pins = {
        PARENT / "CONFIG.json": "parent_config_sha256",
        PARENT / "frontier.py": "parent_runner_sha256",
        PARENT / "audit.py": "parent_auditor_sha256",
        PARENT / "runs/R1/audit.json": "parent_audit_sha256",
    }
    if (cfg["schema"] != "ecc2k130-263-leaf-inverse-frontier-v1"
            or any(ref.sha(path) != cfg[key] for path, key in pins.items())
            or cfg["policies"] != ["source", "descendant_native"]
            or cfg["modes"] != ["x0", "z0", "x5", "z5"]
            or cfg["ordered_cells"] != [f"{p}/{m}"
                for p in cfg["policies"] for m in cfg["modes"]]):
        raise ValueError("leaf-split protocol or parent source changed")
    parent_audit = ref.read(PARENT / "runs/R1/audit.json")
    if (parent_audit["status"] != "PASS_EXACT_INPUTS_AND_TRANSCRIPTS"
            or any(parent_audit["cells"][f"{p}/leaf{i}"]["status"]
                   != "BOUNDED_UNKNOWN"
                   for p in cfg["policies"] for i in (0, 5))
            or any(parent_audit["cells"][f"{p}/state{i}"]["status"]
                   != "SAT_VERIFIED_GROUP"
                   for p in cfg["policies"] for i in (0, 3))):
        raise ValueError("parent frontier audit status changed")
    parent_cfg, block_cfg, sat_cfg = prior.config()
    if cfg["solver_sha256"] != parent_cfg["solver_sha256"]:
        raise ValueError("solver binary identity changed")
    return cfg, parent_cfg, block_cfg, sat_cfg


def parent_inputs(policy, cfg, parent_cfg, block_cfg, sat_cfg):
    if policy not in cfg["policies"]:
        raise ValueError("unknown curve policy")
    witness, build, base, inputs, base_row, positive = prior.inputs_for(
        policy, parent_cfg, block_cfg, sat_cfg)
    if len(positive) != cfg["fixed_positive_units"]:
        raise ValueError("fixed positive witness changed")
    return witness, build, base, inputs, base_row, positive


def released_vars(mode, inputs, cfg):
    if mode not in cfg["modes"]:
        raise ValueError("mode outside frozen split")
    axis, leaf = mode[0], int(mode[1:])
    variables = {inputs[f"{axis}{leaf}:{bit}"] for bit in range(ref.DEGREE)}
    if len(variables) != cfg["released_coordinate_bits"]:
        raise ValueError("coordinate bits do not have unique input variables")
    return variables


def fixed_units(mode, inputs, positive, cfg):
    released = released_vars(mode, inputs, cfg)
    full_vars = {abs(lit) for lit in positive}
    if not released <= full_vars:
        raise ValueError("coordinate not fixed in parent witness")
    fixed = sorted(lit for lit in positive if abs(lit) not in released)
    if (len(fixed) != cfg["single_coordinate_fixed_units"]
            or len({abs(lit) for lit in fixed}) != len(fixed)):
        raise ValueError("single-coordinate fixed-unit count changed")
    return fixed


def unit_bytes(units):
    return "".join(f"{lit} 0\n" for lit in units).encode()


def build_cells(policy, scratch):
    cfg, parent_cfg, block_cfg, sat_cfg = config()
    _, build, base, inputs, base_row, positive = parent_inputs(
        policy, cfg, parent_cfg, block_cfg, sat_cfg)
    RUN.mkdir(parents=True, exist_ok=True)
    receipt = RUN / f"{policy}_cells.json"
    if receipt.exists():
        raise FileExistsError(receipt)
    rows = {}
    with tempfile.TemporaryDirectory(prefix="leaf-split-build-",
                                     dir=scratch) as temporary:
        for mode in cfg["modes"]:
            raw = unit_bytes(fixed_units(mode, inputs, positive, cfg))
            delta = RUN / f"{policy}_{mode}.units.txt"
            if delta.exists():
                raise FileExistsError(delta)
            formula = Path(temporary) / f"{mode}.xcnf"
            vars_, total, count = prior.parent.parent_audit.compose_cell(
                base, raw, formula)
            delta.write_bytes(raw)
            rows[mode] = {
                "released_input_count": len(released_vars(mode, inputs, cfg)),
                "unit_count": count,
                "unit_delta_sha256": sha_bytes(raw),
                "formula_sha256": ref.sha(formula),
                "formula_bytes": formula.stat().st_size,
                "variables": vars_,
                "total_constraints": total,
                "target_choice": 0,
            }
    write_json(receipt, {
        "schema": "ecc2k130-263-leaf-inverse-frontier-cells-v1",
        "status": "PASS_EXACT_SINGLE_COORDINATE_INPUTS",
        "policy": policy,
        "config_sha256": ref.sha(HERE / "CONFIG.json"),
        "producer_sha256": ref.sha(Path(__file__)),
        "parent_base_sha256": base_row["raw_sha256"],
        "parent_base_gzip_sha256": base_row["gzip_sha256"],
        "parent_positive_units_sha256": ref.sha(
            prior.SAT / "runs/R1" / f"{policy}_positive.units.txt"),
        "parent_frontier_audit_sha256": ref.sha(
            PARENT / "runs/R1/audit.json"),
        "cells": rows,
    })
    print(json.dumps({"policy": policy, "cells": rows}, sort_keys=True),
          flush=True)


def run_cell(policy, mode, scratch):
    cfg, parent_cfg, block_cfg, sat_cfg = config()
    _, build, base, inputs, base_row, positive = parent_inputs(
        policy, cfg, parent_cfg, block_cfg, sat_cfg)
    cells_path = RUN / f"{policy}_cells.json"
    cells = ref.read(cells_path)
    row = cells["cells"][mode]
    if (cells["status"] != "PASS_EXACT_SINGLE_COORDINATE_INPUTS"
            or cells["policy"] != policy
            or cells["config_sha256"] != ref.sha(HERE / "CONFIG.json")
            or cells["producer_sha256"] != ref.sha(Path(__file__))
            or cells["parent_base_sha256"] != base_row["raw_sha256"]):
        raise ValueError("frozen cell producer or base changed")
    prefix = RUN / f"{policy}_{mode}"
    delta = prefix.with_suffix(".units.txt")
    raw_units = unit_bytes(fixed_units(mode, inputs, positive, cfg))
    if (delta.read_bytes() != raw_units
            or row["unit_delta_sha256"] != sha_bytes(raw_units)):
        raise ValueError("single-coordinate unit delta changed")
    archive = prefix.with_suffix(".stdout.txt.gz")
    stderr_path = prefix.with_suffix(".stderr.txt")
    receipt_path = prefix.with_suffix(".solver.json")
    if any(path.exists() for path in (archive, stderr_path, receipt_path)):
        raise FileExistsError("solver evidence already exists")
    solver_name = shutil.which("cryptominisat5")
    if solver_name is None:
        raise FileNotFoundError("CryptoMiniSat 5 is unavailable")
    solver = Path(solver_name).resolve()
    if ref.sha(solver) != cfg["solver_sha256"]:
        raise ValueError("solver binary differs from frozen configuration")
    version = subprocess.run([str(solver), "--version"], text=True,
                             capture_output=True, check=True).stdout
    if "CryptoMiniSat version 5.14.7" not in version:
        raise ValueError("solver version changed")
    if prior.process_rss_bytes(os.getpid()) <= 0:
        raise RuntimeError("RSS sampler preflight failed")
    with tempfile.TemporaryDirectory(prefix="leaf-split-run-",
                                     dir=scratch) as temporary:
        formula = Path(temporary) / "cell.xcnf"
        vars_, total, count = prior.parent.parent_audit.compose_cell(
            base, raw_units, formula)
        if (ref.sha(formula) != row["formula_sha256"]
                or formula.stat().st_size != row["formula_bytes"]
                or vars_ != row["variables"]
                or total != row["total_constraints"]
                or count != row["unit_count"]):
            raise ValueError("full XCNF differs from precommitted cell")
        command = [str(solver), "--threads=1", "--maxtime=120",
                   "--verb=1", "--printsol=1", str(formula)]
        stdout_path = Path(temporary) / "stdout.txt"
        started = time.perf_counter()
        peak = 0
        guard = None
        with stdout_path.open("xb") as stdout, stderr_path.open("x") as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                       start_new_session=True)
            try:
                while process.poll() is None:
                    wall = time.perf_counter() - started
                    peak = max(peak, prior.process_rss_bytes(process.pid))
                    if peak > cfg["peak_rss_cap_bytes"]:
                        guard = "RSS_CAP"
                    elif wall > cfg["external_wall_seconds"]:
                        guard = "WALL_CAP"
                    if guard is not None:
                        os.killpg(process.pid, signal.SIGKILL)
                        break
                    time.sleep(0.25)
                exit_code = process.wait()
            except BaseException:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                raise
        wall = time.perf_counter() - started
        raw_output = stdout_path.read_bytes()
        terminal = [line.strip() for line in raw_output.decode(
            "utf-8", errors="replace").splitlines() if line.startswith("s ")]
        if guard == "RSS_CAP":
            status = "OOM_GUARD"
        elif guard == "WALL_CAP":
            status = "BOUNDED_UNKNOWN"
        elif terminal == ["s SATISFIABLE"] and exit_code == 10:
            status = "SAT_UNVERIFIED"
        elif terminal == ["s UNSATISFIABLE"] and exit_code == 20:
            status = "UNSAT"
        elif terminal == ["s INDETERMINATE"] and exit_code == 15:
            status = "BOUNDED_UNKNOWN"
        else:
            status = "PRODUCER_FAILURE"
        with archive.open("xb") as dest:
            with gzip.GzipFile(filename="", mode="wb", fileobj=dest,
                               mtime=0) as zipped:
                zipped.write(raw_output)
        child_peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        if sys.platform != "darwin":
            child_peak *= 1024
        write_json(receipt_path, {
            "schema": "ecc2k130-263-leaf-inverse-frontier-solver-v1",
            "status": status,
            "policy": policy,
            "mode": mode,
            "candidate_id": None,
            "formula_sha256": ref.sha(formula),
            "cell_receipt_sha256": ref.sha(cells_path),
            "config_sha256": ref.sha(HERE / "CONFIG.json"),
            "runner_sha256": ref.sha(Path(__file__)),
            "solver_sha256": ref.sha(solver),
            "solver_version": version,
            "command_flags": command[1:-1],
            "threads": cfg["threads"],
            "internal_wall_seconds": cfg["internal_wall_seconds"],
            "external_wall_seconds": cfg["external_wall_seconds"],
            "peak_rss_cap_bytes": cfg["peak_rss_cap_bytes"],
            "wall_seconds": wall,
            "peak_sampled_rss_bytes": peak,
            "peak_child_rss_bytes": child_peak,
            "guard": guard,
            "exit_code": exit_code,
            "terminal_status_lines": terminal,
            "stdout_raw_sha256": sha_bytes(raw_output),
            "stdout_raw_bytes": len(raw_output),
            "stdout_archive_sha256": ref.sha(archive),
            "stdout_archive_bytes": archive.stat().st_size,
            "stderr_sha256": ref.sha(stderr_path),
        })
    print(json.dumps({"policy": policy, "mode": mode, "status": status,
                      "wall_seconds": wall, "guard": guard}, sort_keys=True),
          flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "run"))
    parser.add_argument("--policy", choices=("source", "descendant_native"),
                        required=True)
    parser.add_argument("--mode", choices=("x0", "z0", "x5", "z5"))
    parser.add_argument("--scratch-dir", type=Path, default=Path("/private/tmp"))
    args = parser.parse_args()
    if not args.scratch_dir.is_dir():
        parser.error("scratch directory does not exist")
    if args.action == "build":
        if args.mode is not None:
            parser.error("build creates all modes for one curve")
        build_cells(args.policy, args.scratch_dir)
    else:
        if args.mode is None:
            parser.error("run requires a mode")
        run_cell(args.policy, args.mode, args.scratch_dir)


if __name__ == "__main__":
    main()
