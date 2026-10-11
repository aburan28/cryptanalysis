#!/usr/bin/env python3
"""Freeze and run partially free balanced-S3 root-implication controls."""

import argparse
import gzip
import hashlib
import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/compact-s3-m4-20261003"
Q1419 = PARENT / "q1419_partial_pin"
Q1316 = ROOT / "experiments/compact-s3-m4-external-roots-20261010"
sys.path[:0] = [str(Q1316), str(PARENT), str(Q1419),
                str(ROOT / "ecc2k130/codegen")]
import field  # noqa: E402
from chain_s3 import evaluate_s3  # noqa: E402
from chain_s3_balanced_multitarget import build_balanced  # noqa: E402
from run_cell import read_profile, verify_relation  # noqa: E402
from verify_archive import check_serialized_xcnf, parsed_model  # noqa: E402
from oracle import Counted, roots  # noqa: E402
from experiment import solve  # noqa: E402

PROPOSAL = "Q20261010171000"
FREEZE = HERE / "freeze.json"
CELLS = ("three_leaves", "two_same")
SETTINGS = ("default", "gauss")
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


def flags(n, setting):
    base = ["--verb", "1", "--threads", "1", "--random", "0",
            "--maxconfl", str(MAX_CONFLICTS)]
    if setting == "gauss":
        base += ["--maxmatrixcols", "10000" if n == 53 else "25000",
                 "--autodisablegauss", "0"]
    return base


def make_input(protocol, n, cell_name):
    profile, _, fixture = read_profile(protocol, n)
    assert protocol["cells"][cell_name]["pinned_leaf_indices"][:2] == [0, 1]
    started = time.monotonic()
    original_path = Q1419 / "runs" / f"n{n}_{cell_name}/system.xcnf.gz"
    receipt_path = Q1419 / "runs" / f"n{n}_{cell_name}/receipt.json"
    receipt = read(receipt_path)
    original_bytes = gzip.decompress(original_path.read_bytes())
    assert sha(original_path) == receipt["formula_archive_sha256"]
    assert hashlib.sha256(original_bytes).hexdigest() == receipt[
        "formula_raw_sha256"]
    lines = original_bytes.decode("ascii").splitlines()
    header = lines[0].split()
    assert header[:2] == ["p", "cnf"]
    variables, rows = map(int, header[2:])
    original_cnf = receipt["formula"]["cnf_clauses"]
    assert lines[1+original_cnf].startswith("x")
    f = field.Onb(n)
    witness = fixture["fixture"]
    x, y = (f.fromCoords(witness["raw_leaf_x"][i]) for i in (0, 1))
    ctx = Counted(f)
    oracle_started = time.monotonic()
    values = roots(ctx, x, y)
    assert len(values) == 2
    assert int(witness["raw_pair_sum_points"][0][0]) in values
    assert all(evaluate_s3(f, x, y, value) == 0 for value in values)
    root_coords = [f.toCoords(value) for value in values]
    oracle_seconds = time.monotonic() - oracle_started
    selector = variables + 1
    additions = []
    for i in range(n):
        midpoint = 2 + 4*n + i
        first = midpoint if root_coords[0] >> i & 1 else -midpoint
        second = midpoint if root_coords[1] >> i & 1 else -midpoint
        additions += [f"{-selector} {first} 0", f"{selector} {second} 0"]
    augmented = "\n".join([
        f"p cnf {variables+1} {rows+2*n}",
        *lines[1:1+original_cnf], *additions,
        *lines[1+original_cnf:], ""]).encode("ascii")
    path = HERE / "inputs" / f"n{n}_{cell_name}.xcnf.gz"
    assert not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(augmented, mtime=0))
    return {
        "curve_id": profile["curve_id"], "field_degree_n": n,
        "cell": cell_name,
        "actual_usable_points_B": profile["factor_base_actual_B"],
        "folded_columns_K": profile["folded_columns_K"],
        "factor_base_enumerated_set_sha256": profile[
            "factor_base_enumerated_set_sha256"],
        "workload_id": profile["workload_id"],
        "public_target": profile["public_target"],
        "parent_receipt_sha256": sha(receipt_path),
        "parent_formula_sha256": hashlib.sha256(original_bytes).hexdigest(),
        "augmented_formula_sha256": hashlib.sha256(augmented).hexdigest(),
        "augmented_archive_sha256": sha(path),
        "original_variables": variables,
        "original_rows": rows,
        "original_cnf_clauses": original_cnf,
        "added_variables": 1, "added_cnf_clauses": 2*n,
        "selector_variable": selector,
        "fixed_pair_leaf_x_coords": witness["raw_leaf_x"][:2],
        "root_x_coords": root_coords,
        "oracle_api_counts": ctx.calls,
        "oracle_seconds_exploratory": oracle_seconds,
        "input_construction_seconds_exploratory": time.monotonic()-started,
    }


def freeze():
    protocol = read(Q1419 / "protocol.json")
    binary = Path(shutil.which("cryptominisat5") or "")
    assert binary.is_file()
    cells = {f"n{n}_{cell}": make_input(protocol, n, cell)
             for n in (53, 83) for cell in CELLS}
    order = [[n, cell, setting] for n in (53, 83)
             for cell in CELLS for setting in SETTINGS]
    save(FREEZE, {
        "schema": "q20261010171000-freeze-v1",
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "isogeny": "none", "cells": cells, "order": order,
        "q1419_protocol_sha256": sha(Q1419 / "protocol.json"),
        "q1316_oracle_sha256": sha(Q1316 / "oracle.py"),
        "q1316_runner_sha256": sha(Q1316 / "experiment.py"),
        "source_sha256": {name: sha(HERE / name) for name in
            ("PROTOCOL.md", "runner.py", "audit.py")},
        "solver_path": str(binary), "solver_sha256": sha(binary),
        "settings": list(SETTINGS), "max_conflicts": MAX_CONFLICTS,
        "external_wall_cap_seconds": WALL_CAP_SECONDS,
    })
    print(json.dumps({"status": "FROZEN", "sha256": sha(FREEZE)}))


def check_freeze():
    frozen = read(FREEZE)
    assert frozen["q1419_protocol_sha256"] == sha(Q1419 / "protocol.json")
    assert frozen["q1316_oracle_sha256"] == sha(Q1316 / "oracle.py")
    assert frozen["q1316_runner_sha256"] == sha(Q1316 / "experiment.py")
    assert frozen["solver_sha256"] == sha(frozen["solver_path"])
    for name, digest in frozen["source_sha256"].items():
        assert sha(HERE / name) == digest
    for key, cell in frozen["cells"].items():
        path = HERE / "inputs" / f"{key}.xcnf.gz"
        assert sha(path) == cell["augmented_archive_sha256"]
        assert hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest() == (
            cell["augmented_formula_sha256"])
    return frozen


def run():
    frozen = check_freeze()
    protocol = read(Q1419 / "protocol.json")
    for n, cell_name, setting in frozen["order"]:
        key = f"n{n}_{cell_name}"
        label = f"{key}_{setting}"
        receipt_path = HERE / "runs" / f"{label}.json"
        if receipt_path.exists(): continue
        receipt_path.parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir="/private/tmp") as tmp:
            formula = Path(tmp) / "system.xcnf"
            started = time.monotonic()
            formula.write_bytes(gzip.decompress(
                (HERE / "inputs" / f"{key}.xcnf.gz").read_bytes()))
            decompress_seconds = time.monotonic() - started
            command = [frozen["solver_path"], *flags(n, setting), str(formula)]
            out = HERE / "runs" / f"{label}.stdout"
            err = HERE / "runs" / f"{label}.stderr"
            timing = solve(command, out, err)
            stdout, stderr = out.read_bytes(), err.read_bytes()
            out_gz = out.with_suffix(".stdout.gz")
            err_gz = err.with_suffix(".stderr.gz")
            out_gz.write_bytes(gzip.compress(stdout, mtime=0))
            err_gz.write_bytes(gzip.compress(stderr, mtime=0))
            out.unlink(); err.unlink()
            text = stdout.decode(errors="replace")
            status = {10:"SAT",20:"UNSAT"}.get(timing["return_code"],
                                                  "BOUNDED_UNKNOWN")
            matches = re.findall(r"Conflicts in UIP\s*:\s*(\d+)", text)
            relation = None
            replay_started = time.monotonic()
            if status == "SAT":
                model = parsed_model(text)
                assert model is not None
                check_serialized_xcnf(formula.read_bytes(), model)
                profile, parent, _ = read_profile(protocol, n)
                _, leaves, _, _, _ = build_balanced(
                    n, profile["normal_basis_weight_bound"],
                    parent["raw_preimage_x_coordinates"])
                relation = verify_relation(profile, model, leaves)
                assert relation["status"] == "verified_four_point_relation"
            replay_seconds = time.monotonic() - replay_started
            cell = frozen["cells"][key]
            save(receipt_path, {
                "schema": "q20261010171000-run-v1",
                "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
                "isogeny": "none", "field_degree_n": n,
                "cell": cell_name, "setting": setting,
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
                "conflicts_reported": int(matches[-1]) if matches else None,
                "decompression_seconds_exploratory": decompress_seconds,
                "relation_check_seconds_exploratory": replay_seconds,
                "stdout_gzip_sha256": sha(out_gz),
                "stderr_gzip_sha256": sha(err_gz),
                "relation": relation, **timing,
            })
            print(json.dumps({"cell":label,"status":status,
                "conflicts":int(matches[-1]) if matches else None,
                "solver_seconds":round(timing["solver_wall_seconds_exploratory"],3)}),
                flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze","check","run"))
    action = parser.parse_args().action
    if action == "freeze": freeze()
    elif action == "check":
        check_freeze(); print("PASS: freeze")
    else: run()
