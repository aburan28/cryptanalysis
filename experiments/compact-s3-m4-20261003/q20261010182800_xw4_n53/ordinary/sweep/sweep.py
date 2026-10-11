#!/usr/bin/env python3
"""Four frozen CryptoMiniSat settings on one ordinary N53 x-W4 XCNF."""

import argparse
import gzip
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))
import experiment as parent  # noqa: E402

PROPOSAL = "Q20261010184000"
WALL_CAP = 300
CONFLICT_CAP = 100_000
SETTINGS = [
    ("polar_false", ["--polar", "false", "--random", "0"]),
    ("polar_true", ["--polar", "true", "--random", "0"]),
    ("luby_false", ["--polar", "false", "--restart", "luby",
                    "--random", "0"]),
    ("geom_seed1_false", ["--polar", "false", "--restart", "geom",
                          "--random", "1"]),
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, row):
    assert not path.exists(), path
    path.write_text(json.dumps(row, sort_keys=True, indent=2) + "\n")


def freeze():
    frozen = parent.check()
    prepared = load(PARENT / "prepare.json")
    assert prepared["freeze_sha256"] == digest(PARENT / "freeze.json")
    save(HERE / "freeze.json", {
        "schema": "q20261010184000-freeze-v1", "proposal_id": PROPOSAL,
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "curve_id": frozen["curve_id"], "workload_id": frozen["workload_id"],
        "public_target": frozen["public_target"],
        "actual_usable_points_B": frozen["actual_usable_points_B"],
        "folded_columns_K": frozen["folded_columns_K"],
        "factor_base_enumerated_set_sha256": frozen[
            "factor_base_enumerated_set_sha256"],
        "parent_freeze_sha256": digest(PARENT / "freeze.json"),
        "parent_prepare_sha256": digest(PARENT / "prepare.json"),
        "parent_experiment_sha256": digest(PARENT / "experiment.py"),
        "formula_archive_sha256": digest(PARENT / "formula.xcnf.gz"),
        "formula_sha256": prepared["formula_sha256"],
        "solver_path": frozen["solver_path"],
        "solver_sha256": frozen["solver_sha256"],
        "common_solver_flags": ["--verb", "1", "--threads", "1",
                                "--maxconfl", str(CONFLICT_CAP)],
        "cells": [{"name": name, "extra_flags": flags}
                  for name, flags in SETTINGS],
        "external_wall_cap_seconds_per_cell": WALL_CAP,
        "source_sha256": {name: digest(HERE / name) for name in
                          ("PROTOCOL.md", "sweep.py", "audit.py")}})
    print(json.dumps({"freeze_sha256": digest(HERE / "freeze.json")}))


def check():
    frozen = load(HERE / "freeze.json")
    base = parent.check()
    prepared = load(PARENT / "prepare.json")
    assert frozen["parent_freeze_sha256"] == digest(PARENT / "freeze.json")
    assert frozen["parent_prepare_sha256"] == digest(PARENT / "prepare.json")
    assert frozen["parent_experiment_sha256"] == digest(PARENT / "experiment.py")
    assert frozen["formula_archive_sha256"] == digest(PARENT / "formula.xcnf.gz")
    assert frozen["formula_sha256"] == prepared["formula_sha256"]
    assert frozen["solver_sha256"] == base["solver_sha256"] == digest(
        frozen["solver_path"])
    assert frozen["cells"] == [{"name": name, "extra_flags": flags}
                               for name, flags in SETTINGS]
    for name, value in frozen["source_sha256"].items():
        assert value == digest(HERE / name)
    return frozen, base, prepared


def execute_cell(frozen, base, prepared, raw, name, extra_flags):
    input_path = HERE / f"{name}.xcnf"
    input_path.write_bytes(raw)
    out_path, err_path = HERE / f"{name}.stdout", HERE / f"{name}.stderr"
    flags = [*frozen["common_solver_flags"], *extra_flags]
    command = [frozen["solver_path"], *flags, str(input_path)]
    started = time.monotonic()
    timeout = False
    with out_path.open("wb") as stdout, err_path.open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        while True:
            pid, code, usage = os.wait4(process.pid, os.WNOHANG)
            if pid:
                break
            if time.monotonic() - started >= WALL_CAP:
                timeout = True
                process.kill()
                _, code, usage = os.wait4(process.pid, 0)
                break
            time.sleep(0.1)
    wall = time.monotonic() - started
    exit_code = os.waitstatus_to_exitcode(code)
    stdout, stderr = out_path.read_bytes(), err_path.read_bytes()
    out_gz, err_gz = HERE / f"{name}.stdout.gz", HERE / f"{name}.stderr.gz"
    out_gz.write_bytes(gzip.compress(stdout, mtime=0))
    err_gz.write_bytes(gzip.compress(stderr, mtime=0))
    input_path.unlink(); out_path.unlink(); err_path.unlink()
    solver_text = stdout.decode(errors="replace")
    status = {10: "SAT", 20: "UNSAT"}.get(exit_code, "BOUNDED_UNKNOWN")
    conflicts = re.findall(r"Conflicts in UIP\s*:\s*(\d+)", solver_text)
    check_started = time.monotonic()
    relation = None
    if status == "SAT":
        model = parent.parsed_model(solver_text)
        assert model is not None
        parent.check_serialized_xcnf(raw, model)
        relation = parent.verify_relation(base, prepared, model)
    verification = time.monotonic() - check_started
    return {"name": name, "extra_flags": extra_flags,
        "solver_status": status, "return_code": exit_code,
        "external_timeout": timeout,
        "conflicts_reported": int(conflicts[-1]) if conflicts else None,
        "solver_wall_seconds_exploratory": wall,
        "child_user_seconds": usage.ru_utime,
        "child_system_seconds": usage.ru_stime,
        "peak_child_rss_raw": usage.ru_maxrss,
        "peak_child_rss_unit": "bytes" if platform.system() == "Darwin"
                               else "kilobytes",
        "relation_check_seconds_exploratory": verification,
        "model_replay": relation,
        "stdout_gzip_sha256": digest(out_gz),
        "stderr_gzip_sha256": digest(err_gz)}


def run():
    frozen, base, prepared = check()
    assert not (HERE / "run.json").exists()
    raw = gzip.decompress((PARENT / "formula.xcnf.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == frozen["formula_sha256"]
    rows = []
    for name, flags in SETTINGS:
        row_path = HERE / f"{name}.json"
        if row_path.exists():
            row = load(row_path)
            assert row["name"] == name and row["extra_flags"] == flags
            assert digest(HERE / f"{name}.stdout.gz") == row[
                "stdout_gzip_sha256"]
            assert digest(HERE / f"{name}.stderr.gz") == row[
                "stderr_gzip_sha256"]
        else:
            row = execute_cell(frozen, base, prepared, raw, name, flags)
            save(row_path, row)
        rows.append(row)
        print(json.dumps({"cell": name, "status": row["solver_status"],
                          "relation_status": row["model_replay"]["status"]
                          if row["model_replay"] else None,
                          "child_cpu_seconds": row["child_user_seconds"] +
                          row["child_system_seconds"]}), flush=True)
    save(HERE / "run.json", {
        "schema": "q20261010184000-run-v1", "proposal_id": PROPOSAL,
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "curve_id": frozen["curve_id"], "workload_id": frozen["workload_id"],
        "public_target": frozen["public_target"],
        "actual_usable_points_B": frozen["actual_usable_points_B"],
        "folded_columns_K": frozen["folded_columns_K"],
        "factor_base_enumerated_set_sha256": frozen[
            "factor_base_enumerated_set_sha256"],
        "freeze_sha256": digest(HERE / "freeze.json"),
        "formula_sha256": frozen["formula_sha256"],
        "solver_sha256": frozen["solver_sha256"],
        "cells": rows})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check", "run"))
    action = parser.parse_args().action
    if action == "freeze":
        freeze()
    elif action == "check":
        check(); print("PASS: freeze")
    else:
        run()
