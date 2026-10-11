#!/usr/bin/env python3
"""Frozen ordinary N53 balanced t-coordinate four-point SAT gate."""

import argparse
import gzip
import hashlib
import itertools
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
W4 = HERE.parent
T_PARENT = W4.parent
ROOT = HERE.parents[3]
Q1419 = ROOT / "experiments/compact-s3-m4-20261003/q1419_partial_pin"
sys.path[:0] = [str(T_PARENT), str(Q1419),
                str(ROOT / "experiments/compact-s3-m4-20261003"),
                str(ROOT / "ecc2k130/codegen")]
import field  # noqa: E402
import curves  # noqa: E402
from chain_s3 import Formula, multiplication_table, square_destinations  # noqa: E402
from chain_s3_multitarget import choose_target_x  # noqa: E402
from run_cell import read_profile  # noqa: E402
from verify_archive import check_serialized_xcnf, parsed_model  # noqa: E402
from t_link import t3_link, t_of_x, x_roots_of_t  # noqa: E402

PROPOSAL = "Q20261010174500"
FREEZE = HERE / "freeze.json"
PREPARE = HERE / "prepare.json"
RUN = HERE / "run.json"
WALL_CAP = 120
MAX_CONFLICTS = 1_000_000


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    assert not path.exists(), path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def freeze():
    profile, parent, _ = read_profile(load(Q1419 / "protocol.json"), 53)
    base = load(W4 / "run.json")["rows"][1]
    assert profile["curve_id"] == load(W4 / "run.json")["curve_id"] == (
        "EC1N53Ckb1hf77aab617904")
    assert base["actual_usable_points_B"] == 151792
    assert base["folded_columns_K"] == 1432
    binary = Path(shutil.which("cryptominisat5") or "")
    assert binary.is_file()
    save(FREEZE, {"schema": "q20261010174500-freeze-v1",
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "isogeny": "none", "curve_id": profile["curve_id"],
        "ordinary_workload_id": profile["workload_id"],
        "public_target": profile["public_target"],
        "actual_usable_points_B": base["actual_usable_points_B"],
        "folded_columns_K": base["folded_columns_K"],
        "factor_base_enumerated_set_sha256": base["enumerated_set_sha256"],
        "cofactor": profile["cofactor"],
        "subgroup_order_r": profile["subgroup_order_r"],
        "raw_target_preimage_count": len(parent[
            "raw_preimage_x_coordinates"]),
        "q1419_protocol_sha256": digest(Q1419 / "protocol.json"),
        "w4_run_sha256": digest(W4 / "run.json"),
        "w4_base_sha256": digest(W4 / "bases/n53_t_weight4_columns.bin"),
        "t_link_source_sha256": digest(T_PARENT / "t_link.py"),
        "source_sha256": {name: digest(HERE / name) for name in
                          ("PROTOCOL.md", "experiment.py", "audit.py")},
        "solver_path": str(binary), "solver_sha256": digest(binary),
        "solver_flags": ["--verb", "1", "--threads", "1",
                         "--random", "0", "--maxconfl",
                         str(MAX_CONFLICTS)],
        "external_wall_cap_seconds": WALL_CAP})
    print(json.dumps({"freeze_sha256": digest(FREEZE)}))


def check_freeze():
    frozen = load(FREEZE)
    assert digest(Q1419 / "protocol.json") == frozen["q1419_protocol_sha256"]
    assert digest(W4 / "run.json") == frozen["w4_run_sha256"]
    assert digest(W4 / "bases/n53_t_weight4_columns.bin") == frozen[
        "w4_base_sha256"]
    assert digest(T_PARENT / "t_link.py") == frozen["t_link_source_sha256"]
    assert digest(frozen["solver_path"]) == frozen["solver_sha256"]
    for name, value in frozen["source_sha256"].items():
        assert digest(HERE / name) == value
    return frozen


def prepare():
    frozen = check_freeze()
    profile, parent, _ = read_profile(load(Q1419 / "protocol.json"), 53)
    f = field.Onb(53)
    target_options = sorted({f.toCoords(t_of_x(f, f.fromCoords(value)))
        for value in parent["raw_preimage_x_coordinates"]})
    assert len(parent["raw_preimage_x_coordinates"]) == frozen[
        "raw_target_preimage_count"]
    started = time.monotonic()
    formula = Formula()
    leaves = [[formula.new() for _ in range(53)] for _ in range(4)]
    mids = [[formula.new() for _ in range(53)] for _ in range(2)]
    for leaf in leaves:
        formula.at_most(leaf, 4)
        formula.clauses.append(leaf[:])
    target, selector = choose_target_x(formula, 53, target_options)
    table = multiplication_table(f)
    destinations = square_destinations(f)
    one = f.toCoords(f.one())
    t3_link(formula, leaves[0], leaves[1], mids[0], table, destinations, one)
    t3_link(formula, leaves[2], leaves[3], mids[1], table, destinations, one)
    t3_link(formula, mids[0], mids[1], target, table, destinations, one)
    construction = time.monotonic() - started
    path = HERE / "inputs/system.xcnf.gz"
    assert not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    raw_path = HERE / "inputs/system.xcnf"
    formula.write(raw_path)
    raw = raw_path.read_bytes()
    path.write_bytes(gzip.compress(raw, mtime=0))
    raw_path.unlink()
    save(PREPARE, {"schema": "q20261010174500-prepare-v1",
        "proposal_id": PROPOSAL, "curve_id": profile["curve_id"],
        "workload_id": profile["workload_id"],
        "freeze_sha256": digest(FREEZE),
        "target_t_options_coords": target_options,
        "raw_target_preimage_count": len(parent[
            "raw_preimage_x_coordinates"]),
        "leaves": leaves, "selector": selector,
        "variables": formula.variables,
        "cnf_clauses": len(formula.clauses),
        "xor_rows": len(formula.xors),
        "and_gates": len(formula.and_cache),
        "formula_raw_bytes": len(raw),
        "formula_sha256": hashlib.sha256(raw).hexdigest(),
        "formula_archive_sha256": digest(path),
        "formula_construction_seconds_exploratory": construction})
    print(json.dumps({"status": "PREPARED", "target_t_options":
        len(target_options), "variables": formula.variables,
        "cnf": len(formula.clauses), "xor": len(formula.xors),
        "formula_sha256": hashlib.sha256(raw).hexdigest()}))


def canonical_x(f, x):
    values = []
    for _ in range(f.m):
        values.append(f.toCoords(x))
        x = f.sqr(x)
    return min(values)


def verify_relation(frozen, prepared, model):
    f = field.Onb(53)
    e = curves.Curve(f)
    keys_raw = (W4 / "bases/n53_t_weight4_columns.bin").read_bytes()
    assert hashlib.sha256(keys_raw).hexdigest() == frozen[
        "factor_base_enumerated_set_sha256"]
    keys = {int.from_bytes(keys_raw[i:i+7], "little")
            for i in range(0, len(keys_raw), 7)}
    assert len(keys) == frozen["folded_columns_K"]
    tcoords = [sum((1 << i) for i, bit in enumerate(bits) if model[bit])
               for bits in prepared["leaves"]]
    point_rows = []
    for coords in tcoords:
        if coords == 0 or coords.bit_count() > 4:
            return {"status": "outside_t_weight", "leaf_t_coords": tcoords}
        roots = x_roots_of_t(f, e, f.fromCoords(coords))
        if not roots:
            return {"status": "nonrational_t", "leaf_t_coords": tcoords}
        point = e.pointFromX(roots[0])
        if point is None:
            return {"status": "nonrational_t", "leaf_t_coords": tcoords}
        subgroup = e.mul(point, frozen["cofactor"])
        if subgroup is None:
            return {"status": "identity_projection", "leaf_t_coords": tcoords}
        assert e.mul(subgroup, frozen["subgroup_order_r"]) is None
        key = canonical_x(f, subgroup[0])
        if key not in keys:
            return {"status": "outside_exact_t_base", "leaf_t_coords": tcoords}
        point_rows.append((subgroup, key))
    public = tuple(frozen["public_target"])
    assert e.onCurve(public)
    for signs in itertools.product((1, -1), repeat=4):
        total = None
        for (point, _), sign in zip(point_rows, signs):
            total = e.add(total, point if sign == 1 else e.neg(point))
        if total == public:
            return {"status": "verified_four_point_relation",
                "leaf_t_coords": tcoords, "signs": list(signs),
                "projected_points": [[int(x), int(y)]
                    for (x, y), _ in point_rows],
                "folded_columns": [key for _, key in point_rows],
                "distinct_columns": len({key for _, key in point_rows}),
                "public_target": list(public)}
    return {"status": "no_signed_public_sum", "leaf_t_coords": tcoords,
            "folded_columns": [key for _, key in point_rows]}


def solve():
    frozen = check_freeze()
    prepared = load(PREPARE)
    assert prepared["freeze_sha256"] == digest(FREEZE)
    archive = HERE / "inputs/system.xcnf.gz"
    assert digest(archive) == prepared["formula_archive_sha256"]
    raw = gzip.decompress(archive.read_bytes())
    assert hashlib.sha256(raw).hexdigest() == prepared["formula_sha256"]
    assert not RUN.exists()
    raw_path = HERE / "inputs/solver.xcnf"
    raw_path.write_bytes(raw)
    out_path = HERE / "solver.stdout"
    err_path = HERE / "solver.stderr"
    command = [frozen["solver_path"], *frozen["solver_flags"],
               str(raw_path)]
    started = time.monotonic()
    external_timeout = False
    with out_path.open("wb") as stdout, err_path.open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        while True:
            pid, status, usage = os.wait4(process.pid, os.WNOHANG)
            if pid:
                break
            if time.monotonic() - started >= WALL_CAP:
                external_timeout = True
                process.kill()
                _, status, usage = os.wait4(process.pid, 0)
                break
            time.sleep(0.02)
    wall = time.monotonic()-started
    return_code = os.waitstatus_to_exitcode(status)
    stdout, stderr = out_path.read_bytes(), err_path.read_bytes()
    out_gz = HERE / "solver.stdout.gz"
    err_gz = HERE / "solver.stderr.gz"
    out_gz.write_bytes(gzip.compress(stdout, mtime=0))
    err_gz.write_bytes(gzip.compress(stderr, mtime=0))
    out_path.unlink(); err_path.unlink(); raw_path.unlink()
    solver_text = stdout.decode(errors="replace")
    status_name = {10: "SAT", 20: "UNSAT"}.get(return_code,
                                                "BOUNDED_UNKNOWN")
    conflicts = re.findall(r"Conflicts in UIP\s*:\s*(\d+)", solver_text)
    relation = None
    verification_started = time.monotonic()
    if status_name == "SAT":
        model = parsed_model(solver_text)
        assert model is not None
        check_serialized_xcnf(raw, model)
        relation = verify_relation(frozen, prepared, model)
    verification = time.monotonic() - verification_started
    save(RUN, {"schema": "q20261010174500-run-v1",
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "isogeny": "none", "curve_id": frozen["curve_id"],
        "workload_id": frozen["ordinary_workload_id"],
        "public_target": frozen["public_target"],
        "actual_usable_points_B": frozen["actual_usable_points_B"],
        "folded_columns_K": frozen["folded_columns_K"],
        "factor_base_enumerated_set_sha256": frozen[
            "factor_base_enumerated_set_sha256"],
        "freeze_sha256": digest(FREEZE),
        "prepare_sha256": digest(PREPARE),
        "formula_sha256": prepared["formula_sha256"],
        "solver_sha256": frozen["solver_sha256"],
        "solver_flags": frozen["solver_flags"],
        "solver_status": status_name,
        "return_code": return_code,
        "external_timeout": external_timeout,
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
    print(json.dumps({"status": status_name,
        "relation_status": relation["status"] if relation else None,
        "solver_wall_seconds_exploratory": wall}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check", "prepare", "solve"))
    action = parser.parse_args().action
    if action == "freeze":
        freeze()
    elif action == "check":
        check_freeze(); print("PASS: freeze")
    elif action == "prepare":
        prepare()
    else:
        solve()
