#!/usr/bin/env python3
"""Freeze and run Q1419's balanced-S3 controls with external midpoint roots."""

import argparse
import gzip
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/compact-s3-m4-20261003"
Q1419 = PARENT / "q1419_partial_pin"
sys.path[:0] = [str(PARENT), str(Q1419), str(ROOT / "ecc2k130/codegen")]
import field  # noqa: E402
from chain_s3 import evaluate_s3  # noqa: E402
from chain_s3_balanced_multitarget import build_balanced  # noqa: E402
from run_cell import pin_bits, read_profile, verify_relation  # noqa: E402
from verify_archive import check_serialized_xcnf, parsed_model  # noqa: E402
from oracle import Counted, roots  # noqa: E402

PROPOSAL = "Q20261010131600"
FREEZE = HERE / "freeze.json"
MAX_CONFLICTS = 1_000_000
WALL_CAP_SECONDS = 60


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    assert not path.exists(), path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def make_cell(protocol, n):
    profile, parent, fixture = read_profile(protocol, n)
    f = field.Onb(n)
    witness = fixture["fixture"]
    started = time.monotonic()
    formula, leaves, mids, _, selector = build_balanced(
        n, profile["normal_basis_weight_bound"],
        parent["raw_preimage_x_coordinates"])
    for bits, x in zip(leaves, witness["raw_leaf_x"]):
        pin_bits(formula, bits, x)
    choice = parent["raw_preimage_x_coordinates"].index(
        f.toCoords(int(witness["raw_sum"][0])))
    pin_bits(formula, selector, choice)
    original_vars, original_cnf = formula.variables, len(formula.clauses)
    with tempfile.TemporaryDirectory(dir="/private/tmp") as tmp:
        original_path = Path(tmp) / "original.xcnf"
        formula.write(original_path)
        original_bytes = original_path.read_bytes()
    parent_path = Q1419 / "runs" / f"n{n}_free_mids/system.xcnf.gz"
    assert original_bytes == gzip.decompress(parent_path.read_bytes())
    ctx = Counted(f)
    root_sets = []
    oracle_started = time.monotonic()
    for j, bits in enumerate(mids):
        x, y = (f.fromCoords(witness["raw_leaf_x"][2*j+k]) for k in (0, 1))
        values = roots(ctx, x, y)
        assert len(values) == 2
        assert int(witness["raw_pair_sum_points"][j][0]) in values
        assert all(evaluate_s3(f, x, value, y) == 0 for value in values)
        coords = [f.toCoords(value) for value in values]
        select = formula.new()
        for i, bit in enumerate(bits):
            first = bit if coords[0] >> i & 1 else -bit
            second = bit if coords[1] >> i & 1 else -bit
            formula.clauses.extend(([-select, first], [select, second]))
        root_sets.append({"pair": j,
                          "leaf_x_coords": witness["raw_leaf_x"][2*j:2*j+2],
                          "root_x_coords": coords,
                          "selector_variable": select})
    oracle_seconds = time.monotonic() - oracle_started
    with tempfile.TemporaryDirectory(dir="/private/tmp") as tmp:
        augmented_path = Path(tmp) / "augmented.xcnf"
        formula.write(augmented_path)
        augmented = augmented_path.read_bytes()
    out = HERE / "inputs" / f"n{n}.xcnf.gz"
    assert not out.exists()
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(gzip.compress(augmented, mtime=0))
    return {
        "field_degree_n": n, "curve_id": profile["curve_id"],
        "actual_usable_points_B": profile["factor_base_actual_B"],
        "folded_columns_K": profile["folded_columns_K"],
        "factor_base_enumerated_set_sha256": profile[
            "factor_base_enumerated_set_sha256"],
        "workload_id": profile["workload_id"],
        "public_target": profile["public_target"],
        "parent_receipt_sha256": sha(Q1419 / "runs" /
                                      f"n{n}_free_mids/receipt.json"),
        "parent_formula_sha256": hashlib.sha256(original_bytes).hexdigest(),
        "augmented_formula_sha256": hashlib.sha256(augmented).hexdigest(),
        "augmented_archive_sha256": sha(out),
        "original_variables": original_vars,
        "original_cnf_clauses": original_cnf,
        "added_variables": formula.variables - original_vars,
        "added_cnf_clauses": len(formula.clauses) - original_cnf,
        "root_sets": root_sets,
        "oracle_api_counts": ctx.calls,
        "oracle_seconds_exploratory": oracle_seconds,
        "formula_construction_seconds_exploratory": time.monotonic() - started,
    }


def freeze():
    protocol = read(Q1419 / "protocol.json")
    assert protocol["proposal_id"] == "Q1419"
    for path, digest in protocol["dependency_sha256"].items():
        assert sha(ROOT / path) == digest
    binary = Path(shutil.which("cryptominisat5") or "")
    assert binary.is_file()
    cells = {str(n): make_cell(protocol, n) for n in (53, 83)}
    data = {
        "schema": "q20261010131600-freeze-v1",
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "isogeny": "none", "cells": cells,
        "q1419_protocol_sha256": sha(Q1419 / "protocol.json"),
        "source_sha256": {name: sha(HERE / name) for name in
            ("PROTOCOL.md", "oracle.py", "experiment.py", "audit.py")},
        "solver_path": str(binary), "solver_sha256": sha(binary),
        "solver_threads": 1, "solver_seed": 0,
        "max_conflicts": MAX_CONFLICTS,
        "external_wall_cap_seconds": WALL_CAP_SECONDS,
    }
    save(FREEZE, data)
    print(json.dumps({"status": "FROZEN", "sha256": sha(FREEZE)}))


def check_freeze():
    data = read(FREEZE)
    assert data["q1419_protocol_sha256"] == sha(Q1419 / "protocol.json")
    assert data["solver_sha256"] == sha(data["solver_path"])
    for name, digest in data["source_sha256"].items():
        assert sha(HERE / name) == digest
    for n in (53, 83):
        cell = data["cells"][str(n)]
        path = HERE / "inputs" / f"n{n}.xcnf.gz"
        assert sha(path) == cell["augmented_archive_sha256"]
        assert hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest() == (
            cell["augmented_formula_sha256"])
    return data


def solve(command, out, err):
    started = time.monotonic()
    timeout = False
    with out.open("wb") as stdout, err.open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        while True:
            pid, status, usage = os.wait4(process.pid, os.WNOHANG)
            if pid:
                break
            if time.monotonic() - started >= WALL_CAP_SECONDS:
                timeout = True
                process.kill()
                _, status, usage = os.wait4(process.pid, 0)
                break
            time.sleep(0.02)
    return {"return_code": os.waitstatus_to_exitcode(status),
            "external_timeout": timeout,
            "solver_wall_seconds_exploratory": time.monotonic() - started,
            "peak_child_rss_raw": usage.ru_maxrss,
            "peak_child_rss_unit": "bytes" if platform.system() == "Darwin"
                                   else "kilobytes",
            "child_user_seconds": usage.ru_utime,
            "child_system_seconds": usage.ru_stime}


def run():
    frozen = check_freeze()
    for n in (53, 83):
        receipt_path = HERE / "runs" / f"n{n}.json"
        if receipt_path.exists():
            continue
        receipt_path.parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir="/private/tmp") as tmp:
            formula = Path(tmp) / "system.xcnf"
            started = time.monotonic()
            formula.write_bytes(gzip.decompress(
                (HERE / "inputs" / f"n{n}.xcnf.gz").read_bytes()))
            decompression = time.monotonic() - started
            command = [frozen["solver_path"], "--verb", "1", "--threads", "1",
                       "--random", "0", "--maxconfl", str(MAX_CONFLICTS),
                       str(formula)]
            out = HERE / "runs" / f"n{n}.stdout"
            err = HERE / "runs" / f"n{n}.stderr"
            timing = solve(command, out, err)
            stdout, stderr = out.read_bytes(), err.read_bytes()
            out_gz = out.with_suffix(".stdout.gz")
            err_gz = err.with_suffix(".stderr.gz")
            out_gz.write_bytes(gzip.compress(stdout, mtime=0))
            err_gz.write_bytes(gzip.compress(stderr, mtime=0))
            out.unlink(); err.unlink()
            text = stdout.decode(errors="replace")
            status = {10: "SAT", 20: "UNSAT"}.get(timing["return_code"],
                                                    "BOUNDED_UNKNOWN")
            conflicts = re.findall(r"Conflicts in UIP\s*:\s*(\d+)", text)
            relation = None
            if status == "SAT":
                model = parsed_model(text)
                assert model is not None
                check_serialized_xcnf(formula.read_bytes(), model)
                profile, parent, _ = read_profile(read(Q1419 / "protocol.json"), n)
                _, leaves, _, _, _ = build_balanced(
                    n, profile["normal_basis_weight_bound"],
                    parent["raw_preimage_x_coordinates"])
                relation = verify_relation(profile, model, leaves)
                assert relation["status"] == "verified_four_point_relation"
            cell = frozen["cells"][str(n)]
            save(receipt_path, {
                "schema": "q20261010131600-run-v1",
                "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
                "isogeny": "none", "field_degree_n": n,
                "curve_id": cell["curve_id"],
                "actual_usable_points_B": cell["actual_usable_points_B"],
                "folded_columns_K": cell["folded_columns_K"],
                "factor_base_enumerated_set_sha256": cell[
                    "factor_base_enumerated_set_sha256"],
                "workload_id": cell["workload_id"],
                "public_target": cell["public_target"],
                "freeze_sha256": sha(FREEZE),
                "formula_sha256": cell["augmented_formula_sha256"],
                "solver_sha256": frozen["solver_sha256"],
                "solver_flags": command[1:-1], "status": status,
                "conflicts_reported": int(conflicts[-1]) if conflicts else None,
                "decompression_seconds_exploratory": decompression,
                "stdout_gzip_sha256": sha(out_gz),
                "stderr_gzip_sha256": sha(err_gz),
                "relation": relation, **timing,
            })
            print(json.dumps({"n": n, "status": status,
                              "conflicts": int(conflicts[-1]) if conflicts else None,
                              "solver_seconds": round(timing[
                                  "solver_wall_seconds_exploratory"], 3)}),
                  flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check", "run"))
    action = parser.parse_args().action
    if action == "freeze": freeze()
    elif action == "check":
        check_freeze(); print("PASS: freeze")
    else: run()
