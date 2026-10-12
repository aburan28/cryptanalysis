#!/usr/bin/env python3
"""Pin Q1410's witness in the exact N53 x-weight-four ordinary formula."""

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
PARENT = HERE.parent / "ordinary"
ROOT = HERE.parents[3]
Q1410 = ROOT / "experiments/compact-s3-m4-20261003"
sys.path[:0] = [str(PARENT), str(Q1410 / "q1419_partial_pin"),
                str(Q1410), str(ROOT / "ecc2k130/codegen")]
import experiment as ordinary  # noqa: E402
from chain_s3_balanced_multitarget import build_balanced  # noqa: E402
from verify_archive import check_serialized_xcnf, parsed_model  # noqa: E402
import field  # noqa: E402

PROPOSAL = "Q20261010184800"
WALL_CAP = 60
CONFLICT_CAP = 100_000
WITNESS = Q1410 / "runs/n53_q1410_witness_locked.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def freeze():
    original = ordinary.check()
    prepared = load(PARENT / "prepare.json")
    witness = load(WITNESS)
    assert witness["verified_relation"] is not None
    assert witness["curve_id"] == original["curve_id"]
    assert witness["public_target"] == original["public_target"]
    assert prepared["freeze_sha256"] == digest(PARENT / "freeze.json")
    save(HERE / "freeze.json", {
        "schema": "q20261010184800-freeze-v1", "proposal_id": PROPOSAL,
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "curve_id": original["curve_id"],
        "workload_id": original["workload_id"],
        "public_target": original["public_target"],
        "actual_usable_points_B": original["actual_usable_points_B"],
        "folded_columns_K": original["folded_columns_K"],
        "factor_base_enumerated_set_sha256": original[
            "factor_base_enumerated_set_sha256"],
        "parent_freeze_sha256": digest(PARENT / "freeze.json"),
        "parent_prepare_sha256": digest(PARENT / "prepare.json"),
        "parent_experiment_sha256": digest(PARENT / "experiment.py"),
        "ordinary_formula_archive_sha256": digest(PARENT / "formula.xcnf.gz"),
        "ordinary_formula_sha256": prepared["formula_sha256"],
        "witness_receipt_sha256": digest(WITNESS),
        "solver_path": original["solver_path"],
        "solver_sha256": original["solver_sha256"],
        "solver_flags": ["--verb", "1", "--threads", "1",
                         "--random", "0", "--maxconfl", str(CONFLICT_CAP)],
        "external_wall_cap_seconds": WALL_CAP,
        "source_sha256": {name: digest(HERE / name) for name in
                          ("PROTOCOL.md", "control.py", "audit.py")}})
    print(json.dumps({"freeze_sha256": digest(HERE / "freeze.json")}))


def check():
    frozen = load(HERE / "freeze.json")
    assert frozen["parent_freeze_sha256"] == digest(PARENT / "freeze.json")
    assert frozen["parent_prepare_sha256"] == digest(PARENT / "prepare.json")
    assert frozen["parent_experiment_sha256"] == digest(PARENT / "experiment.py")
    assert frozen["ordinary_formula_archive_sha256"] == digest(
        PARENT / "formula.xcnf.gz")
    assert frozen["witness_receipt_sha256"] == digest(WITNESS)
    assert frozen["solver_sha256"] == digest(frozen["solver_path"])
    for name, value in frozen["source_sha256"].items():
        assert value == digest(HERE / name)
    return frozen


def prepare():
    frozen = check()
    assert not (HERE / "formula.xcnf.gz").exists()
    prepared = load(PARENT / "prepare.json")
    raw = gzip.decompress((PARENT / "formula.xcnf.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == frozen["ordinary_formula_sha256"]
    coset = load(Q1410 / "runs/n53_ordinary_raw_preimages.json")
    formula, leaves, mids, _, selector = build_balanced(
        53, 4, coset["raw_target_x_coordinates"])
    assert leaves == prepared["leaves"] and selector == prepared["selector"]
    path = HERE / "rebuild.xcnf"
    formula.write(path)
    assert digest(path) == frozen["ordinary_formula_sha256"]
    path.unlink()
    witness = load(WITNESS)["fixture"]
    onb = field.Onb(53)
    raw_sum = tuple(witness["raw_sum"])
    raw_points = [tuple(map(int, point)) for point in
                  coset["raw_target_points"]]
    choice = raw_points.index(raw_sum)
    pins = []
    for vector, value in zip(leaves, witness["raw_leaf_x"]):
        pins.extend([lit if value >> i & 1 else -lit
                     for i, lit in enumerate(vector)])
    for vector, point in zip(mids, witness["raw_pair_sum_points"]):
        value = onb.toCoords(point[0])
        pins.extend([lit if value >> i & 1 else -lit
                     for i, lit in enumerate(vector)])
    pins.extend([lit if choice >> i & 1 else -lit
                 for i, lit in enumerate(selector)])
    lines = raw.decode("ascii").splitlines()
    header = lines[0].split()
    assert header[:2] == ["p", "cnf"]
    output = "\n".join([f"p cnf {header[2]} {int(header[3])+len(pins)}",
                        *lines[1:], *(f"{lit} 0" for lit in pins), ""]).encode(
                            "ascii")
    archive = HERE / "formula.xcnf.gz"
    archive.write_bytes(gzip.compress(output, mtime=0))
    save(HERE / "prepare.json", {
        "schema": "q20261010184800-prepare-v1", "proposal_id": PROPOSAL,
        "freeze_sha256": digest(HERE / "freeze.json"),
        "ordinary_formula_sha256": frozen["ordinary_formula_sha256"],
        "formula_sha256": hashlib.sha256(output).hexdigest(),
        "formula_archive_sha256": digest(archive),
        "added_unit_clauses": len(pins), "pin_literals": pins,
        "selected_target_index": choice,
        "witness_leaf_x_coords": witness["raw_leaf_x"],
        "witness_raw_sum": witness["raw_sum"]})
    print(json.dumps({"status": "PREPARED", "pins": len(pins),
                      "target_index": choice}))


def solve():
    frozen = check()
    prepared = load(HERE / "prepare.json")
    assert prepared["freeze_sha256"] == digest(HERE / "freeze.json")
    assert not (HERE / "run.json").exists()
    archive = HERE / "formula.xcnf.gz"
    assert digest(archive) == prepared["formula_archive_sha256"]
    raw = gzip.decompress(archive.read_bytes())
    assert hashlib.sha256(raw).hexdigest() == prepared["formula_sha256"]
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
            time.sleep(0.05)
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
    relation = None
    if status == "SAT":
        model = parsed_model(solver_text)
        assert model is not None
        check_serialized_xcnf(raw, model)
        relation = ordinary.verify_relation(
            load(PARENT / "freeze.json"), load(PARENT / "prepare.json"), model)
        assert relation["status"] == "verified_four_point_relation"
        assert relation["leaf_x_coords"] == prepared["witness_leaf_x_coords"]
        assert relation["selected_target_index"] == prepared[
            "selected_target_index"]
    save(HERE / "run.json", {
        "schema": "q20261010184800-run-v1", "proposal_id": PROPOSAL,
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "curve_id": frozen["curve_id"], "workload_id": frozen["workload_id"],
        "freeze_sha256": digest(HERE / "freeze.json"),
        "prepare_sha256": digest(HERE / "prepare.json"),
        "formula_sha256": prepared["formula_sha256"],
        "solver_sha256": frozen["solver_sha256"],
        "solver_flags": frozen["solver_flags"],
        "solver_status": status, "return_code": exit_code,
        "external_timeout": timeout,
        "conflicts_reported": int(conflicts[-1]) if conflicts else None,
        "solver_wall_seconds_exploratory": wall,
        "child_user_seconds": usage.ru_utime,
        "child_system_seconds": usage.ru_stime,
        "peak_child_rss_raw": usage.ru_maxrss,
        "peak_child_rss_unit": "bytes" if platform.system() == "Darwin"
                               else "kilobytes",
        "model_replay": relation,
        "stdout_gzip_sha256": digest(out_gz),
        "stderr_gzip_sha256": digest(err_gz)})
    print(json.dumps({"status": status,
                      "relation_status": relation["status"] if relation else None,
                      "wall_seconds": wall}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check", "prepare", "solve"))
    action = parser.parse_args().action
    if action == "freeze":
        freeze()
    elif action == "check":
        check(); print("PASS: freeze")
    elif action == "prepare":
        prepare()
    else:
        solve()
