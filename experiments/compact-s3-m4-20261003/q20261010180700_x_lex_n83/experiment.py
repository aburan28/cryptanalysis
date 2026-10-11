#!/usr/bin/env python3
"""Sorted-leaf symmetry screen on Q1408's archived N83 ordinary formula."""

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
sys.path[:0] = [str(PARENT / "q1419_partial_pin"), str(PARENT)]
from chain_s3 import Formula  # noqa: E402
from chain_s3_balanced_multitarget import build_balanced  # noqa: E402
from q1325_inputs import read_inputs  # noqa: E402
from run_q1404_raw_preimage_w5 import verify_model  # noqa: E402
from run_probe import curves, field  # noqa: E402
from verify_archive import check_serialized_xcnf, parsed_model  # noqa: E402

PROPOSAL = "Q20261010180700"
WALL_CAP = 300
CONFLICT_CAP = 100_000
ARCHIVE = PARENT / "runs/n83_q1408_ordinary.xcnf.gz"
PARENT_RUN = PARENT / "runs/n83_q1408_ordinary.json"
PARENT_PROTOCOL = PARENT / "q1408_balanced_s3_w5_protocol.json"
COSET = PARENT / "runs/n83_ordinary_raw_preimages.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, row):
    assert not path.exists(), path
    path.write_text(json.dumps(row, sort_keys=True, indent=2) + "\n")


def add_lex(formula, left, right):
    assert len(left) == len(right)
    equal_prefix = 1
    for index, (a, b) in enumerate(zip(reversed(left), reversed(right))):
        formula.clauses.append([-equal_prefix, -a, b])
        if index + 1 < len(left):
            different = formula.new()
            formula.xor_relation([a, b, different])
            equal_prefix = formula.and_gate(equal_prefix, -different)


def selfcheck(solver):
    for a, b in itertools.product(range(8), repeat=2):
        f = Formula()
        left, right = [[f.new() for _ in range(3)] for _ in range(2)]
        add_lex(f, left, right)
        for vector, value in ((left, a), (right, b)):
            for i, lit in enumerate(vector):
                f.clauses.append([lit if value >> i & 1 else -lit])
        path = HERE / "selfcheck.xcnf"
        f.write(path)
        run = subprocess.run([solver, "--verb", "0", "--threads", "1",
                              str(path)], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, check=False)
        path.unlink()
        assert run.returncode in (10, 20)
        assert (run.returncode == 10) == (a <= b), (a, b)


def freeze():
    parent, protocol, coset = load(PARENT_RUN), load(PARENT_PROTOCOL), load(COSET)
    base_path, base, key_path, _, baseline_path, baseline = read_inputs()
    assert parent["proposal_id"] == protocol["proposal_id"] == "Q1408"
    assert parent["candidate_id"] is None and parent["isogeny"] == "none"
    assert parent["curve_id"] == protocol["curve_id"] == baseline["curve_id"]
    assert parent["workload_id"] == baseline["workload_id"] == "bab50a1e5f66"
    assert parent["factor_base_actual_B"] == 30977592
    assert parent["factor_base_folded_columns"] == 186612
    raw = gzip.decompress(ARCHIVE.read_bytes())
    assert hashlib.sha256(raw).hexdigest() == parent["attempts"][0][
        "xcnf_sha256"]
    assert coset["raw_target_x_coordinates"] == parent[
        "raw_preimage_x_coordinates"]
    solver = parent["attempts"][0]["solver_command"][0]
    assert Path(solver).is_file()
    assert digest(solver) == parent["solver_binary_sha256"]
    selfcheck(solver)
    save(HERE / "freeze.json", {
        "schema": "q20261010180700-freeze-v1", "proposal_id": PROPOSAL,
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "curve_id": parent["curve_id"], "workload_id": parent["workload_id"],
        "public_target": parent["public_target"],
        "actual_usable_points_B": parent["factor_base_actual_B"],
        "folded_columns_K": parent["factor_base_folded_columns"],
        "factor_base_enumerated_set_sha256": parent[
            "factor_base_enumerated_set_sha256"],
        "base_receipt_sha256": digest(base_path),
        "base_key_file_sha256": digest(key_path),
        "ordinary_baseline_sha256": digest(baseline_path),
        "parent_run_sha256": digest(PARENT_RUN),
        "parent_protocol_sha256": digest(PARENT_PROTOCOL),
        "coset_sha256": digest(COSET),
        "parent_formula_archive_sha256": digest(ARCHIVE),
        "parent_formula_sha256": hashlib.sha256(raw).hexdigest(),
        "solver_path": solver, "solver_sha256": digest(solver),
        "solver_flags": ["--verb", "1", "--threads", "1",
                         "--random", "0", "--maxconfl", str(CONFLICT_CAP)],
        "external_wall_cap_seconds": WALL_CAP,
        "source_sha256": {name: digest(HERE / name) for name in
                          ("PROTOCOL.md", "experiment.py", "audit.py")}})
    print(json.dumps({"freeze_sha256": digest(HERE / "freeze.json")}))


def check():
    frozen = load(HERE / "freeze.json")
    for path, key in ((PARENT_RUN, "parent_run_sha256"),
                      (PARENT_PROTOCOL, "parent_protocol_sha256"),
                      (COSET, "coset_sha256"),
                      (ARCHIVE, "parent_formula_archive_sha256")):
        assert digest(path) == frozen[key]
    base_path, _, key_path, _, baseline_path, _ = read_inputs()
    assert digest(base_path) == frozen["base_receipt_sha256"]
    assert digest(key_path) == frozen["base_key_file_sha256"]
    assert digest(baseline_path) == frozen["ordinary_baseline_sha256"]
    assert digest(frozen["solver_path"]) == frozen["solver_sha256"]
    for name, value in frozen["source_sha256"].items():
        assert digest(HERE / name) == value
    return frozen


def build():
    frozen = check()
    assert not (HERE / "formula.xcnf.gz").exists()
    parent = load(PARENT_RUN)
    raw = gzip.decompress(ARCHIVE.read_bytes())
    assert hashlib.sha256(raw).hexdigest() == frozen["parent_formula_sha256"]
    lines = raw.decode("ascii").splitlines()
    header = lines[0].split()
    assert header[:2] == ["p", "cnf"]
    assert int(header[2]) == parent["formula"]["variables"]
    assert int(header[3]) == (parent["formula"]["cnf_clauses"] +
                              parent["formula"]["xor_rows"])
    leaves = [[2 + 83*i + j for j in range(83)] for i in range(4)]
    delta = Formula()
    delta.variables = int(header[2])
    delta.clauses = []
    for left, right in zip(leaves, leaves[1:]):
        add_lex(delta, left, right)
    path = HERE / "delta.xcnf"
    delta.write(path)
    delta_lines = path.read_text().splitlines()[1:]
    path.unlink()
    output = "\n".join([f"p cnf {delta.variables} {int(header[3])+len(delta_lines)}",
                        *lines[1:], *delta_lines, ""]).encode("ascii")
    archive = HERE / "formula.xcnf.gz"
    archive.write_bytes(gzip.compress(output, mtime=0))
    save(HERE / "build.json", {
        "schema": "q20261010180700-build-v1", "proposal_id": PROPOSAL,
        "freeze_sha256": digest(HERE / "freeze.json"),
        "parent_formula_sha256": frozen["parent_formula_sha256"],
        "formula_sha256": hashlib.sha256(output).hexdigest(),
        "formula_archive_sha256": digest(archive),
        "variables": delta.variables,
        "cnf_clauses": parent["formula"]["cnf_clauses"] + len(delta.clauses),
        "xor_rows": parent["formula"]["xor_rows"] + len(delta.xors),
        "added_variables": delta.variables - int(header[2]),
        "added_cnf_clauses": len(delta.clauses),
        "added_xor_rows": len(delta.xors),
        "added_and_gates": len(delta.and_cache), "leaves": leaves})
    print(json.dumps({"status": "BUILT", "formula_sha256":
                      hashlib.sha256(output).hexdigest()}))


def replay_model(frozen, built, raw, solver_text):
    model = parsed_model(solver_text)
    assert model is not None
    check_serialized_xcnf(raw, model)
    leaves = built["leaves"]
    values = [sum(1 << i for i, lit in enumerate(vector) if model[lit])
              for vector in leaves]
    assert values == sorted(values)
    parent = load(PARENT_RUN)
    raw_xs = parent["raw_preimage_x_coordinates"]
    formula, actual_leaves, _, _, selector = build_balanced(83, 5, raw_xs)
    assert actual_leaves == leaves
    path = HERE / "replay_parent.xcnf"
    formula.write(path)
    assert digest(path) == frozen["parent_formula_sha256"]
    path.unlink()
    _, base, _, keys, _, _ = read_inputs()
    coset = load(COSET)
    raw_points = [tuple(map(int, row)) for row in coset["raw_target_points"]]
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    verified = verify_model(onb, curve, int(base["curve"]["subgroup_order"]),
                            set(keys), tuple(map(int, frozen["public_target"])),
                            raw_points, raw_xs, leaves, selector, model)
    return {"selected_target_index": verified[0],
            "leaf_x_coords": verified[2], "lift_status": verified[3],
            "relation": verified[4], "four_distinct_columns": verified[5]}


def solve():
    frozen = check()
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
    verification_started = time.monotonic()
    relation = replay_model(frozen, built, raw, solver_text) if status == "SAT" else None
    verification = time.monotonic() - verification_started
    save(HERE / "run.json", {
        "schema": "q20261010180700-run-v1", "proposal_id": PROPOSAL,
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
        "model_replay": relation,
        "stdout_gzip_sha256": digest(out_gz),
        "stderr_gzip_sha256": digest(err_gz)})
    print(json.dumps({"status": status, "model_replay": relation,
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
