#!/usr/bin/env python3
"""Validate Q1448 arithmetic and pinned SAT encoding before ordinary work."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))

import curves  # noqa: E402
import field  # noqa: E402
from q1419_partial_pin.run_cell import pin_bits  # noqa: E402
from q1420_root_theory.build_formula import convert_to_cnf  # noqa: E402
from q1425_reverse_pair.relax_control import serialize_cnf  # noqa: E402
from q1448_torsion_phi5.build_formula import (  # noqa: E402
    build, transformed_targets)

Q1446_VALIDATION = PARENT / "q1446_joint_pair_span/validation.json"
OUTPUT = HERE / "validation.json"
RUNTIME = HERE / "sage_runtime_info.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def phi5(onb, xs):
    """Independent arithmetic evaluation of the nine published terms."""
    one = onb.one()
    us = [onb.pow(x ^ one, (1 << onb.m) - 2) for x in xs]
    e = 0
    s = [one] + [0] * 5
    for u in us:
        e ^= u
        y = onb.sqr(u) ^ u
        for j in range(5, 0, -1):
            s[j] ^= onb.mul(s[j - 1], y)
    mul, power = onb.mul, onb.pow
    return (power(e, 8) ^ mul(power(e, 6), s[5]) ^
            mul(power(e, 4), power(s[4], 2)) ^
            mul(mul(power(e, 2), power(s[3], 2)), s[5]) ^
            power(s[3], 4) ^ mul(power(e, 2), power(s[5], 3)) ^
            mul(power(s[2], 2), power(s[5], 2)) ^
            power(s[5], 4) ^ power(s[5], 3))


def validate_one(case: dict) -> dict:
    n = int(case["degree"])
    assert n in (53, 83)
    h = 428 if n == 53 else 4
    relation = case["point_relation"]
    onb = field.Onb(n)

    def inverse(x):
        if x == 0:
            raise ZeroDivisionError
        return onb.pow(x, (1 << n) - 2)

    onb.inv = inverse
    curve = curves.Curve(onb)
    raw_x = [int(x) for x in relation["raw_leaf_x"]]
    points = []
    for mask, sign in zip(raw_x, relation["signs"]):
        point = curve.pointFromX(onb.fromCoords(mask))
        assert point is not None
        points.append(point if sign > 0 else curve.neg(point))
    total = None
    for point in points:
        total = curve.add(total, point)
    assert total is not None
    assert curve.mul(total, h) == tuple(relation["public_target"])
    raw_target = onb.toCoords(total[0])
    assert phi5(onb, [*(onb.fromCoords(x) for x in raw_x),
                       total[0]]) == 0

    # N53's known witness belongs to the archived ordinary public target.
    # N83's control is planted on a separately labeled public target.
    if n == 53:
        formula, meta = build(n)
        assert raw_target in meta["raw_target_x_values"]
        selector_choice = meta["raw_target_x_values"].index(raw_target)
        control_law = "archived N53 ordinary target, fully pinned witness"
    else:
        formula, meta = build(n, [raw_target],
                              relation["public_target"])
        selector_choice = 0
        control_law = "N83 planted target, fully pinned witness"
    assert meta["curve_id"] == case["curve_id"]
    assert meta["factor_base_actual_B"] == case["factor_base_actual_B"]
    assert meta["folded_columns_K"] == case["folded_columns_K"]
    assert meta["factor_base_enumerated_set_sha256"] == case[
        "factor_base_enumerated_set_sha256"]
    for bits, mask in zip(meta["leaf_x_variables"], raw_x):
        pin_bits(formula, bits, mask)
    for bits, mask in zip(meta["leaf_phi_variables"], raw_x):
        pin_bits(formula, bits, transformed_targets(onb, [mask])[0])
    pin_bits(formula, meta["target_selector_variables"], selector_choice)
    variables, clauses = convert_to_cnf(formula)
    raw_cnf = serialize_cnf(variables, clauses)
    with tempfile.TemporaryDirectory(prefix=f"q1448-n{n}-") as directory:
        path = Path(directory) / "control.cnf"
        path.write_bytes(raw_cnf)
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.perf_counter_ns()
        completed = subprocess.run(
            ["cadical", "-q", "-t", "30", "-n", str(path)],
            capture_output=True, text=True, timeout=45, check=False)
        wall_ns = time.perf_counter_ns() - start
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
    assert completed.returncode == 10
    assert "s SATISFIABLE" in completed.stdout
    return {
        "degree_n": n,
        "curve_id": case["curve_id"],
        "factor_base_actual_B": meta["factor_base_actual_B"],
        "folded_columns_K": meta["folded_columns_K"],
        "factor_base_enumerated_set_sha256": meta[
            "factor_base_enumerated_set_sha256"],
        "control_law": control_law,
        "raw_leaf_x": raw_x,
        "raw_target_x": raw_target,
        "target_selector_choice": selector_choice,
        "public_target": relation["public_target"],
        "cofactor_projection_check": "pass",
        "phi5_arithmetic_zero": True,
        "pinned_cnf_sat": True,
        "pinned_cnf_sha256": hashlib.sha256(raw_cnf).hexdigest(),
        "pinned_cnf_variables": variables,
        "pinned_cnf_clauses": len(clauses),
        "solver_exit_code": completed.returncode,
        "solver_wall_ns_exploratory": wall_ns,
        "peak_child_rss_raw": after.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "solver_stdout_sha256": hashlib.sha256(
            completed.stdout.encode()).hexdigest(),
        "solver_stderr_sha256": hashlib.sha256(
            completed.stderr.encode()).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    validation = json.loads(Q1446_VALIDATION.read_text())
    assert validation["proposal_id"] == "Q1446"
    runtime = json.loads(RUNTIME.read_text())
    assert runtime["status"] == "verified"
    rows = [validate_one(case) for case in validation["controls"]]
    result = {
        "kind": "q1448_torsion_phi5_prerun_controls",
        "proposal_id": "Q1448", "candidate_id": None,
        "isogeny": "none", "status": "pass",
        "rows": rows,
        "q1446_validation_sha256": sha(Q1446_VALIDATION),
        "sage_runtime_info_sha256": sha(RUNTIME),
        "builder_source_sha256": sha(HERE / "build_formula.py"),
        "validator_source_sha256": sha(Path(__file__)),
        "cadical_version": subprocess.run(
            ["cadical", "--version"], capture_output=True, text=True,
            check=True).stdout.strip(),
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
    }
    if args.check:
        # Timing and peak RSS are exploratory and can differ in a replay.
        prior = json.loads(OUTPUT.read_text())
        for old, new in zip(prior["rows"], rows):
            for key in ("solver_wall_ns_exploratory", "peak_child_rss_raw",
                        "pinned_cnf_sha256", "solver_stdout_sha256"):
                new[key] = old[key]
        assert prior == result
        print("Q1448 N53/N83 pinned controls: PASS")
    else:
        if OUTPUT.exists():
            raise FileExistsError(f"refusing to overwrite {OUTPUT}")
        OUTPUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"proposal_id": "Q1448", "status": "pass",
                          "degrees": [row["degree_n"] for row in rows]}))


if __name__ == "__main__":
    main()
