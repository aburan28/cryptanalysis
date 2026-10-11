#!/usr/bin/env python3
"""Frozen ordinary N53 balanced S3 screen at normal-x weight five."""

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
W4 = PARENT / "q20261010182800_xw4_n53/ordinary"
ROOT = HERE.parents[2]
sys.path[:0] = [str(PARENT / "q1419_partial_pin"), str(PARENT),
                str(ROOT / "ecc2k130/codegen")]
import field  # noqa: E402
import curves  # noqa: E402
from chain_s3_balanced_multitarget import build_balanced  # noqa: E402
from chain_s3_multitarget import decode_choice  # noqa: E402
from run_probe import lift  # noqa: E402
from verify_archive import parsed_model  # noqa: E402

PROPOSAL = "Q20261010191500"
PARENT_RUN = PARENT / "runs/n53_q1410_ordinary.json"
PARENT_PROTOCOL = PARENT / "q1410_balanced_s3_n53_protocol.json"
COSET = PARENT / "runs/n53_ordinary_raw_preimages.json"
W4_PREPARE = W4 / "prepare.json"
W4_ARCHIVE = W4 / "formula.xcnf.gz"
WALL_CAP = 300
CONFLICT_CAP = 100_000


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def freeze():
    parent = load(PARENT_RUN)
    protocol = load(PARENT_PROTOCOL)
    w4 = load(W4_PREPARE)
    coset = load(COSET)
    assert parent["proposal_id"] == protocol["proposal_id"] == "Q1410"
    assert parent["curve_id"] == "EC1N53Ckb1hf77aab617904"
    assert parent["workload_id"] == "74f2979b3e68"
    assert coset["raw_target_x_coordinates"] == parent[
        "raw_preimage_x_coordinates"]
    assert w4["formula_sha256"] == hashlib.sha256(
        gzip.decompress(W4_ARCHIVE.read_bytes())).hexdigest()
    solver = parent["attempts"][0]["solver_command"][0]
    assert digest(solver) == parent["solver_binary_sha256"]
    save(HERE / "freeze.json", {
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "curve_id": parent["curve_id"], "workload_id": parent["workload_id"],
        "public_target": parent["public_target"], "isogeny": "none",
        "cofactor": protocol["curve"]["cofactor"],
        "subgroup_order_r": int(protocol["curve"]["subgroup_order"]),
        "normal_x_weight_bound": 5,
        "actual_usable_points_B": None, "folded_columns_K": None,
        "solver_path": solver, "solver_sha256": digest(solver),
        "solver_flags": ["--verb", "1", "--threads", "1", "--random", "0",
                         "--maxconfl", str(CONFLICT_CAP)],
        "external_wall_cap_seconds": WALL_CAP,
        "w4_formula_sha256": w4["formula_sha256"],
        "input_sha256": {str(path.relative_to(ROOT)): digest(path) for path in
                         (PARENT_RUN, PARENT_PROTOCOL, COSET, W4_PREPARE,
                          W4_ARCHIVE, Path(field.__file__), Path(curves.__file__))},
        "source_sha256": {name: digest(HERE / name) for name in
                          ("PROTOCOL.md", "experiment.py", "audit.py")}})


def check():
    frozen = load(HERE / "freeze.json")
    assert digest(frozen["solver_path"]) == frozen["solver_sha256"]
    for name, value in frozen["source_sha256"].items():
        assert digest(HERE / name) == value
    for name, value in frozen["input_sha256"].items():
        assert digest(ROOT / name) == value
    return frozen


def prepare():
    frozen = check()
    assert not (HERE / "prepare.json").exists()
    raw_xs = load(COSET)["raw_target_x_coordinates"]
    assert len(raw_xs) == 428
    control, _, _, _, _ = build_balanced(53, 4, raw_xs)
    path = HERE / "control.xcnf"
    control.write(path)
    assert digest(path) == frozen["w4_formula_sha256"]
    path.unlink()
    start = time.monotonic()
    formula, leaves, _, _, selector = build_balanced(53, 5, raw_xs)
    build_seconds = time.monotonic()-start
    path = HERE / "formula.xcnf"
    formula.write(path)
    raw = path.read_bytes()
    archive = HERE / "formula.xcnf.gz"
    assert not archive.exists()
    archive.write_bytes(gzip.compress(raw, mtime=0))
    path.unlink()
    save(HERE / "prepare.json", {
        "proposal_id": PROPOSAL, "freeze_sha256": digest(HERE / "freeze.json"),
        "formula_sha256": hashlib.sha256(raw).hexdigest(),
        "formula_archive_sha256": digest(archive),
        "formula_raw_bytes": len(raw), "variables": formula.variables,
        "cnf_clauses": len(formula.clauses), "xor_rows": len(formula.xors),
        "and_gates": len(formula.and_cache),
        "target_preimage_count": len(raw_xs), "leaves": leaves,
        "selector": selector,
        "formula_construction_seconds_exploratory": build_seconds})
    print(json.dumps({"variables": formula.variables,
                      "cnf": len(formula.clauses), "xor": len(formula.xors),
                      "and_gates": len(formula.and_cache)}))


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
    stdout_path, stderr_path = HERE / "solver.stdout", HERE / "solver.stderr"
    command = [frozen["solver_path"], *frozen["solver_flags"], str(input_path)]
    start = time.monotonic()
    timeout = False
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        while True:
            pid, code, usage = os.wait4(process.pid, os.WNOHANG)
            if pid:
                break
            if time.monotonic()-start >= WALL_CAP:
                timeout = True
                process.kill()
                _, code, usage = os.wait4(process.pid, 0)
                break
            time.sleep(0.1)
    wall = time.monotonic()-start
    exit_code = os.waitstatus_to_exitcode(code)
    stdout = stdout_path.read_bytes()
    stderr = stderr_path.read_bytes()
    (HERE / "solver.stdout.gz").write_bytes(gzip.compress(stdout, mtime=0))
    (HERE / "solver.stderr.gz").write_bytes(gzip.compress(stderr, mtime=0))
    input_path.unlink(); stdout_path.unlink(); stderr_path.unlink()
    output = stdout.decode(errors="replace")
    status = {10: "SAT", 20: "UNSAT"}.get(exit_code, "BOUNDED_UNKNOWN")
    conflicts = re.findall(r"Conflicts in UIP\s*:\s*(\d+)", output)
    relation = None
    if status == "SAT":
        model = parsed_model(output)
        assert model is not None
        choice = decode_choice(prepared["selector"], model)
        coset = load(COSET)
        raw_point = tuple(map(int, coset["raw_target_points"][choice]))
        public = tuple(map(int, frozen["public_target"]))
        onb = field.Onb(53)
        curve = curves.Curve(onb)
        coords, rel, verified = lift(onb, curve, prepared["leaves"], model,
                                      raw_point, public, frozen["cofactor"])
        assert all(0 < x < (1 << 53) and x.bit_count() <= 5 for x in coords)
        assert verified == "verified_four_point_relation"
        assert rel is not None
        assert all(curve.mul(tuple(map(int, row)), frozen[
            "subgroup_order_r"]) is None for row in rel["projected_points"])
        relation = {"status": verified, "selected_target_index": choice,
                    "leaf_x_coords": coords, "relation": rel}
    save(HERE / "run.json", {
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "curve_id": frozen["curve_id"], "workload_id": frozen["workload_id"],
        "isogeny": "none", "status": status, "timed_out": timeout,
        "exit_code": exit_code,
        "last_reported_conflicts": int(conflicts[-1]) if conflicts else None,
        "child_cpu_seconds": usage.ru_utime+usage.ru_stime,
        "wall_seconds_exploratory": wall,
        "peak_child_rss_raw": usage.ru_maxrss,
        "peak_child_rss_unit": "bytes" if platform.system() == "Darwin"
                               else "kilobytes",
        "freeze_sha256": digest(HERE / "freeze.json"),
        "prepare_sha256": digest(HERE / "prepare.json"),
        "formula_archive_sha256": digest(archive),
        "stdout_archive_sha256": digest(HERE / "solver.stdout.gz"),
        "stderr_archive_sha256": digest(HERE / "solver.stderr.gz"),
        "relation": relation})
    print(json.dumps({"status": status,
                      "conflicts": int(conflicts[-1]) if conflicts else None,
                      "cpu": usage.ru_utime+usage.ru_stime,
                      "wall": wall, "relation": relation is not None}))


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
