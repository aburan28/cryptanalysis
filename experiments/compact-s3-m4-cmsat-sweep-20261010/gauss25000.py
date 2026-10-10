#!/usr/bin/env python3
"""Frozen N83 Gaussian-width follow-up on the same S3 formulas."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import tempfile
import time
from pathlib import Path

from sweep import HERE, PROPOSAL, WALL_CAP_SECONDS, MAX_CONFLICTS, execute, sha

FLAGS = ["--verb", "1", "--threads", "1", "--random", "0",
         "--maxconfl", str(MAX_CONFLICTS), "--maxmatrixcols", "25000",
         "--autodisablegauss", "0"]
INPUTS = ("n83_ordinary", "n83_satisfiable_control")
FREEZE = HERE / "gauss25000.freeze.json"
OUT = HERE / "gauss25000"


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def write_new(path: Path, data: dict) -> None:
    assert not path.exists()
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")


def freeze() -> None:
    parent = read(HERE / "freeze.json")
    assert parent["source_sha256"]["sweep.py"] == sha(HERE / "sweep.py")
    for name in INPUTS:
        assert parent["inputs"][name]["raw_sha256"] == hashlib.sha256(
            gzip.decompress(Path(parent["inputs"][name]["path"]).read_bytes())
        ).hexdigest()
    write_new(FREEZE, {
        "schema": "q20261010125300-gauss25000-freeze-v1",
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "isogeny": "none", "parent_freeze_sha256": sha(HERE / "freeze.json"),
        "source_sha256": sha(Path(__file__)),
        "parent_runner_sha256": sha(HERE / "sweep.py"),
        "solver_sha256": parent["solver_sha256"],
        "formula_raw_sha256": {name: parent["inputs"][name]["raw_sha256"]
                               for name in INPUTS},
        "input_names": list(INPUTS), "flags": FLAGS,
        "external_wall_cap_seconds": WALL_CAP_SECONDS,
        "rationale": "N83's 20916-column Gaussian matrix was rejected by the 10000-column setting in the first frozen cohort.",
    })
    print(json.dumps({"status": "FROZEN", "sha256": sha(FREEZE)}))


def check() -> tuple[dict, dict]:
    frozen = read(FREEZE)
    parent = read(HERE / "freeze.json")
    assert frozen["source_sha256"] == sha(Path(__file__))
    assert frozen["parent_freeze_sha256"] == sha(HERE / "freeze.json")
    assert frozen["parent_runner_sha256"] == sha(HERE / "sweep.py")
    assert frozen["solver_sha256"] == parent["solver_sha256"] == sha(
        Path(parent["solver_path"]))
    assert frozen["flags"] == FLAGS and frozen["input_names"] == list(INPUTS)
    return frozen, parent


def run() -> None:
    frozen, parent = check()
    OUT.mkdir(exist_ok=True)
    for name in INPUTS:
        receipt = OUT / f"{name}.json"
        if receipt.exists():
            continue
        with tempfile.TemporaryDirectory(prefix="q1253-g25-", dir="/private/tmp") as tmp:
            formula = Path(tmp) / "system.xcnf"
            start = time.monotonic()
            formula.write_bytes(gzip.decompress(
                Path(parent["inputs"][name]["path"]).read_bytes()))
            decompress_seconds = time.monotonic() - start
            command = [parent["solver_path"], *FLAGS, str(formula)]
            stdout_path = OUT / f"{name}.stdout"
            stderr_path = OUT / f"{name}.stderr"
            assert not stdout_path.exists() and not stderr_path.exists()
            execution = execute(command, stdout_path, stderr_path)
            stdout = stdout_path.read_bytes()
            stderr = stderr_path.read_bytes()
            out_gz = OUT / f"{name}.stdout.gz"
            err_gz = OUT / f"{name}.stderr.gz"
            out_gz.write_bytes(gzip.compress(stdout, mtime=0))
            err_gz.write_bytes(gzip.compress(stderr, mtime=0))
            stdout_path.unlink()
            stderr_path.unlink()
            output = stdout.decode(errors="replace")
            matrices = [int(x) for x in re.findall(
                r"\[matrix\] Using ([0-9]+) matrices", output)]
            status = ("SAT" if execution["return_code"] == 10
                      else "UNSAT" if execution["return_code"] == 20
                      else "BOUNDED_UNKNOWN")
            write_new(receipt, {
                "schema": "q20261010125300-gauss25000-cell-v1",
                "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
                "isogeny": "none", "input_name": name,
                "curve_id": parent["profiles"]["83"]["curve_id"],
                "actual_usable_points_B": parent["profiles"]["83"][
                    "actual_usable_points_B"],
                "folded_columns_K": parent["profiles"]["83"]["folded_columns_K"],
                "factor_base_enumerated_set_sha256": parent["profiles"]["83"][
                    "factor_base_enumerated_set_sha256"],
                "freeze_sha256": sha(FREEZE),
                "formula_raw_sha256": parent["inputs"][name]["raw_sha256"],
                "solver_sha256": parent["solver_sha256"],
                "flags": FLAGS, "status": status,
                "gaussian_matrices_active": max(matrices) if matrices else None,
                "formula_decompression_seconds_exploratory":
                    decompress_seconds,
                "stdout_gzip_sha256": sha(out_gz),
                "stderr_gzip_sha256": sha(err_gz),
                **execution,
            })
            print(json.dumps({"input": name, "status": status,
                              "matrices": max(matrices) if matrices else None,
                              "wall_seconds": round(execution[
                                  "wall_seconds_exploratory"], 3)}), flush=True)


def audit() -> None:
    frozen, parent = check()
    rows = []
    for name in INPUTS:
        receipt = read(OUT / f"{name}.json")
        stdout = gzip.decompress((OUT / f"{name}.stdout.gz").read_bytes())
        stderr = gzip.decompress((OUT / f"{name}.stderr.gz").read_bytes())
        assert receipt["freeze_sha256"] == sha(FREEZE)
        assert receipt["formula_raw_sha256"] == frozen[
            "formula_raw_sha256"][name] == parent["inputs"][name][
                "raw_sha256"]
        assert receipt["stdout_gzip_sha256"] == sha(
            OUT / f"{name}.stdout.gz")
        assert receipt["stderr_gzip_sha256"] == sha(
            OUT / f"{name}.stderr.gz")
        assert not stderr.strip()
        assert b"c rst" in stdout
        matrices = [int(x) for x in re.findall(
            rb"\[matrix\] Using ([0-9]+) matrices", stdout)]
        assert receipt["gaussian_matrices_active"] == (
            max(matrices) if matrices else None)
        assert receipt["status"] == (
            "SAT" if receipt["return_code"] == 10
            else "UNSAT" if receipt["return_code"] == 20
            else "BOUNDED_UNKNOWN")
        rows.append({"input_name": name, "status": receipt["status"],
                     "gaussian_matrices_active": receipt[
                         "gaussian_matrices_active"],
                     "wall_seconds_exploratory": receipt[
                         "wall_seconds_exploratory"]})
    write_new(HERE / "gauss25000.audit.json", {
        "schema": "q20261010125300-gauss25000-audit-v1",
        "proposal_id": PROPOSAL, "status": "PASS", "rows": rows,
        "freeze_sha256": sha(FREEZE),
        "source_sha256": sha(Path(__file__)),
    })
    print(json.dumps({"status": "PASS", "cells": len(rows)}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check", "run", "audit"))
    action = parser.parse_args().action
    if action == "freeze":
        freeze()
    elif action == "check":
        check()
        print("PASS: Gaussian-width follow-up freeze")
    elif action == "run":
        run()
    else:
        audit()


if __name__ == "__main__":
    main()
