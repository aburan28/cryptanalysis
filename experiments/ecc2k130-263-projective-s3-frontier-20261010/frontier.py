#!/usr/bin/env python3
"""Build and run frozen single-block projective-S3 SAT controls."""

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
BLOCKS = HERE.parent / "ecc2k130-263-projective-s3-blocks-20261010"
SAT = HERE.parent / "ecc2k130-263-projective-s3-sat-20261010"
sys.path.insert(0, str(BLOCKS))
sys.path.insert(0, str(SAT))
import common as parent  # noqa: E402
from run_build import process_rss_bytes  # noqa: E402


ref = parent.ref
RUN = HERE / "runs/R1"


def config():
    cfg = ref.read(HERE / "CONFIG.json")
    pins = {
        BLOCKS / "CONFIG.json": "parent_config_sha256",
        BLOCKS / "runs/R1/audit.json": "parent_audit_sha256",
        BLOCKS / "common.py": "parent_common_sha256",
        SAT / "verify_model.py": "model_verifier_sha256",
    }
    if (cfg["schema"] != "ecc2k130-263-projective-s3-frontier-v1"
            or any(ref.sha(path) != cfg[key] for path, key in pins.items())
            or cfg["policies"] != ["source", "descendant_native"]
            or cfg["modes"] != ["leaf0", "leaf5", "state0", "state3"]
            or cfg["ordered_cells"] != [f"{policy}/{mode}"
                for policy in cfg["policies"] for mode in cfg["modes"]]):
        raise ValueError("frontier protocol or parent identity changed")
    parent_cfg, parent_parent_cfg, parent_audit = parent.load_config()
    blocks_audit = ref.read(BLOCKS / "runs/R1/audit.json")
    if (parent_audit["status"] != "PASS_FIXED_EXCEPTIONAL_SAT_AND_GROUP_REPLAY"
            or blocks_audit["status"] != "PASS_PAIRED_BLOCK_DIAGNOSTIC"):
        raise ValueError("parent block audit did not pass")
    return cfg, parent_cfg, parent_parent_cfg


def inputs_for(policy, cfg, parent_cfg, parent_parent_cfg):
    if policy not in cfg["policies"]:
        raise ValueError("unknown curve policy")
    witness, build, base, inputs, base_row = parent.parent_inputs(
        policy, parent_cfg, parent_parent_cfg)
    positive = parent.parent_cells.exact_units(
        policy, "positive", inputs, build["target_selector_variables"],
        witness)
    if len(positive) != cfg["fixed_positive_units"]:
        raise ValueError("fixed positive control changed")
    return witness, build, base, inputs, base_row, positive


def release_variables(mode, inputs):
    if mode.startswith("leaf"):
        index = int(mode[4:])
        names = [f"{word}{index}:{bit}"
                 for word in ("x", "z") for bit in range(ref.DEGREE)]
    elif mode.startswith("state"):
        index = int(mode[5:])
        names = [f"t{index}:{bit}" for bit in range(ref.DEGREE)]
        names.append(f"f:{index}")
    else:
        raise ValueError("unknown frontier mode")
    if mode not in ("leaf0", "leaf5", "state0", "state3"):
        raise ValueError("mode outside frozen frontier")
    variables = {inputs[name] for name in names}
    if len(variables) != len(names):
        raise ValueError("released variable map is not injective")
    return variables


def fixed_units(mode, inputs, positive, cfg):
    released = release_variables(mode, inputs)
    positive_vars = {abs(lit) for lit in positive}
    if not released <= positive_vars:
        raise ValueError("released input was not fixed in parent witness")
    units = sorted(lit for lit in positive if abs(lit) not in released)
    expected = (cfg["leaf_singleton_fixed_units"] if mode.startswith("leaf")
                else cfg["state_singleton_fixed_units"])
    if len(units) != expected or len({abs(lit) for lit in units}) != expected:
        raise ValueError("single-block unit count changed")
    return units


def unit_bytes(units):
    return "".join(f"{lit} 0\n" for lit in units).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, row):
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, sort_keys=True, indent=2) + "\n")


def build_cells(policy, scratch):
    cfg, parent_cfg, parent_parent_cfg = config()
    _, build, base, inputs, base_row, positive = inputs_for(
        policy, cfg, parent_cfg, parent_parent_cfg)
    RUN.mkdir(parents=True, exist_ok=True)
    output = RUN / f"{policy}_cells.json"
    if output.exists():
        raise FileExistsError(output)
    rows = {}
    with tempfile.TemporaryDirectory(prefix="s3-frontier-build-",
                                     dir=scratch) as temporary:
        for mode in cfg["modes"]:
            units = fixed_units(mode, inputs, positive, cfg)
            delta = RUN / f"{policy}_{mode}.units.txt"
            if delta.exists():
                raise FileExistsError(delta)
            raw = unit_bytes(units)
            formula = Path(temporary) / f"{mode}.xcnf"
            vars_, total, count = parent.parent_audit.compose_cell(
                base, raw, formula)
            delta.write_bytes(raw)
            rows[mode] = {
                "unit_count": count,
                "released_input_count": len(release_variables(mode, inputs)),
                "unit_delta_sha256": digest(raw),
                "formula_sha256": ref.sha(formula),
                "formula_bytes": formula.stat().st_size,
                "variables": vars_,
                "total_constraints": total,
                "target_choice": 0,
            }
    write_json(output, {
        "schema": "ecc2k130-263-projective-s3-frontier-cells-v1",
        "status": "PASS_EXACT_SINGLE_BLOCK_INPUTS",
        "policy": policy,
        "config_sha256": ref.sha(HERE / "CONFIG.json"),
        "producer_sha256": ref.sha(Path(__file__)),
        "parent_base_sha256": base_row["raw_sha256"],
        "parent_base_gzip_sha256": base_row["gzip_sha256"],
        "parent_build_sha256": ref.sha(
            SAT / "runs/R1" / f"{policy}_control_base.json"),
        "parent_input_map_sha256": ref.sha(
            SAT / "runs/R1" / f"{policy}_control_base.inputs.json"),
        "parent_positive_units_sha256": ref.sha(
            SAT / "runs/R1" / f"{policy}_positive.units.txt"),
        "cells": rows,
    })
    print(json.dumps({"policy": policy, "cells": rows}, sort_keys=True),
          flush=True)


def run_cell(policy, mode, scratch):
    cfg, parent_cfg, parent_parent_cfg = config()
    _, build, base, inputs, _, positive = inputs_for(
        policy, cfg, parent_cfg, parent_parent_cfg)
    cell_path = RUN / f"{policy}_cells.json"
    cells = ref.read(cell_path)
    if (cells["status"] != "PASS_EXACT_SINGLE_BLOCK_INPUTS"
            or cells["policy"] != policy
            or cells["config_sha256"] != ref.sha(HERE / "CONFIG.json")
            or cells["producer_sha256"] != ref.sha(Path(__file__))
            or cells["parent_base_sha256"] != build["formula_sha256"]):
        raise ValueError("frozen cell producer or base changed")
    row = cells["cells"][mode]
    prefix = RUN / f"{policy}_{mode}"
    delta = prefix.with_suffix(".units.txt")
    expected = unit_bytes(fixed_units(mode, inputs, positive, cfg))
    if (delta.read_bytes() != expected
            or row["unit_delta_sha256"] != digest(expected)):
        raise ValueError("single-block fixed units differ")
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
    if process_rss_bytes(os.getpid()) <= 0:
        raise RuntimeError("RSS sampler preflight failed")
    with tempfile.TemporaryDirectory(prefix="s3-frontier-run-",
                                     dir=scratch) as temporary:
        formula = Path(temporary) / "cell.xcnf"
        vars_, total, count = parent.parent_audit.compose_cell(
            base, expected, formula)
        if (ref.sha(formula) != row["formula_sha256"]
                or formula.stat().st_size != row["formula_bytes"]
                or vars_ != row["variables"]
                or total != row["total_constraints"]
                or count != row["unit_count"]):
            raise ValueError("constructed XCNF differs from frozen cell")
        command = [str(solver), "--threads=1", "--maxtime=120",
                   "--verb=1", "--printsol=1", str(formula)]
        stdout_path = Path(temporary) / "stdout.txt"
        peak = 0
        guard = None
        started = time.perf_counter()
        with stdout_path.open("xb") as stdout, stderr_path.open("x") as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                       start_new_session=True)
            try:
                while process.poll() is None:
                    wall = time.perf_counter() - started
                    peak = max(peak, process_rss_bytes(process.pid))
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
        raw = stdout_path.read_bytes()
        terminal = [line.strip() for line in raw.decode(
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
                zipped.write(raw)
        child_peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        if sys.platform != "darwin":
            child_peak *= 1024
        write_json(receipt_path, {
            "schema": "ecc2k130-263-projective-s3-frontier-solver-v1",
            "status": status,
            "policy": policy,
            "mode": mode,
            "candidate_id": None,
            "formula_sha256": ref.sha(formula),
            "cell_receipt_sha256": ref.sha(cell_path),
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
            "stdout_raw_sha256": digest(raw),
            "stdout_raw_bytes": len(raw),
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
    parser.add_argument("--mode", choices=("leaf0", "leaf5", "state0",
                                            "state3"))
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
            parser.error("run requires one mode")
        run_cell(args.policy, args.mode, args.scratch_dir)


if __name__ == "__main__":
    main()
