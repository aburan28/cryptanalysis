#!/usr/bin/env python3
"""Frozen ordinary N83 balanced-S3 leaf-weight search."""

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
ROOT = HERE.parents[2]
sys.path[:0] = [str(PARENT / "q1419_partial_pin"), str(PARENT),
                str(ROOT / "ecc2k130/codegen")]
import field  # noqa: E402
import curves  # noqa: E402
from chain_s3_balanced_multitarget import build_balanced  # noqa: E402
from chain_s3_multitarget import decode_choice  # noqa: E402
from run_probe import lift  # noqa: E402
from verify_archive import parsed_model  # noqa: E402
from q1325_inputs import read_inputs  # noqa: E402

PROPOSAL = "Q20261010193000"
WEIGHTS = (5, 6, 7, 8)
CONFLICT_CAP = 100_000
WALL_CAP = 180
PARENT_RUN = PARENT / "runs/n83_q1408_ordinary.json"
PARENT_FORMULA = PARENT / "runs/n83_q1408_ordinary.xcnf.gz"
COSET = PARENT / "runs/n83_ordinary_raw_preimages.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def freeze():
    parent = load(PARENT_RUN)
    coset = load(COSET)
    base_path, base, keys_path, keys, baseline_path, baseline = read_inputs()
    fb = base["factor_base"]
    assert parent["proposal_id"] == "Q1408"
    assert parent["curve_id"] == base["curve"]["curve_id"] == (
        "EC1N83Ckb1h876c2921cb64")
    assert parent["workload_id"] == baseline["workload_id"] == (
        "bab50a1e5f66")
    assert parent["public_target"] == list(map(int, baseline[
        "public_subgroup_target"]))
    assert coset["raw_target_x_coordinates"] == parent[
        "raw_preimage_x_coordinates"]
    assert len(coset["raw_target_x_coordinates"]) == 4
    assert fb["actual_usable_points_B_before_folding"] == 30977592
    assert fb["signed_frobenius_columns"] == len(keys) == 186612
    assert fb["enumerated_set_sha256"] == parent[
        "factor_base_enumerated_set_sha256"]
    raw_parent = gzip.decompress(PARENT_FORMULA.read_bytes())
    assert hashlib.sha256(raw_parent).hexdigest() == parent[
        "attempts"][0]["xcnf_sha256"]
    solver = parent["attempts"][0]["solver_command"][0]
    assert sha(solver) == parent["solver_binary_sha256"]
    inputs = (PARENT_RUN, PARENT_FORMULA, COSET, base_path, keys_path,
              baseline_path, Path(field.__file__), Path(curves.__file__),
              PARENT / "chain_s3_balanced_multitarget.py",
              PARENT / "chain_s3.py", PARENT / "chain_s3_factored.py")
    save(HERE / "freeze.json", {
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "curve_id": parent["curve_id"], "workload_id": parent["workload_id"],
        "isogeny": "none", "public_target": parent["public_target"],
        "cofactor": int(base["curve"]["cofactor"]),
        "subgroup_order_r": int(base["curve"]["subgroup_order"]),
        "weights": list(WEIGHTS),
        "weight5_exact_base_B": fb["actual_usable_points_B_before_folding"],
        "weight5_exact_folded_K": fb["signed_frobenius_columns"],
        "weight5_enumerated_set_sha256": fb["enumerated_set_sha256"],
        "weight5_parent_formula_sha256": hashlib.sha256(raw_parent).hexdigest(),
        "solver_path": solver, "solver_sha256": sha(solver),
        "solver_flags": ["--verb", "1", "--threads", "1", "--random", "0",
                         "--maxconfl", str(CONFLICT_CAP)],
        "external_wall_cap_seconds": WALL_CAP,
        "input_sha256": {str(path.relative_to(ROOT)): sha(path)
                         for path in inputs},
        "source_sha256": {name: sha(HERE / name) for name in
                          ("PROTOCOL.md", "sweep.py", "audit.py")}})


def check():
    frozen = load(HERE / "freeze.json")
    assert frozen["weights"] == list(WEIGHTS)
    for name, value in frozen["source_sha256"].items():
        assert sha(HERE / name) == value
    for name, value in frozen["input_sha256"].items():
        assert sha(ROOT / name) == value
    assert sha(frozen["solver_path"]) == frozen["solver_sha256"]
    return frozen


def prepare():
    frozen = check()
    raw_xs = load(COSET)["raw_target_x_coordinates"]
    assert not (HERE / "prepare.json").exists()
    rows = []
    for weight in WEIGHTS:
        started = time.monotonic()
        formula, leaves, _, _, selector = build_balanced(83, weight, raw_xs)
        build_seconds = time.monotonic()-started
        path = HERE / f"w{weight}.xcnf"
        assert not path.exists()
        formula.write(path)
        raw = path.read_bytes()
        if weight == 5:
            assert hashlib.sha256(raw).hexdigest() == frozen[
                "weight5_parent_formula_sha256"]
        archive = HERE / f"w{weight}.xcnf.gz"
        assert not archive.exists()
        archive.write_bytes(gzip.compress(raw, mtime=0))
        path.unlink()
        rows.append({"weight": weight, "formula_sha256": hashlib.sha256(
            raw).hexdigest(), "formula_archive_sha256": sha(archive),
            "formula_raw_bytes": len(raw), "variables": formula.variables,
            "cnf_clauses": len(formula.clauses),
            "xor_rows": len(formula.xors),
            "and_gates": len(formula.and_cache),
            "leaves": leaves, "selector": selector,
            "construction_seconds_exploratory": build_seconds})
    save(HERE / "prepare.json", {
        "proposal_id": PROPOSAL, "freeze_sha256": sha(HERE / "freeze.json"),
        "target_preimage_count": len(raw_xs), "rows": rows})
    print(json.dumps([{"weight": row["weight"],
                       "variables": row["variables"],
                       "cnf": row["cnf_clauses"],
                       "xor": row["xor_rows"]} for row in rows]))


def run(weight):
    frozen = check()
    assert weight in WEIGHTS
    prepared = load(HERE / "prepare.json")
    assert prepared["freeze_sha256"] == sha(HERE / "freeze.json")
    row = next(item for item in prepared["rows"] if item["weight"] == weight)
    receipt = HERE / f"w{weight}.json"
    assert not receipt.exists()
    archive = HERE / f"w{weight}.xcnf.gz"
    assert sha(archive) == row["formula_archive_sha256"]
    raw = gzip.decompress(archive.read_bytes())
    assert hashlib.sha256(raw).hexdigest() == row["formula_sha256"]
    input_path = HERE / f"w{weight}.solver.xcnf"
    input_path.write_bytes(raw)
    stdout_path = HERE / f"w{weight}.stdout"
    stderr_path = HERE / f"w{weight}.stderr"
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
    stdout, stderr = stdout_path.read_bytes(), stderr_path.read_bytes()
    out_archive = HERE / f"w{weight}.stdout.gz"
    err_archive = HERE / f"w{weight}.stderr.gz"
    out_archive.write_bytes(gzip.compress(stdout, mtime=0))
    err_archive.write_bytes(gzip.compress(stderr, mtime=0))
    input_path.unlink(); stdout_path.unlink(); stderr_path.unlink()
    output = stdout.decode(errors="replace")
    status = {10: "SAT", 20: "UNSAT"}.get(exit_code, "BOUNDED_UNKNOWN")
    conflicts = re.findall(r"Conflicts in UIP\s*:\s*(\d+)", output)
    relation = None
    if status == "SAT":
        model = parsed_model(output)
        assert model is not None
        choice = decode_choice(row["selector"], model)
        coset = load(COSET)
        raw_point = tuple(map(int, coset["raw_target_points"][choice]))
        public = tuple(map(int, frozen["public_target"]))
        onb = field.Onb(83)
        curve = curves.Curve(onb)
        coords, rel, verified = lift(onb, curve, row["leaves"], model,
                                      raw_point, public, frozen["cofactor"])
        assert all(0 < x < (1 << 83) and x.bit_count() <= weight
                   for x in coords)
        assert verified == "verified_four_point_relation" and rel is not None
        assert all(curve.mul(tuple(map(int, point)), frozen[
            "subgroup_order_r"]) is None for point in rel["projected_points"])
        relation = {"status": verified, "selected_target_index": choice,
                    "leaf_x_coords": coords, "relation": rel}
    save(receipt, {
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "curve_id": frozen["curve_id"], "workload_id": frozen["workload_id"],
        "isogeny": "none", "weight": weight,
        "actual_usable_points_B": (frozen["weight5_exact_base_B"]
                                   if weight == 5 else None),
        "folded_columns_K": (frozen["weight5_exact_folded_K"]
                             if weight == 5 else None),
        "factor_base_enumerated_set_sha256": (
            frozen["weight5_enumerated_set_sha256"] if weight == 5 else None),
        "status": status, "exit_code": exit_code, "timed_out": timed_out,
        "last_reported_conflicts": int(conflicts[-1]) if conflicts else None,
        "child_cpu_seconds": usage.ru_utime+usage.ru_stime,
        "wall_seconds_exploratory": wall,
        "peak_child_rss_raw": usage.ru_maxrss,
        "peak_child_rss_unit": "bytes" if platform.system() == "Darwin"
                               else "kilobytes",
        "freeze_sha256": sha(HERE / "freeze.json"),
        "prepare_sha256": sha(HERE / "prepare.json"),
        "formula_archive_sha256": sha(archive),
        "stdout_archive_sha256": sha(out_archive),
        "stderr_archive_sha256": sha(err_archive),
        "relation": relation})
    print(json.dumps({"weight": weight, "status": status,
                      "conflicts": int(conflicts[-1]) if conflicts else None,
                      "child_cpu": usage.ru_utime+usage.ru_stime,
                      "wall": wall, "relation": relation is not None}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check", "prepare", "run"))
    parser.add_argument("--weight", type=int, choices=WEIGHTS)
    args = parser.parse_args()
    if args.action == "freeze":
        freeze()
    elif args.action == "check":
        check(); print("PASS: freeze")
    elif args.action == "prepare":
        prepare()
    else:
        assert args.weight is not None
        run(args.weight)
