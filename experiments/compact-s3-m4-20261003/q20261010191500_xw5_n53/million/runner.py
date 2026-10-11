#!/usr/bin/env python3
"""Frozen million-conflict continuation on the N53 weight-five XCNF."""

import argparse
import gzip
import hashlib
import json
import os
import platform
import re
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
PROPOSAL = "Q20261010191700"
WALL_CAP = 1200
CONFLICT_CAP = 1_000_000


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, row):
    assert not path.exists(), path
    path.write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")


def freeze():
    parent = load(PARENT / "freeze.json")
    prepared = load(PARENT / "prepare.json")
    short_run = load(PARENT / "run.json")
    assert parent["proposal_id"] == short_run["proposal_id"] == (
        "Q20261010191500")
    assert short_run["status"] == "BOUNDED_UNKNOWN"
    assert parent["workload_id"] == "74f2979b3e68"
    assert sha(PARENT / "formula.xcnf.gz") == prepared[
        "formula_archive_sha256"]
    save(HERE / "freeze.json", {
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "curve_id": parent["curve_id"], "workload_id": parent["workload_id"],
        "isogeny": "none", "public_target": parent["public_target"],
        "solver_path": parent["solver_path"],
        "solver_sha256": parent["solver_sha256"],
        "solver_flags": ["--verb", "1", "--threads", "1", "--random", "0",
                         "--maxconfl", str(CONFLICT_CAP)],
        "external_wall_cap_seconds": WALL_CAP,
        "formula_sha256": prepared["formula_sha256"],
        "formula_archive_sha256": prepared["formula_archive_sha256"],
        "parent_sha256": {name: sha(PARENT / name) for name in
                          ("freeze.json", "prepare.json", "run.json",
                           "formula.xcnf.gz")},
        "source_sha256": {name: sha(HERE / name) for name in
                          ("PROTOCOL.md", "runner.py", "audit.py")}})


def check():
    frozen = load(HERE / "freeze.json")
    for name, value in frozen["source_sha256"].items():
        assert sha(HERE / name) == value
    for name, value in frozen["parent_sha256"].items():
        assert sha(PARENT / name) == value
    assert sha(frozen["solver_path"]) == frozen["solver_sha256"]
    return frozen


def run():
    frozen = check()
    assert not (HERE / "run.json").exists()
    archive = PARENT / "formula.xcnf.gz"
    raw = gzip.decompress(archive.read_bytes())
    assert hashlib.sha256(raw).hexdigest() == frozen["formula_sha256"]
    input_path = HERE / "solver.xcnf"
    input_path.write_bytes(raw)
    stdout_path = HERE / "solver.stdout"
    stderr_path = HERE / "solver.stderr"
    command = [frozen["solver_path"], *frozen["solver_flags"], str(input_path)]
    started = time.monotonic()
    timed_out = False
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        while True:
            pid, code, usage = os.wait4(process.pid, os.WNOHANG)
            if pid:
                break
            if time.monotonic()-started >= WALL_CAP:
                timed_out = True
                process.kill()
                _, code, usage = os.wait4(process.pid, 0)
                break
            time.sleep(0.1)
    wall = time.monotonic()-started
    exit_code = os.waitstatus_to_exitcode(code)
    stdout = stdout_path.read_bytes()
    stderr = stderr_path.read_bytes()
    (HERE / "solver.stdout.gz").write_bytes(gzip.compress(stdout, mtime=0))
    (HERE / "solver.stderr.gz").write_bytes(gzip.compress(stderr, mtime=0))
    input_path.unlink(); stdout_path.unlink(); stderr_path.unlink()
    output = stdout.decode(errors="replace")
    status = {10: "SAT", 20: "UNSAT"}.get(exit_code, "BOUNDED_UNKNOWN")
    conflicts = re.findall(r"Conflicts in UIP\s*:\s*(\d+)", output)
    save(HERE / "run.json", {
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "curve_id": frozen["curve_id"], "workload_id": frozen["workload_id"],
        "isogeny": "none", "status": status, "exit_code": exit_code,
        "timed_out": timed_out,
        "last_reported_conflicts": int(conflicts[-1]) if conflicts else None,
        "wall_seconds_exploratory": wall,
        "child_cpu_seconds": usage.ru_utime+usage.ru_stime,
        "peak_child_rss_raw": usage.ru_maxrss,
        "peak_child_rss_unit": "bytes" if platform.system() == "Darwin"
                               else "kilobytes",
        "freeze_sha256": sha(HERE / "freeze.json"),
        "stdout_archive_sha256": sha(HERE / "solver.stdout.gz"),
        "stderr_archive_sha256": sha(HERE / "solver.stderr.gz"),
        "verified_relation": None})
    print(json.dumps({"status": status, "conflicts":
                      int(conflicts[-1]) if conflicts else None,
                      "cpu": usage.ru_utime+usage.ru_stime, "wall": wall}))


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
