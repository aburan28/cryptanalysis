#!/usr/bin/env python3
"""Longer cap on the identical archived ordinary N53 t-S3 formula."""

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
import experiment as original  # noqa: E402

PROPOSAL = "Q20261010175400"
WALL_CAP = 1200


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, row):
    assert not path.exists(), path
    path.write_text(json.dumps(row, sort_keys=True, indent=2) + "\n")


def freeze():
    parent = original.check_freeze()
    prepared = load(PARENT / "prepare.json")
    assert prepared["freeze_sha256"] == digest(PARENT / "freeze.json")
    save(HERE / "freeze.json", {
        "schema": "q20261010175400-freeze-v1", "proposal_id": PROPOSAL,
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "curve_id": parent["curve_id"],
        "workload_id": parent["ordinary_workload_id"],
        "public_target": parent["public_target"],
        "actual_usable_points_B": parent["actual_usable_points_B"],
        "folded_columns_K": parent["folded_columns_K"],
        "parent_freeze_sha256": digest(PARENT / "freeze.json"),
        "parent_prepare_sha256": digest(PARENT / "prepare.json"),
        "parent_experiment_sha256": digest(PARENT / "experiment.py"),
        "formula_archive_sha256": digest(PARENT / "inputs/system.xcnf.gz"),
        "formula_sha256": prepared["formula_sha256"],
        "solver_path": parent["solver_path"],
        "solver_sha256": parent["solver_sha256"],
        "solver_flags": parent["solver_flags"],
        "external_wall_cap_seconds": WALL_CAP,
        "source_sha256": {name: digest(HERE / name) for name in
                          ("PROTOCOL.md", "runner.py", "audit.py")}})
    print(json.dumps({"freeze_sha256": digest(HERE / "freeze.json")}))


def check():
    frozen = load(HERE / "freeze.json")
    parent = original.check_freeze()
    prepared = load(PARENT / "prepare.json")
    assert frozen["parent_freeze_sha256"] == digest(PARENT / "freeze.json")
    assert frozen["parent_prepare_sha256"] == digest(PARENT / "prepare.json")
    assert frozen["parent_experiment_sha256"] == digest(PARENT / "experiment.py")
    assert frozen["formula_archive_sha256"] == digest(
        PARENT / "inputs/system.xcnf.gz")
    assert frozen["formula_sha256"] == prepared["formula_sha256"]
    assert frozen["solver_sha256"] == parent["solver_sha256"] == digest(
        frozen["solver_path"])
    assert frozen["solver_flags"] == parent["solver_flags"]
    assert frozen["external_wall_cap_seconds"] == WALL_CAP
    for name, value in frozen["source_sha256"].items():
        assert value == digest(HERE / name)
    return frozen, parent, prepared


def run():
    frozen, parent, prepared = check()
    assert not (HERE / "run.json").exists()
    raw = gzip.decompress((PARENT / "inputs/system.xcnf.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == frozen["formula_sha256"]
    input_path = HERE / "solver.xcnf"
    input_path.write_bytes(raw)
    output_path, error_path = HERE / "solver.stdout", HERE / "solver.stderr"
    command = [frozen["solver_path"], *frozen["solver_flags"], str(input_path)]
    started = time.monotonic()
    timeout = False
    with output_path.open("wb") as stdout, error_path.open("wb") as stderr:
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
    stdout, stderr = output_path.read_bytes(), error_path.read_bytes()
    out_gz, err_gz = HERE / "solver.stdout.gz", HERE / "solver.stderr.gz"
    out_gz.write_bytes(gzip.compress(stdout, mtime=0))
    err_gz.write_bytes(gzip.compress(stderr, mtime=0))
    input_path.unlink(); output_path.unlink(); error_path.unlink()
    solver_text = stdout.decode(errors="replace")
    status = {10: "SAT", 20: "UNSAT"}.get(exit_code, "BOUNDED_UNKNOWN")
    conflicts = re.findall(r"Conflicts in UIP\s*:\s*(\d+)", solver_text)
    relation = None
    verification_started = time.monotonic()
    if status == "SAT":
        model = original.parsed_model(solver_text)
        assert model is not None
        original.check_serialized_xcnf(raw, model)
        relation = original.verify_relation(parent, prepared, model)
    verification = time.monotonic() - verification_started
    save(HERE / "run.json", {
        "schema": "q20261010175400-run-v1", "proposal_id": PROPOSAL,
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "curve_id": frozen["curve_id"], "workload_id": frozen["workload_id"],
        "public_target": frozen["public_target"],
        "actual_usable_points_B": frozen["actual_usable_points_B"],
        "folded_columns_K": frozen["folded_columns_K"],
        "freeze_sha256": digest(HERE / "freeze.json"),
        "formula_sha256": frozen["formula_sha256"],
        "solver_sha256": frozen["solver_sha256"],
        "solver_flags": frozen["solver_flags"], "solver_status": status,
        "return_code": exit_code, "external_timeout": timeout,
        "conflicts_reported": int(conflicts[-1]) if conflicts else None,
        "solver_wall_seconds_exploratory": wall,
        "child_user_seconds": usage.ru_utime,
        "child_system_seconds": usage.ru_stime,
        "peak_child_rss_raw": usage.ru_maxrss,
        "peak_child_rss_unit": "bytes" if platform.system() == "Darwin"
                               else "kilobytes",
        "relation_check_seconds_exploratory": verification,
        "relation": relation,
        "stdout_gzip_sha256": digest(out_gz),
        "stderr_gzip_sha256": digest(err_gz)})
    print(json.dumps({"status": status,
                      "relation_status": relation["status"] if relation else None,
                      "wall_seconds": wall,
                      "child_cpu_seconds": usage.ru_utime + usage.ru_stime}))


if __name__ == "__main__":
    action = argparse.ArgumentParser()
    action.add_argument("action", choices=("freeze", "check", "run"))
    command = action.parse_args().action
    if command == "freeze":
        freeze()
    elif command == "check":
        check(); print("PASS: freeze")
    else:
        run()
