#!/usr/bin/env python3
"""Exact two-leaf S3 handoff after fixing the first pair of a PDP4 query.

This is a stage diagnostic. The caller supplies the x coordinate of the
signed complement left by its verified first pair. SAT solutions are checked
against the Boolean formula and independently by curve arithmetic.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))

from chain_s3 import Formula, field, multiplication_table, square_destinations, evaluate_s3  # noqa: E402
from chain_s3_base_orbit import choose_base_orbit_x  # noqa: E402
from chain_s3_factored import s3_link_factored  # noqa: E402
from chain_s3_projected_sparse import projected_sparse_leaf  # noqa: E402
import curves  # noqa: E402


def n53_keys() -> tuple[list[int], dict]:
    path = PARENT / "bases/n53_weight3_orbits.json.gz"
    with gzip.open(path, "rt") as stream:
        archive = json.load(stream)
    fb = archive["factor_base"]
    packed = base64.b64decode(fb["packed_canonical_x_keys_base64"])
    assert hashlib.sha256(packed).hexdigest() == fb["enumerated_set_sha256"]
    assert len(packed) == 7 * fb["signed_frobenius_columns"]
    keys = [int.from_bytes(packed[i:i + 7], "little")
            for i in range(0, len(packed), 7)]
    return keys, archive


def build(n: int, complement_x: int):
    assert n in (53, 83) and 0 < complement_x < 1 << n
    onb = field.Onb(n)
    table = multiplication_table(onb)
    destinations = square_destinations(onb)
    formula = Formula()
    raw = []
    leaves = []
    if n == 53:
        keys, archive = n53_keys()
        assert archive["factor_base"]["actual_usable_points_B_before_folding"] == 24062
        assert archive["curve"]["cofactor"] == 428
        for _ in range(2):
            leaf, _, _ = choose_base_orbit_x(formula, n, keys, destinations)
            leaves.append(leaf)
    else:
        for _ in range(2):
            preimage, leaf = projected_sparse_leaf(formula, n, 5, table, destinations)
            raw.append(preimage)
            leaves.append(leaf)
    complement = [1 if complement_x >> i & 1 else -1 for i in range(n)]
    s3_link_factored(formula, leaves[0], leaves[1], complement,
                     table, destinations)
    return formula, raw, leaves, onb


def pin_bits(formula, bits, value):
    for i, bit in enumerate(bits):
        formula.clauses.append([bit if value >> i & 1 else -bit])


def xcoords(bits, assignment):
    return sum((1 << i) for i, bit in enumerate(bits) if assignment[bit])


def parse_assignment(stdout, nvars):
    if "s SATISFIABLE" not in stdout:
        return None
    values = {}
    for line in stdout.splitlines():
        if line.startswith("v "):
            for lit in map(int, line[2:].split()):
                if lit:
                    values[abs(lit)] = lit > 0
    assert len(values) == nvars, (len(values), nvars)
    return values


def verify(formula, raw, leaves, onb, complement_x, values):
    assert all(any(values[abs(lit)] == (lit > 0) for lit in row)
               for row in formula.clauses)
    assert all((sum(values[bit] for bit in row) & 1) == int(rhs)
               for row, rhs in formula.xors)
    xs = [xcoords(bits, values) for bits in leaves]
    assert evaluate_s3(onb, *(onb.fromCoords(x) for x in (*xs, complement_x))) == 0
    curve = curves.Curve(onb)
    points = [curve.pointFromX(onb.fromCoords(x)) for x in xs]
    assert all(point is not None for point in points)
    if raw:
        for preimage_bits, point in zip(raw, points):
            preimage = curve.pointFromX(onb.fromCoords(xcoords(preimage_bits, values)))
            assert preimage is not None
            assert curve.mul(preimage, 4)[0] == point[0]
    target = curve.pointFromX(onb.fromCoords(complement_x))
    assert target is not None
    signs = [point for point in points]
    assert any(curve.add(a, b) == target or curve.add(a, b) == curve.neg(target)
               for a in (signs[0], curve.neg(signs[0]))
               for b in (signs[1], curve.neg(signs[1])))
    return {"projected_leaf_x_coords": xs,
            "raw_leaf_x_coords": [xcoords(bits, values) for bits in raw],
            "boolean_constraints_checked": len(formula.clauses) + len(formula.xors),
            "s3_and_group_relation_checked": True}


def run(args):
    started = time.perf_counter_ns()
    formula, raw, leaves, onb = build(args.n, args.complement_x)
    for bits, value in zip(raw, args.pin_raw):
        pin_bits(formula, bits, value)
    for bits, value in zip(leaves, args.pin_projected):
        pin_bits(formula, bits, value)
    assert len(args.pin_raw) in (0, 2) and len(args.pin_projected) in (0, 2)
    build_s = (time.perf_counter_ns() - started) / 1e9
    path = HERE / f"{args.label}.xcnf"
    formula.write(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    command = ["cryptominisat5", "--maxtime", str(args.cap),
               "--verb", "1", "--printsol", "1"]
    if args.polar is not None:
        command += ["--polar", str(args.polar)]
    command.append(str(path))
    started = time.perf_counter_ns()
    try:
        child = subprocess.run(command, capture_output=True, text=True,
                               check=False, timeout=args.wall_cap)
        stdout, stderr, return_code = child.stdout, child.stderr, child.returncode
        wall_timeout = False
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or b"").decode(errors="replace")
        stderr = (exc.stderr or b"").decode(errors="replace")
        return_code = None
        wall_timeout = True
    solver_s = (time.perf_counter_ns() - started) / 1e9
    peak_child_rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    assignment = parse_assignment(stdout, formula.variables) if not wall_timeout else None
    check = verify(formula, raw, leaves, onb, args.complement_x, assignment) if assignment else None
    status = "SAT_VERIFIED" if check else (
        "WALL_TIMEOUT" if wall_timeout else
        "INDETERMINATE" if "s INDETERMINATE" in stdout else
        "UNSAT" if "s UNSATISFIABLE" in stdout else "SOLVER_FAILURE")
    result = {"label": args.label, "status": status, "n": args.n,
              "complement_x_coords": args.complement_x, "pin_raw": args.pin_raw,
              "pin_projected": args.pin_projected, "variables": formula.variables,
              "polar": args.polar,
              "cnf_clauses": len(formula.clauses), "xor_rows": len(formula.xors),
              "formula_sha256": digest, "formula_build_seconds_exploratory": build_s,
              "solver_wall_seconds_exploratory": solver_s, "solver_return_code": return_code,
              "wall_cap_seconds": args.wall_cap,
              "child_peak_rss_bytes_darwin": peak_child_rss,
              "solver_command": command, "check": check,
              "solver_stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
              "solver_stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest()}
    (HERE / f"{args.label}.stdout.txt").write_text(stdout)
    (HERE / f"{args.label}.stderr.txt").write_text(stderr)
    (HERE / f"{args.label}.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(53, 83), required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--complement-x", type=int, required=True)
    parser.add_argument("--pin-raw", type=int, nargs="*", default=[])
    parser.add_argument("--pin-projected", type=int, nargs="*", default=[])
    parser.add_argument("--cap", type=int, default=10)
    parser.add_argument("--wall-cap", type=int, default=25)
    parser.add_argument("--polar", choices=("true", "false", "rnd", "auto", "stable"))
    run(parser.parse_args())
