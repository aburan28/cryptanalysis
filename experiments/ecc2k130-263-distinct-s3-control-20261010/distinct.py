#!/usr/bin/env python3
"""Build, freeze, and run finite six-distinct-leaf projective-S3 SAT cells."""

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
RUN = HERE / "runs/R1"
SAT = HERE.parent / "ecc2k130-263-projective-s3-sat-20261010"
PROJECTIVE = HERE.parent / "ecc2k130-263-projective-s3-20261010"
NATIVE = HERE.parent / "ecc2k130-263-native-w24-m6-20261010"
WORKLOAD = HERE.parent / "ecc2k130-263-equal-w24-workload-20261005"
sys.path.insert(0, str(SAT))
import build_control as circuit  # noqa: E402


ref = circuit.ref


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def config():
    cfg = ref.read(HERE / "CONFIG.json")
    pins = {
        NATIVE / "runs/R1/geometry_controls.json": "geometry_controls_sha256",
        NATIVE / "runs/R1/verification.json": "native_verification_sha256",
        WORKLOAD / "primary_workload.json": "primary_workload_sha256",
        NATIVE / "field.py": "field_source_sha256",
        PROJECTIVE / "binary_group.py": "binary_group_source_sha256",
        PROJECTIVE / "build_projective.py": "projective_builder_sha256",
        SAT / "build_control.py": "sat_builder_sha256",
        SAT / "verify_model.py": "sat_model_verifier_sha256",
    }
    if (cfg["schema"] != "ecc2k130-263-distinct-s3-control-v1"
            or any(ref.sha(path) != cfg[key] for path, key in pins.items())
            or cfg["policies"] != ["source", "descendant_native"]
            or cfg["modes"]
            != ["positive", "negative", "x0", "z0", "x5", "z5"]
            or cfg["ordered_cells"] != [f"{p}/{m}"
                for p in cfg["policies"] for m in cfg["modes"]]
            or cfg["geometry_leaf_indices"] != list(range(6))
            or cfg["signs"] != [0] * 6):
        raise ValueError("frozen control configuration or source changed")
    return cfg


def witness(cfg):
    path = RUN / "witness.json"
    value = ref.read(path)
    if (value["schema"] != "ecc2k130-263-distinct-s3-witness-v1"
            or value["status"] != "PASS_TWO_FINITE_SIX_DISTINCT_CONTROLS"
            or value["config_sha256"] != ref.sha(HERE / "CONFIG.json")
            or value["geometry_controls_sha256"]
            != cfg["geometry_controls_sha256"]
            or value["native_verification_sha256"]
            != cfg["native_verification_sha256"]
            or value["source_sha256"] != ref.sha(HERE / "make_witness.py")
            or value["binary_group_source_sha256"]
            != cfg["binary_group_source_sha256"]
            or value["sage_runtime_info_sha256"]
            != ref.sha(RUN / "sage_runtime_info.json")):
        raise ValueError("checked Sage witness or source changed")
    for policy in cfg["policies"]:
        control = value["policies"][policy]
        if (control["target_point_normalized"]
                != cfg["expected_targets"][policy]
                or not all(control[key] for key in (
                    "all_six_masks_distinct", "all_intermediates_finite",
                    "all_five_projective_links_zero", "sage_binary_group_agree",
                    "fourfold_points_distinct_in_subgroup"))):
            raise ValueError("finite distinct control conditions changed")
    return value


def base_paths(policy):
    return (RUN / f"{policy}_base.xcnf.gz",
            RUN / f"{policy}_inputs.json",
            RUN / f"{policy}_base.json")


def build_base(policy, scratch):
    cfg = config()
    checked = witness(cfg)
    archive, input_path, receipt = base_paths(policy)
    if any(path.exists() for path in (archive, input_path, receipt)):
        raise FileExistsError("base formula evidence already exists")
    control = checked["policies"][policy]
    target_x = control["target_x"]
    xs = [target_x] + [target_x ^ 1] * 3
    started = time.perf_counter()
    prog, roots, leaves, _ = circuit.parent.build_ir(policy)
    formula, choice, literals = circuit.encode_with_map(
        policy, prog, roots, leaves, xs)
    with tempfile.TemporaryDirectory(prefix="distinct-s3-build-",
                                     dir=scratch) as temporary:
        raw = Path(temporary) / "base.xcnf"
        formula.writeDimacs(raw)
        raw_sha = ref.sha(raw)
        raw_bytes = raw.stat().st_size
        RUN.mkdir(parents=True, exist_ok=True)
        with raw.open("rb") as source, archive.open("xb") as dest:
            with gzip.GzipFile(filename="", mode="wb", fileobj=dest,
                               mtime=0) as zipped:
                shutil.copyfileobj(source, zipped, length=1 << 20)
    input_vars = {"%s:%d" % key: value for key, value in literals.items()}
    write_json(input_path, input_vars)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        peak *= 1024
    row = {
        "schema": "ecc2k130-263-distinct-s3-base-v1",
        "status": "CONTROL_FORMULA_BUILT",
        "candidate_id": None,
        "policy": policy,
        "target_x_choices": [str(value) for value in xs],
        "target_selector_variables": choice,
        "formula_raw_sha256": raw_sha,
        "formula_raw_bytes": raw_bytes,
        "formula_gzip_sha256": ref.sha(archive),
        "formula_gzip_bytes": archive.stat().st_size,
        "input_vars_sha256": ref.sha(input_path),
        "input_vars_count": len(input_vars),
        "stats": formula.stats(),
        "config_sha256": ref.sha(HERE / "CONFIG.json"),
        "witness_sha256": ref.sha(RUN / "witness.json"),
        "builder_sha256": ref.sha(Path(__file__)),
        "projective_builder_sha256": cfg["projective_builder_sha256"],
        "sat_builder_sha256": cfg["sat_builder_sha256"],
        "build_wall_seconds": time.perf_counter() - started,
        "peak_process_rss_bytes": peak,
    }
    write_json(receipt, row)
    print(json.dumps({key: row[key] for key in (
        "policy", "status", "stats", "build_wall_seconds",
        "peak_process_rss_bytes")}, sort_keys=True), flush=True)


def read_base(policy, cfg):
    checked = witness(cfg)
    archive, input_path, receipt_path = base_paths(policy)
    base = ref.read(receipt_path)
    inputs = ref.read(input_path)
    control = checked["policies"][policy]
    target = control["target_x"]
    if (base["schema"] != "ecc2k130-263-distinct-s3-base-v1"
            or base["status"] != "CONTROL_FORMULA_BUILT"
            or base["policy"] != policy
            or base["target_x_choices"]
            != [str(target)] + [str(target ^ 1)] * 3
            or base["formula_gzip_sha256"] != ref.sha(archive)
            or base["input_vars_sha256"] != ref.sha(input_path)
            or base["input_vars_count"] != len(inputs)
            or base["config_sha256"] != ref.sha(HERE / "CONFIG.json")
            or base["witness_sha256"] != ref.sha(RUN / "witness.json")
            or base["builder_sha256"] != ref.sha(Path(__file__))
            or base["projective_builder_sha256"]
            != cfg["projective_builder_sha256"]
            or base["sat_builder_sha256"] != cfg["sat_builder_sha256"]):
        raise ValueError("base formula source or receipt changed")
    return control, archive, inputs, base


def word_units(bits, name, value, width, inputs):
    for bit in range(width):
        bits.append((inputs[f"{name}:{bit}"], (value >> bit) & 1))


def exact_units(mode, control, inputs, choice, cfg):
    fixed = []
    alpha = control["alpha"]
    for index, leaf in enumerate(control["leaves"]):
        word_units(fixed, f"s{index}", leaf["mask"], 24, inputs)
        x, z, _ = ref.leaf(leaf["mask"], alpha)
        if x != leaf["raw_point_normalized"][0] or z != leaf["z"]:
            raise ValueError("leaf differs from checked witness")
        if mode != f"x{index}":
            word_units(fixed, f"x{index}", x, ref.DEGREE, inputs)
        if mode != f"z{index}":
            word_units(fixed, f"z{index}", z, ref.DEGREE, inputs)
    for index, point in enumerate(control["intermediates"]):
        if not point["finite"]:
            raise ValueError("control projective state is not finite")
        word_units(fixed, f"t{index}", point["x"], ref.DEGREE, inputs)
        fixed.append((inputs[f"f:{index}"], 1))
    selected = int(mode == "negative")
    for bit, variable in enumerate(choice):
        fixed.append((variable, (selected >> bit) & 1))
    if len({literal for literal, _ in fixed}) != len(fixed):
        raise ValueError("duplicate fixed input variable")
    expected = (cfg["single_coordinate_fixed_units"]
                if mode in ("x0", "z0", "x5", "z5")
                else cfg["fixed_positive_units"])
    if len(fixed) != expected:
        raise ValueError("fixed-unit count differs from protocol")
    return sorted(literal if value else -literal for literal, value in fixed)


def unit_bytes(units):
    return "".join(f"{literal} 0\n" for literal in units).encode()


def compose(base, raw_units, output):
    lines = raw_units.splitlines()
    with base.open("rb") as source, output.open("xb") as dest:
        header = source.readline().split()
        if len(header) != 4 or header[:2] != [b"p", b"cnf"]:
            raise ValueError("invalid base XCNF header")
        variables, constraints = map(int, header[2:])
        dest.write(f"p cnf {variables} {constraints + len(lines)}\n".encode())
        shutil.copyfileobj(source, dest, length=1 << 20)
        dest.write(raw_units)
    return variables, constraints + len(lines), len(lines)


def freeze_cells(policy, scratch):
    cfg = config()
    control, archive, inputs, base_row = read_base(policy, cfg)
    receipt = RUN / f"{policy}_cells.json"
    if receipt.exists():
        raise FileExistsError(receipt)
    rows = {}
    with tempfile.TemporaryDirectory(prefix="distinct-s3-freeze-",
                                     dir=scratch) as temporary:
        base = Path(temporary) / "base.xcnf"
        with gzip.open(archive, "rb") as source, base.open("xb") as dest:
            shutil.copyfileobj(source, dest, length=1 << 20)
        if (ref.sha(base) != base_row["formula_raw_sha256"]
                or base.stat().st_size != base_row["formula_raw_bytes"]):
            raise ValueError("base XCNF archive differs")
        for mode in cfg["modes"]:
            raw_units = unit_bytes(exact_units(
                mode, control, inputs,
                base_row["target_selector_variables"], cfg))
            delta = RUN / f"{policy}_{mode}.units.txt"
            if delta.exists():
                raise FileExistsError(delta)
            formula = Path(temporary) / f"{mode}.xcnf"
            variables, constraints, count = compose(
                base, raw_units, formula)
            delta.write_bytes(raw_units)
            rows[mode] = {
                "unit_count": count,
                "target_choice": int(mode == "negative"),
                "released_coordinate_bits": cfg["released_coordinate_bits"]
                    if mode in ("x0", "z0", "x5", "z5") else 0,
                "unit_delta_sha256": sha_bytes(raw_units),
                "formula_sha256": ref.sha(formula),
                "formula_bytes": formula.stat().st_size,
                "variables": variables,
                "total_constraints": constraints,
            }
    write_json(receipt, {
        "schema": "ecc2k130-263-distinct-s3-cells-v1",
        "status": "PASS_SIX_EXACT_INPUTS",
        "policy": policy,
        "config_sha256": ref.sha(HERE / "CONFIG.json"),
        "producer_sha256": ref.sha(Path(__file__)),
        "witness_sha256": ref.sha(RUN / "witness.json"),
        "base_receipt_sha256": ref.sha(base_paths(policy)[2]),
        "base_gzip_sha256": ref.sha(archive),
        "input_vars_sha256": ref.sha(base_paths(policy)[1]),
        "cells": rows,
    })
    print(json.dumps({"policy": policy, "cells": {
        mode: row["unit_count"] for mode, row in rows.items()}},
        sort_keys=True), flush=True)


def process_rss_bytes(pid):
    proc = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                          capture_output=True, text=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        return 0
    return int(proc.stdout.strip()) * 1024


def run_cell(policy, mode, scratch):
    cfg = config()
    control, archive, inputs, base_row = read_base(policy, cfg)
    cells_path = RUN / f"{policy}_cells.json"
    cells = ref.read(cells_path)
    row = cells["cells"][mode]
    if (cells["policy"] != policy
            or cells["config_sha256"] != ref.sha(HERE / "CONFIG.json")
            or cells["producer_sha256"] != ref.sha(Path(__file__))
            or cells["witness_sha256"] != ref.sha(RUN / "witness.json")
            or cells["base_receipt_sha256"] != ref.sha(base_paths(policy)[2])
            or cells["base_gzip_sha256"] != ref.sha(archive)
            or cells["input_vars_sha256"] != ref.sha(base_paths(policy)[1])):
        raise ValueError("frozen cell producer or base changed")
    prefix = RUN / f"{policy}_{mode}"
    delta = prefix.with_suffix(".units.txt")
    expected = unit_bytes(exact_units(
        mode, control, inputs, base_row["target_selector_variables"], cfg))
    if (delta.read_bytes() != expected
            or row["unit_delta_sha256"] != sha_bytes(expected)):
        raise ValueError("fixed unit delta differs from frozen input")
    output_archive = prefix.with_suffix(".stdout.txt.gz")
    stderr_path = prefix.with_suffix(".stderr.txt")
    receipt = prefix.with_suffix(".solver.json")
    if any(path.exists() for path in (output_archive, stderr_path, receipt)):
        raise FileExistsError("solver evidence already exists")
    solver_name = shutil.which("cryptominisat5")
    if solver_name is None:
        raise FileNotFoundError("CryptoMiniSat 5 is unavailable")
    solver = Path(solver_name).resolve()
    if ref.sha(solver) != cfg["solver_sha256"]:
        raise ValueError("solver binary changed")
    version = subprocess.run([str(solver), "--version"], text=True,
                             capture_output=True, check=True).stdout
    if "CryptoMiniSat version 5.14.7" not in version:
        raise ValueError("solver version changed")
    if process_rss_bytes(os.getpid()) <= 0:
        raise RuntimeError("RSS sampler preflight failed")
    fixed = mode in ("positive", "negative")
    internal = (cfg["fixed_internal_wall_seconds"] if fixed
                else cfg["released_internal_wall_seconds"])
    external = (cfg["fixed_external_wall_seconds"] if fixed
                else cfg["released_external_wall_seconds"])
    with tempfile.TemporaryDirectory(prefix="distinct-s3-run-",
                                     dir=scratch) as temporary:
        base = Path(temporary) / "base.xcnf"
        with gzip.open(archive, "rb") as source, base.open("xb") as dest:
            shutil.copyfileobj(source, dest, length=1 << 20)
        if (ref.sha(base) != base_row["formula_raw_sha256"]
                or base.stat().st_size != base_row["formula_raw_bytes"]):
            raise ValueError("base XCNF differs")
        formula = Path(temporary) / "cell.xcnf"
        variables, constraints, count = compose(base, expected, formula)
        if (ref.sha(formula) != row["formula_sha256"]
                or formula.stat().st_size != row["formula_bytes"]
                or variables != row["variables"]
                or constraints != row["total_constraints"]
                or count != row["unit_count"]):
            raise ValueError("full XCNF differs from precommitted cell")
        command = [str(solver), "--threads=1", f"--maxtime={internal}",
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
                    peak = max(peak, process_rss_bytes(process.pid))
                    if peak > cfg["peak_rss_cap_bytes"]:
                        guard = "RSS_CAP"
                    elif wall > external:
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
        with output_archive.open("xb") as dest:
            with gzip.GzipFile(filename="", mode="wb", fileobj=dest,
                               mtime=0) as zipped:
                zipped.write(raw_output)
        child_peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        if sys.platform != "darwin":
            child_peak *= 1024
        write_json(receipt, {
            "schema": "ecc2k130-263-distinct-s3-solver-v1",
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
            "internal_wall_seconds": internal,
            "external_wall_seconds": external,
            "peak_rss_cap_bytes": cfg["peak_rss_cap_bytes"],
            "wall_seconds": wall,
            "peak_sampled_rss_bytes": peak,
            "peak_child_rss_bytes": child_peak,
            "guard": guard,
            "exit_code": exit_code,
            "terminal_status_lines": terminal,
            "stdout_raw_sha256": sha_bytes(raw_output),
            "stdout_raw_bytes": len(raw_output),
            "stdout_archive_sha256": ref.sha(output_archive),
            "stdout_archive_bytes": output_archive.stat().st_size,
            "stderr_sha256": ref.sha(stderr_path),
        })
    print(json.dumps({"policy": policy, "mode": mode, "status": status,
                      "wall_seconds": wall, "guard": guard}, sort_keys=True),
          flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "freeze", "run"))
    parser.add_argument("--policy", choices=("source", "descendant_native"),
                        required=True)
    parser.add_argument("--mode", choices=("positive", "negative", "x0",
                                           "z0", "x5", "z5"))
    parser.add_argument("--scratch-dir", type=Path, default=Path("/private/tmp"))
    args = parser.parse_args()
    if not args.scratch_dir.is_dir():
        parser.error("scratch directory does not exist")
    if args.action == "build":
        if args.mode is not None:
            parser.error("build does not take a mode")
        build_base(args.policy, args.scratch_dir)
    elif args.action == "freeze":
        if args.mode is not None:
            parser.error("freeze does not take a mode")
        freeze_cells(args.policy, args.scratch_dir)
    else:
        if args.mode is None:
            parser.error("run requires a mode")
        run_cell(args.policy, args.mode, args.scratch_dir)


if __name__ == "__main__":
    main()
