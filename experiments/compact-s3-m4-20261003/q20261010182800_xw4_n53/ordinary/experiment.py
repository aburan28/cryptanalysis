#!/usr/bin/env python3
"""Frozen ordinary N53 balanced x-S3 query on the exact weight-four base."""

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
BASE = HERE.parent
PARENT = BASE.parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(PARENT / "q1419_partial_pin"), str(PARENT),
                str(ROOT / "ecc2k130/codegen")]
import field  # noqa: E402
import curves  # noqa: E402
from chain_s3_balanced_multitarget import build_balanced  # noqa: E402
from chain_s3_multitarget import decode_choice  # noqa: E402
from run_probe import lift  # noqa: E402
from verify_archive import check_serialized_xcnf, parsed_model  # noqa: E402

PROPOSAL = "Q20261010183500"
WALL_CAP = 1200
CONFLICT_CAP = 1_000_000
PARENT_RUN = PARENT / "runs/n53_q1410_ordinary.json"
PARENT_PROTOCOL = PARENT / "q1410_balanced_s3_n53_protocol.json"
PARENT_ARCHIVE = PARENT / "runs/n53_q1410_ordinary.xcnf.gz"
COSET = PARENT / "runs/n53_ordinary_raw_preimages.json"
BASE_RUN = BASE / "run.json"
BASE_KEYS = BASE / "n53_x_weight4_columns.bin"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def freeze():
    parent, protocol, coset, base = [load(path) for path in
        (PARENT_RUN, PARENT_PROTOCOL, COSET, BASE_RUN)]
    assert parent["proposal_id"] == protocol["proposal_id"] == "Q1410"
    assert base["proposal_id"] == "Q20261010182800"
    assert parent["curve_id"] == base["curve_id"] == (
        "EC1N53Ckb1hf77aab617904")
    assert parent["workload_id"] == base["workload_id"] == (
        "74f2979b3e68")
    assert parent["public_target"] == list(map(int, coset["public_target"]))
    assert parent["raw_preimage_x_coordinates"] == coset[
        "raw_target_x_coordinates"]
    assert base["actual_usable_points_B"] == 324042
    assert base["folded_columns_K"] == 3057
    assert base["enumerated_set_sha256"] == digest(BASE_KEYS)
    solver = parent["attempts"][0]["solver_command"][0]
    assert digest(solver) == parent["solver_binary_sha256"]
    raw = gzip.decompress(PARENT_ARCHIVE.read_bytes())
    assert hashlib.sha256(raw).hexdigest() == parent["attempts"][0][
        "xcnf_sha256"]
    save(HERE / "freeze.json", {
        "schema": "q20261010183500-freeze-v1", "proposal_id": PROPOSAL,
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "curve_id": parent["curve_id"], "workload_id": parent["workload_id"],
        "public_target": parent["public_target"],
        "cofactor": protocol["curve"]["cofactor"],
        "subgroup_order_r": int(protocol["curve"]["subgroup_order"]),
        "actual_usable_points_B": base["actual_usable_points_B"],
        "folded_columns_K": base["folded_columns_K"],
        "factor_base_enumerated_set_sha256": digest(BASE_KEYS),
        "base_run_sha256": digest(BASE_RUN),
        "parent_run_sha256": digest(PARENT_RUN),
        "parent_protocol_sha256": digest(PARENT_PROTOCOL),
        "parent_formula_archive_sha256": digest(PARENT_ARCHIVE),
        "parent_formula_sha256": hashlib.sha256(raw).hexdigest(),
        "coset_sha256": digest(COSET),
        "solver_path": solver, "solver_sha256": digest(solver),
        "solver_flags": ["--verb", "1", "--threads", "1",
                         "--random", "0", "--maxconfl", str(CONFLICT_CAP)],
        "external_wall_cap_seconds": WALL_CAP,
        "source_sha256": {name: digest(HERE / name) for name in
                          ("PROTOCOL.md", "experiment.py", "audit.py")}})
    print(json.dumps({"freeze_sha256": digest(HERE / "freeze.json")}))


def check():
    frozen = load(HERE / "freeze.json")
    for path, key in ((BASE_RUN, "base_run_sha256"),
                      (PARENT_RUN, "parent_run_sha256"),
                      (PARENT_PROTOCOL, "parent_protocol_sha256"),
                      (PARENT_ARCHIVE, "parent_formula_archive_sha256"),
                      (COSET, "coset_sha256"),
                      (BASE_KEYS, "factor_base_enumerated_set_sha256")):
        assert digest(path) == frozen[key]
    assert digest(frozen["solver_path"]) == frozen["solver_sha256"]
    for name, value in frozen["source_sha256"].items():
        assert digest(HERE / name) == value
    return frozen


def prepare():
    frozen = check()
    assert not (HERE / "formula.xcnf.gz").exists()
    raw_xs = load(COSET)["raw_target_x_coordinates"]
    assert len(raw_xs) == 428
    # Check that this builder and exact target coset reproduce Q1410.
    control, _, _, _, _ = build_balanced(53, 3, raw_xs)
    path = HERE / "control.xcnf"
    control.write(path)
    assert digest(path) == frozen["parent_formula_sha256"]
    path.unlink()
    started = time.monotonic()
    formula, leaves, _, _, selector = build_balanced(53, 4, raw_xs)
    construction = time.monotonic() - started
    path = HERE / "formula.xcnf"
    formula.write(path)
    raw = path.read_bytes()
    archive = HERE / "formula.xcnf.gz"
    archive.write_bytes(gzip.compress(raw, mtime=0))
    path.unlink()
    save(HERE / "prepare.json", {
        "schema": "q20261010183500-prepare-v1", "proposal_id": PROPOSAL,
        "freeze_sha256": digest(HERE / "freeze.json"),
        "parent_formula_sha256": frozen["parent_formula_sha256"],
        "formula_sha256": hashlib.sha256(raw).hexdigest(),
        "formula_archive_sha256": digest(archive),
        "formula_raw_bytes": len(raw),
        "variables": formula.variables,
        "cnf_clauses": len(formula.clauses),
        "xor_rows": len(formula.xors),
        "and_gates": len(formula.and_cache),
        "leaves": leaves, "selector": selector,
        "target_preimage_count": len(raw_xs),
        "formula_construction_seconds_exploratory": construction})
    print(json.dumps({"status": "PREPARED", "variables": formula.variables,
                      "cnf": len(formula.clauses), "xor": len(formula.xors),
                      "and_gates": len(formula.and_cache)}))


def verify_relation(frozen, prepared, model):
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    raw = load(COSET)
    choice = decode_choice(prepared["selector"], model)
    assert 0 <= choice < len(raw["raw_target_points"])
    raw_point = tuple(map(int, raw["raw_target_points"][choice]))
    public = tuple(map(int, frozen["public_target"]))
    coords, relation, status = lift(onb, curve, prepared["leaves"], model,
                                    raw_point, public, frozen["cofactor"])
    assert all(0 < x < (1 << 53) and x.bit_count() <= 4 for x in coords)
    record = {"status": status, "selected_target_index": choice,
              "leaf_x_coords": coords, "relation": relation}
    if relation is None:
        return record
    keys_raw = BASE_KEYS.read_bytes()
    keys = {int.from_bytes(keys_raw[i:i+7], "little")
            for i in range(0, len(keys_raw), 7)}
    assert len(keys) == frozen["folded_columns_K"]
    columns = []
    for values in relation["projected_points"]:
        point = tuple(map(int, values))
        assert curve.onCurve(point)
        assert curve.mul(point, frozen["subgroup_order_r"]) is None
        x = point[0]
        cycle = []
        for _ in range(53):
            cycle.append(onb.toCoords(x))
            x = onb.sqr(x)
        key = min(cycle)
        assert key in keys
        columns.append(key)
    record["folded_columns"] = columns
    record["distinct_columns"] = len(set(columns))
    return record


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
    relation = None
    if status == "SAT":
        model = parsed_model(solver_text)
        assert model is not None
        check_serialized_xcnf(raw, model)
        relation = verify_relation(frozen, prepared, model)
    verification = time.monotonic() - verification_started
    save(HERE / "run.json", {
        "schema": "q20261010183500-run-v1", "proposal_id": PROPOSAL,
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "curve_id": frozen["curve_id"], "workload_id": frozen["workload_id"],
        "public_target": frozen["public_target"],
        "actual_usable_points_B": frozen["actual_usable_points_B"],
        "folded_columns_K": frozen["folded_columns_K"],
        "factor_base_enumerated_set_sha256": frozen[
            "factor_base_enumerated_set_sha256"],
        "freeze_sha256": digest(HERE / "freeze.json"),
        "prepare_sha256": digest(HERE / "prepare.json"),
        "formula_sha256": prepared["formula_sha256"],
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
    print(json.dumps({"status": status,
                      "relation_status": relation["status"] if relation else None,
                      "wall_seconds": wall,
                      "child_cpu_seconds": usage.ru_utime + usage.ru_stime}))


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
