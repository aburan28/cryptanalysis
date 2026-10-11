#!/usr/bin/env python3
"""One-million-conflict replay of the frozen N83 sorted-leaf XCNF."""

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
import experiment as base  # noqa: E402

PROPOSAL = "Q20261010181200"
WALL_CAP = 600
CONFLICT_CAP = 1_000_000


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def freeze():
    parent = base.check()
    built = load(PARENT / "build.json")
    assert built["freeze_sha256"] == digest(PARENT / "freeze.json")
    flags = ["--verb", "1", "--threads", "1", "--random", "0",
             "--maxconfl", str(CONFLICT_CAP)]
    save(HERE / "freeze.json", {
        "schema": "q20261010181200-freeze-v1", "proposal_id": PROPOSAL,
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "curve_id": parent["curve_id"], "workload_id": parent["workload_id"],
        "public_target": parent["public_target"],
        "actual_usable_points_B": parent["actual_usable_points_B"],
        "folded_columns_K": parent["folded_columns_K"],
        "parent_freeze_sha256": digest(PARENT / "freeze.json"),
        "parent_build_sha256": digest(PARENT / "build.json"),
        "parent_experiment_sha256": digest(PARENT / "experiment.py"),
        "formula_archive_sha256": digest(PARENT / "formula.xcnf.gz"),
        "formula_sha256": built["formula_sha256"],
        "solver_path": parent["solver_path"],
        "solver_sha256": parent["solver_sha256"],
        "solver_flags": flags,
        "external_wall_cap_seconds": WALL_CAP,
        "source_sha256": {name: digest(HERE / name) for name in
                          ("PROTOCOL.md", "runner.py", "audit.py")}})
    print(json.dumps({"freeze_sha256": digest(HERE / "freeze.json")}))


def check():
    frozen = load(HERE / "freeze.json")
    parent = base.check()
    built = load(PARENT / "build.json")
    assert frozen["parent_freeze_sha256"] == digest(PARENT / "freeze.json")
    assert frozen["parent_build_sha256"] == digest(PARENT / "build.json")
    assert frozen["parent_experiment_sha256"] == digest(PARENT / "experiment.py")
    assert frozen["formula_archive_sha256"] == digest(PARENT / "formula.xcnf.gz")
    assert frozen["formula_sha256"] == built["formula_sha256"]
    assert frozen["solver_sha256"] == parent["solver_sha256"] == digest(
        frozen["solver_path"])
    assert frozen["external_wall_cap_seconds"] == WALL_CAP
    for name, value in frozen["source_sha256"].items():
        assert value == digest(HERE / name)
    return frozen, parent, built


def run():
    frozen, parent, built = check()
    assert not (HERE / "run.json").exists()
    raw = gzip.decompress((PARENT / "formula.xcnf.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == frozen["formula_sha256"]
    input_path = HERE / "solver.xcnf"
    input_path.write_bytes(raw)
    out_path, err_path = HERE / "solver.stdout", HERE / "solver.stderr"
    command = [frozen["solver_path"], *frozen["solver_flags"], str(input_path)]
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
    out_gz, err_gz = HERE / "solver.stdout.gz", HERE / "solver.stderr.gz"
    out_gz.write_bytes(gzip.compress(stdout, mtime=0))
    err_gz.write_bytes(gzip.compress(stderr, mtime=0))
    input_path.unlink(); out_path.unlink(); err_path.unlink()
    solver_text = stdout.decode(errors="replace")
    status = {10: "SAT", 20: "UNSAT"}.get(exit_code, "BOUNDED_UNKNOWN")
    conflicts = re.findall(r"Conflicts in UIP\s*:\s*(\d+)", solver_text)
    verification_started = time.monotonic()
    replay = base.replay_model(parent, built, raw, solver_text) if status == "SAT" else None
    verification = time.monotonic() - verification_started
    save(HERE / "run.json", {
        "schema": "q20261010181200-run-v1", "proposal_id": PROPOSAL,
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
        "model_replay": replay,
        "stdout_gzip_sha256": digest(out_gz),
        "stderr_gzip_sha256": digest(err_gz)})
    print(json.dumps({"status": status, "model_replay": replay,
                      "wall_seconds": wall,
                      "child_cpu_seconds": usage.ru_utime + usage.ru_stime}))


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
