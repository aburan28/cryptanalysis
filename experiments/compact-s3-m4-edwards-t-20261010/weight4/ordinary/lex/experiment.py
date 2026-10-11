#!/usr/bin/env python3
"""Exact sorted-leaf symmetry reduction of the frozen ordinary t-S3 XCNF."""

import argparse
import gzip
import hashlib
import itertools
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
from chain_s3 import Formula  # noqa: E402

PROPOSAL = "Q20261010175900"
WALL_CAP = 300
MAX_CONFLICTS = 100_000


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, row):
    assert not path.exists(), path
    path.write_text(json.dumps(row, sort_keys=True, indent=2) + "\n")


def add_lex(formula, left, right):
    """Enforce big-endian left <= right using exact prefix equality bits."""
    assert len(left) == len(right)
    equal_prefix = 1
    for index, (a, b) in enumerate(zip(reversed(left), reversed(right))):
        formula.clauses.append([-equal_prefix, -a, b])
        if index + 1 < len(left):
            different = formula.new()
            formula.xor_relation([a, b, different])
            equal_prefix = formula.and_gate(equal_prefix, -different)


def selfcheck():
    """Exhaustively test 3-bit comparators with a separate SAT assignment."""
    solver = original.load(PARENT / "freeze.json")["solver_path"]
    for a, b in itertools.product(range(8), repeat=2):
        f = Formula()
        left, right = [[f.new() for _ in range(3)] for _ in range(2)]
        add_lex(f, left, right)
        for vector, value in ((left, a), (right, b)):
            for i, lit in enumerate(vector):
                f.clauses.append([lit if value >> i & 1 else -lit])
        path = HERE / "selfcheck.xcnf"
        f.write(path)
        result = subprocess.run([solver, "--verb", "0", "--threads", "1",
                                 str(path)], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, check=False)
        path.unlink()
        assert (result.returncode == 10) == (a <= b), (a, b, result.returncode)
        assert result.returncode in (10, 20)
    print("PASS: 64 comparator truth-table cells")


def freeze():
    parent = original.check_freeze()
    prepared = load(PARENT / "prepare.json")
    assert prepared["freeze_sha256"] == digest(PARENT / "freeze.json")
    selfcheck()
    flags = ["--verb", "1", "--threads", "1", "--random", "0",
             "--maxconfl", str(MAX_CONFLICTS)]
    save(HERE / "freeze.json", {
        "schema": "q20261010175900-freeze-v1", "proposal_id": PROPOSAL,
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "curve_id": parent["curve_id"],
        "workload_id": parent["ordinary_workload_id"],
        "public_target": parent["public_target"],
        "actual_usable_points_B": parent["actual_usable_points_B"],
        "folded_columns_K": parent["folded_columns_K"],
        "factor_base_enumerated_set_sha256": parent[
            "factor_base_enumerated_set_sha256"],
        "parent_freeze_sha256": digest(PARENT / "freeze.json"),
        "parent_prepare_sha256": digest(PARENT / "prepare.json"),
        "parent_experiment_sha256": digest(PARENT / "experiment.py"),
        "parent_formula_archive_sha256": digest(
            PARENT / "inputs/system.xcnf.gz"),
        "parent_formula_sha256": prepared["formula_sha256"],
        "solver_path": parent["solver_path"],
        "solver_sha256": parent["solver_sha256"],
        "solver_flags": flags,
        "external_wall_cap_seconds": WALL_CAP,
        "source_sha256": {name: digest(HERE / name) for name in
                          ("PROTOCOL.md", "experiment.py", "audit.py")}})
    print(json.dumps({"freeze_sha256": digest(HERE / "freeze.json")}))


def check():
    frozen = load(HERE / "freeze.json")
    parent = original.check_freeze()
    prepared = load(PARENT / "prepare.json")
    assert frozen["parent_freeze_sha256"] == digest(PARENT / "freeze.json")
    assert frozen["parent_prepare_sha256"] == digest(PARENT / "prepare.json")
    assert frozen["parent_experiment_sha256"] == digest(PARENT / "experiment.py")
    assert frozen["parent_formula_archive_sha256"] == digest(
        PARENT / "inputs/system.xcnf.gz")
    assert frozen["parent_formula_sha256"] == prepared["formula_sha256"]
    assert frozen["solver_sha256"] == parent["solver_sha256"] == digest(
        frozen["solver_path"])
    for name, value in frozen["source_sha256"].items():
        assert value == digest(HERE / name)
    return frozen, parent, prepared


def build():
    frozen, _, prepared = check()
    assert not (HERE / "formula.xcnf.gz").exists()
    raw = gzip.decompress((PARENT / "inputs/system.xcnf.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == frozen["parent_formula_sha256"]
    lines = raw.decode("ascii").splitlines()
    header = lines[0].split()
    assert header[:2] == ["p", "cnf"]
    assert int(header[2]) == prepared["variables"]
    assert int(header[3]) == prepared["cnf_clauses"] + prepared["xor_rows"]
    delta = Formula()
    delta.variables = prepared["variables"]
    delta.clauses = []
    for left, right in zip(prepared["leaves"], prepared["leaves"][1:]):
        add_lex(delta, left, right)
    path = HERE / "formula.xcnf"
    delta_path = HERE / "delta.xcnf"
    delta.write(delta_path)
    delta_lines = delta_path.read_text().splitlines()[1:]
    delta_path.unlink()
    output = "\n".join([f"p cnf {delta.variables} {int(header[3])+len(delta_lines)}",
                        *lines[1:], *delta_lines, ""]).encode("ascii")
    path.write_bytes(output)
    archive = HERE / "formula.xcnf.gz"
    archive.write_bytes(gzip.compress(output, mtime=0))
    path.unlink()
    save(HERE / "build.json", {
        "schema": "q20261010175900-build-v1", "proposal_id": PROPOSAL,
        "freeze_sha256": digest(HERE / "freeze.json"),
        "parent_formula_sha256": frozen["parent_formula_sha256"],
        "formula_sha256": hashlib.sha256(output).hexdigest(),
        "formula_archive_sha256": digest(archive),
        "variables": delta.variables,
        "cnf_clauses": prepared["cnf_clauses"] + len(delta.clauses),
        "xor_rows": prepared["xor_rows"] + len(delta.xors),
        "added_variables": delta.variables - prepared["variables"],
        "added_cnf_clauses": len(delta.clauses),
        "added_xor_rows": len(delta.xors),
        "added_and_gates": len(delta.and_cache)})
    print(json.dumps({"status": "BUILT", "formula_sha256":
                      hashlib.sha256(output).hexdigest()}))


def solve():
    frozen, parent, prepared = check()
    built = load(HERE / "build.json")
    assert built["freeze_sha256"] == digest(HERE / "freeze.json")
    assert not (HERE / "run.json").exists()
    archive = HERE / "formula.xcnf.gz"
    assert digest(archive) == built["formula_archive_sha256"]
    raw = gzip.decompress(archive.read_bytes())
    assert hashlib.sha256(raw).hexdigest() == built["formula_sha256"]
    input_path = HERE / "solver.xcnf"
    input_path.write_bytes(raw)
    stdout_path, stderr_path = HERE / "solver.stdout", HERE / "solver.stderr"
    command = [frozen["solver_path"], *frozen["solver_flags"], str(input_path)]
    started = time.monotonic()
    timeout = False
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
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
    stdout, stderr = stdout_path.read_bytes(), stderr_path.read_bytes()
    out_gz, err_gz = HERE / "solver.stdout.gz", HERE / "solver.stderr.gz"
    out_gz.write_bytes(gzip.compress(stdout, mtime=0))
    err_gz.write_bytes(gzip.compress(stderr, mtime=0))
    input_path.unlink(); stdout_path.unlink(); stderr_path.unlink()
    solver_text = stdout.decode(errors="replace")
    status = {10: "SAT", 20: "UNSAT"}.get(exit_code, "BOUNDED_UNKNOWN")
    conflicts = re.findall(r"Conflicts in UIP\s*:\s*(\d+)", solver_text)
    relation = None
    verification_started = time.monotonic()
    if status == "SAT":
        model = original.parsed_model(solver_text)
        assert model is not None
        original.check_serialized_xcnf(raw, model)
        values = [sum(1 << index for index, bit in enumerate(vector)
                      if model[bit]) for vector in prepared["leaves"]]
        assert values == sorted(values)
        relation = original.verify_relation(parent, prepared, model)
    verification = time.monotonic() - verification_started
    save(HERE / "run.json", {
        "schema": "q20261010175900-run-v1", "proposal_id": PROPOSAL,
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "curve_id": frozen["curve_id"], "workload_id": frozen["workload_id"],
        "public_target": frozen["public_target"],
        "actual_usable_points_B": frozen["actual_usable_points_B"],
        "folded_columns_K": frozen["folded_columns_K"],
        "freeze_sha256": digest(HERE / "freeze.json"),
        "build_sha256": digest(HERE / "build.json"),
        "formula_sha256": built["formula_sha256"],
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
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check", "build", "solve"))
    action = parser.parse_args().action
    if action == "freeze":
        freeze()
    elif action == "check":
        check(); print("PASS: freeze")
    elif action == "build":
        build()
    else:
        solve()
