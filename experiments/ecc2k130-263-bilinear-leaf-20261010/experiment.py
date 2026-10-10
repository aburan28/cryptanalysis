#!/usr/bin/env python3
"""Freeze and execute paired selector-weighted W24 XCNF cells."""

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

import bilinear


HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/R1"
sys.path.insert(0, str(bilinear.PARENT))
import distinct  # noqa: E402


ref = bilinear.ref


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def checked_config():
    cfg = ref.read(HERE / "CONFIG.json")
    parent_cfg = distinct.config()
    pins = {
        bilinear.PARENT / "CONFIG.json": "parent_config_sha256",
        bilinear.PARENT / "runs/R1/witness.json": "parent_witness_sha256",
        bilinear.PARENT / "runs/R1/source_base.xcnf.gz":
            "parent_source_base_gzip_sha256",
        bilinear.PARENT / "runs/R1/descendant_native_base.xcnf.gz":
            "parent_descendant_native_base_gzip_sha256",
        bilinear.PARENT / "distinct.py": "parent_distinct_source_sha256",
        bilinear.PARENT / "audit.py": "parent_audit_source_sha256",
        bilinear.finite.ref.HERE / "field.py": "field_source_sha256",
        bilinear.finite.ref.HERE / "build_formula.py": "finite_builder_sha256",
        bilinear.projective.HERE / "build_projective.py":
            "projective_builder_sha256",
        bilinear.SAT / "build_control.py": "sat_builder_sha256",
        ref.CODEGEN / "build.py": "codegen_build_sha256",
        ref.CODEGEN / "ir.py": "codegen_ir_sha256",
        ref.CODEGEN / "cnf.py": "codegen_cnf_sha256",
    }
    if (cfg["schema"] != "ecc2k130-263-bilinear-leaf-v1"
            or cfg["parent_commit"]
            != "f3e4829f980e43ae995522286e18fe5e18cd8d86"
            or any(ref.sha(path) != cfg[key] for path, key in pins.items())
            or cfg["policies"] != parent_cfg["policies"]
            or cfg["variants"] != list(bilinear.VARIANTS)
            or cfg["modes"] != parent_cfg["modes"]
            or cfg["solver_sha256"] != parent_cfg["solver_sha256"]
            or cfg["peak_rss_cap_bytes"] != parent_cfg["peak_rss_cap_bytes"]
            or cfg["fixed_positive_units"]
            != parent_cfg["fixed_positive_units"]
            or cfg["single_coordinate_fixed_units"]
            != parent_cfg["single_coordinate_fixed_units"]):
        raise ValueError("frozen source, parent, or configuration changed")
    eq = ref.read(RUN / "equivalence.json")
    if (eq["status"] != "PASS_BOTH_CURVES_AND_VARIANTS"
            or eq["config_sha256"] != ref.sha(HERE / "CONFIG.json")
            or eq["builder_sha256"] != ref.sha(HERE / "bilinear.py")
            or eq["equivalence_source_sha256"]
            != ref.sha(HERE / "equivalence.py")):
        raise ValueError("circuit equivalence has not passed")
    return cfg, parent_cfg, distinct.witness(parent_cfg)


def base_paths(policy, variant):
    stem = f"{policy}_{variant}"
    return (RUN / f"{stem}_base.xcnf.gz",
            RUN / f"{stem}_inputs.json",
            RUN / f"{stem}_base.json")


def build_base(policy, variant, scratch):
    cfg, _, witness = checked_config()
    archive, map_path, receipt = base_paths(policy, variant)
    if any(path.exists() for path in (archive, map_path, receipt)):
        raise FileExistsError("base evidence exists")
    target_x = witness["policies"][policy]["target_x"]
    choices = [target_x] + [target_x ^ 1] * 3
    started = time.perf_counter()
    prog, roots, leaves, _ = bilinear.build_ir(policy, variant)
    ir_ops = prog.opCount(roots)
    formula, choice, inputs = bilinear.control.encode_with_map(
        policy, prog, roots, leaves, choices)
    with tempfile.TemporaryDirectory(prefix="bilinear-build-",
                                     dir=scratch) as temporary:
        raw = Path(temporary) / "base.xcnf"
        formula.writeDimacs(raw)
        raw_sha, raw_bytes = ref.sha(raw), raw.stat().st_size
        RUN.mkdir(parents=True, exist_ok=True)
        with raw.open("rb") as source, archive.open("xb") as target:
            with gzip.GzipFile(filename="", mode="wb", fileobj=target,
                               mtime=0) as zipped:
                shutil.copyfileobj(source, zipped, length=1 << 20)
    named = {f"{name}:{bit}": variable
             for (name, bit), variable in inputs.items()}
    write_json(map_path, named)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        peak *= 1024
    row = {
        "schema": "ecc2k130-263-bilinear-base-v1",
        "status": "CONTROL_FORMULA_BUILT",
        "policy": policy, "variant": variant, "candidate_id": None,
        "target_x_choices": [str(x) for x in choices],
        "target_selector_variables": choice,
        "formula_raw_sha256": raw_sha,
        "formula_raw_bytes": raw_bytes,
        "formula_gzip_sha256": ref.sha(archive),
        "formula_gzip_bytes": archive.stat().st_size,
        "input_vars_sha256": ref.sha(map_path),
        "input_vars_count": len(named),
        "stats": formula.stats(),
        "ir_operations": ir_ops,
        "config_sha256": ref.sha(HERE / "CONFIG.json"),
        "equivalence_sha256": ref.sha(RUN / "equivalence.json"),
        "parent_witness_sha256": cfg["parent_witness_sha256"],
        "builder_sha256": ref.sha(HERE / "bilinear.py"),
        "producer_sha256": ref.sha(Path(__file__)),
        "build_wall_seconds": time.perf_counter() - started,
        "peak_process_rss_bytes": peak,
    }
    write_json(receipt, row)
    print(json.dumps({"policy": policy, "variant": variant,
                      "stats": row["stats"], "ir_operations": ir_ops,
                      "build_wall_seconds": row["build_wall_seconds"],
                      "peak_process_rss_bytes": peak}, sort_keys=True),
          flush=True)


def read_base(policy, variant, cfg, witness):
    archive, map_path, receipt = base_paths(policy, variant)
    base, inputs = ref.read(receipt), ref.read(map_path)
    target = witness["policies"][policy]["target_x"]
    if (base["schema"] != "ecc2k130-263-bilinear-base-v1"
            or base["status"] != "CONTROL_FORMULA_BUILT"
            or base["policy"] != policy or base["variant"] != variant
            or base["target_x_choices"]
            != [str(target)] + [str(target ^ 1)] * 3
            or base["formula_gzip_sha256"] != ref.sha(archive)
            or base["input_vars_sha256"] != ref.sha(map_path)
            or base["input_vars_count"] != len(inputs)
            or base["config_sha256"] != ref.sha(HERE / "CONFIG.json")
            or base["equivalence_sha256"]
            != ref.sha(RUN / "equivalence.json")
            or base["parent_witness_sha256"]
            != cfg["parent_witness_sha256"]
            or base["builder_sha256"] != ref.sha(HERE / "bilinear.py")
            or base["producer_sha256"] != ref.sha(Path(__file__))):
        raise ValueError("base formula or receipt changed")
    return archive, inputs, base


def freeze_cells(policy, variant, scratch):
    cfg, parent_cfg, witness = checked_config()
    archive, inputs, base_row = read_base(policy, variant, cfg, witness)
    receipt = RUN / f"{policy}_{variant}_cells.json"
    if receipt.exists():
        raise FileExistsError(receipt)
    rows = {}
    control = witness["policies"][policy]
    with tempfile.TemporaryDirectory(prefix="bilinear-freeze-",
                                     dir=scratch) as temporary:
        base = Path(temporary) / "base.xcnf"
        with gzip.open(archive, "rb") as source, base.open("xb") as target:
            shutil.copyfileobj(source, target, length=1 << 20)
        if (ref.sha(base) != base_row["formula_raw_sha256"]
                or base.stat().st_size != base_row["formula_raw_bytes"]):
            raise ValueError("base archive differs")
        for mode in cfg["modes"]:
            raw_units = distinct.unit_bytes(distinct.exact_units(
                mode, control, inputs,
                base_row["target_selector_variables"], parent_cfg))
            path = RUN / f"{policy}_{variant}_{mode}.units.txt"
            if path.exists():
                raise FileExistsError(path)
            formula = Path(temporary) / f"{mode}.xcnf"
            variables, constraints, count = distinct.compose(
                base, raw_units, formula)
            path.write_bytes(raw_units)
            rows[mode] = {
                "unit_count": count,
                "target_choice": int(mode == "negative"),
                "released_coordinate_bits":
                    cfg["released_coordinate_bits"]
                    if mode in ("x0", "z0", "x5", "z5") else 0,
                "unit_delta_sha256": digest(raw_units),
                "formula_sha256": ref.sha(formula),
                "formula_bytes": formula.stat().st_size,
                "variables": variables,
                "total_constraints": constraints,
            }
    write_json(receipt, {
        "schema": "ecc2k130-263-bilinear-cells-v1",
        "status": "PASS_SIX_EXACT_INPUTS",
        "policy": policy, "variant": variant,
        "config_sha256": ref.sha(HERE / "CONFIG.json"),
        "producer_sha256": ref.sha(Path(__file__)),
        "parent_witness_sha256": cfg["parent_witness_sha256"],
        "base_receipt_sha256": ref.sha(base_paths(policy, variant)[2]),
        "base_gzip_sha256": ref.sha(archive),
        "input_vars_sha256": ref.sha(base_paths(policy, variant)[1]),
        "cells": rows,
    })
    print(json.dumps({"policy": policy, "variant": variant,
                      "unit_counts": {mode: row["unit_count"]
                                      for mode, row in rows.items()}},
                     sort_keys=True), flush=True)


def run_cell(policy, variant, mode, scratch):
    cfg, parent_cfg, witness = checked_config()
    archive, inputs, base = read_base(policy, variant, cfg, witness)
    cells_path = RUN / f"{policy}_{variant}_cells.json"
    cells = ref.read(cells_path)
    row = cells["cells"][mode]
    if (cells["status"] != "PASS_SIX_EXACT_INPUTS"
            or cells["config_sha256"] != ref.sha(HERE / "CONFIG.json")
            or cells["producer_sha256"] != ref.sha(Path(__file__))
            or cells["base_receipt_sha256"]
            != ref.sha(base_paths(policy, variant)[2])
            or cells["base_gzip_sha256"] != ref.sha(archive)):
        raise ValueError("frozen cell receipt differs")
    raw_units = distinct.unit_bytes(distinct.exact_units(
        mode, witness["policies"][policy], inputs,
        base["target_selector_variables"], parent_cfg))
    prefix = RUN / f"{policy}_{variant}_{mode}"
    delta = prefix.with_suffix(".units.txt")
    stdout_archive = prefix.with_suffix(".stdout.txt.gz")
    stderr_path = prefix.with_suffix(".stderr.txt")
    receipt = prefix.with_suffix(".solver.json")
    if (delta.read_bytes() != raw_units
            or row["unit_delta_sha256"] != digest(raw_units)):
        raise ValueError("unit delta differs from frozen input")
    if any(path.exists() for path in (stdout_archive, stderr_path, receipt)):
        raise FileExistsError("solver evidence exists")
    solver_name = shutil.which("cryptominisat5")
    if solver_name is None:
        raise FileNotFoundError("CryptoMiniSat 5 unavailable")
    solver = Path(solver_name).resolve()
    if ref.sha(solver) != cfg["solver_sha256"]:
        raise ValueError("solver binary changed")
    version = subprocess.run([str(solver), "--version"], text=True,
                             capture_output=True, check=True).stdout
    if "CryptoMiniSat version 5.14.7" not in version:
        raise ValueError("solver version changed")
    if distinct.process_rss_bytes(os.getpid()) <= 0:
        raise RuntimeError("RSS sampler preflight failed")
    fixed = mode in ("positive", "negative")
    internal = (cfg["fixed_internal_wall_seconds"] if fixed
                else cfg["released_internal_wall_seconds"])
    external = (cfg["fixed_external_wall_seconds"] if fixed
                else cfg["released_external_wall_seconds"])
    with tempfile.TemporaryDirectory(prefix="bilinear-run-",
                                     dir=scratch) as temporary:
        base_file = Path(temporary) / "base.xcnf"
        with gzip.open(archive, "rb") as source, base_file.open("xb") as target:
            shutil.copyfileobj(source, target, length=1 << 20)
        if (ref.sha(base_file) != base["formula_raw_sha256"]
                or base_file.stat().st_size != base["formula_raw_bytes"]):
            raise ValueError("base XCNF changed")
        formula = Path(temporary) / "cell.xcnf"
        variables, constraints, count = distinct.compose(
            base_file, raw_units, formula)
        if (ref.sha(formula) != row["formula_sha256"]
                or formula.stat().st_size != row["formula_bytes"]
                or variables != row["variables"]
                or constraints != row["total_constraints"]
                or count != row["unit_count"]):
            raise ValueError("complete solver input changed")
        command = [str(solver), "--threads=1", f"--maxtime={internal}",
                   "--verb=1", "--printsol=1", str(formula)]
        stdout_path = Path(temporary) / "stdout.txt"
        started = time.perf_counter()
        guard, peak = None, 0
        with stdout_path.open("xb") as stdout, stderr_path.open("x") as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                       start_new_session=True)
            try:
                while process.poll() is None:
                    wall = time.perf_counter() - started
                    peak = max(peak, distinct.process_rss_bytes(process.pid))
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
        with stdout_archive.open("xb") as target:
            with gzip.GzipFile(filename="", mode="wb", fileobj=target,
                               mtime=0) as zipped:
                zipped.write(raw_output)
        child_peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        if sys.platform != "darwin":
            child_peak *= 1024
        write_json(receipt, {
            "schema": "ecc2k130-263-bilinear-solver-v1",
            "status": status,
            "policy": policy, "variant": variant, "mode": mode,
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
            "stdout_raw_sha256": digest(raw_output),
            "stdout_raw_bytes": len(raw_output),
            "stdout_archive_sha256": ref.sha(stdout_archive),
            "stdout_archive_bytes": stdout_archive.stat().st_size,
            "stderr_sha256": ref.sha(stderr_path),
        })
    print(json.dumps({"policy": policy, "variant": variant, "mode": mode,
                      "status": status, "wall_seconds": wall,
                      "guard": guard}, sort_keys=True), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "freeze", "run"))
    parser.add_argument("--policy", choices=bilinear.finite.POLICIES,
                        required=True)
    parser.add_argument("--variant", choices=bilinear.VARIANTS, required=True)
    parser.add_argument("--mode", choices=("positive", "negative", "x0",
                                           "z0", "x5", "z5"))
    parser.add_argument("--scratch-dir", type=Path, default=Path("/private/tmp"))
    args = parser.parse_args()
    if not args.scratch_dir.is_dir():
        parser.error("scratch directory does not exist")
    if args.action == "build":
        if args.mode is not None:
            parser.error("build does not take mode")
        build_base(args.policy, args.variant, args.scratch_dir)
    elif args.action == "freeze":
        if args.mode is not None:
            parser.error("freeze does not take mode")
        freeze_cells(args.policy, args.variant, args.scratch_dir)
    else:
        if args.mode is None:
            parser.error("run requires mode")
        run_cell(args.policy, args.variant, args.mode, args.scratch_dir)


if __name__ == "__main__":
    main()
