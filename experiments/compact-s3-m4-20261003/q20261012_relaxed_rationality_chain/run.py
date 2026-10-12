#!/usr/bin/env python3
"""Compare exact and deferred-rationality four-leaf S3 chains at N83."""
from __future__ import annotations

import argparse
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
from chain_s3 import Formula, field, multiplication_table, product, square_destinations, evaluate_s3  # noqa: E402
from chain_s3_factored import s3_link_factored  # noqa: E402
from chain_s3_projected_sparse import build_projected_sparse_chain, square_bits  # noqa: E402
import curves  # noqa: E402


TARGETS = {
    "selected": PARENT / "q20261011_wdsat_phase_restart/target.json",
    "holdout": PARENT / "q20261011_n83_selector_holdout/target.json",
}
PLANTED_RAW = (3, 9, 10, 11)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def relaxed_leaf(formula, n, weight, table, square_dest):
    raw_x = [formula.new() for _ in range(n)]
    formula.at_most(raw_x, weight)
    formula.clauses.append(raw_x[:])
    x4 = square_bits(square_bits(raw_x, square_dest), square_dest)
    x8 = square_bits(x4, square_dest)
    x16 = square_bits(x8, square_dest)
    x12 = product(formula, x8, x4, table)
    denominator = [formula.new() for _ in range(n)]
    for output, left, right in zip(denominator, x12, x4):
        formula.xor_relation((output, left, right))
    projected_x = [formula.new() for _ in range(n)]
    scaled = product(formula, projected_x, denominator, table)
    for value, eighth, sixteenth in zip(scaled, x8, x16):
        formula.xor_relation((value, eighth, sixteenth), True)
    return raw_x, projected_x


def relaxed_chain(n, target_x):
    onb = field.Onb(n)
    table = multiplication_table(onb)
    square_dest = square_destinations(onb)
    formula = Formula()
    raw, projected = [], []
    for _ in range(4):
        a, b = relaxed_leaf(formula, n, 5, table, square_dest)
        raw.append(a)
        projected.append(b)
    middle = [[formula.new() for _ in range(n)] for _ in range(2)]
    target = [1 if target_x >> i & 1 else -1 for i in range(n)]
    s3_link_factored(formula, projected[0], projected[1], middle[0], table, square_dest)
    s3_link_factored(formula, middle[0], projected[2], middle[1], table, square_dest)
    s3_link_factored(formula, middle[1], projected[3], target, table, square_dest)
    return formula, raw, projected, middle


def target_fixture(kind):
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    if kind == "planted":
        points = []
        for mask in PLANTED_RAW:
            raw = curve.pointFromX(onb.fromCoords(mask))
            assert raw is not None
            point = curve.mul(raw, 4)
            assert point is not None
            points.append(point)
        target = None
        for point in points:
            target = curve.add(target, point)
        assert target is not None and curve.onCurve(target)
        return target, None
    source = json.loads(TARGETS[kind].read_text())
    target = tuple(map(int, source["public_target"]))
    assert curve.onCurve(target)
    return target, source["workload_id"]


def parse_model(output, nvars):
    if "s SATISFIABLE" not in output:
        return None
    values = {}
    for line in output.splitlines():
        if line.startswith("v "):
            for lit in map(int, line[2:].split()):
                if lit:
                    values[abs(lit)] = lit > 0
    assert len(values) == nvars
    return values


def coord(bits, values):
    return sum(1 << i for i, bit in enumerate(bits) if values[bit])


def verify_model(formula, raw, projected, middle, target, values):
    assert all(any(values[abs(lit)] == (lit > 0) for lit in row)
               for row in formula.clauses)
    assert all((sum(values[var] for var in row) & 1) == int(rhs)
               for row, rhs in formula.xors)
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    raw_coords = [coord(vector, values) for vector in raw]
    projected_coords = [coord(vector, values) for vector in projected]
    middle_coords = [coord(vector, values) for vector in middle]
    target_x = onb.toCoords(target[0])
    assert evaluate_s3(onb, *(onb.fromCoords(x) for x in
                              (projected_coords[0], projected_coords[1], middle_coords[0]))) == 0
    assert evaluate_s3(onb, *(onb.fromCoords(x) for x in
                              (middle_coords[0], projected_coords[2], middle_coords[1]))) == 0
    assert evaluate_s3(onb, *(onb.fromCoords(x) for x in
                              (middle_coords[1], projected_coords[3], target_x))) == 0
    points = []
    for mask, expected_x in zip(raw_coords, projected_coords):
        assert 0 < mask < 1 << 83 and mask.bit_count() <= 5
        raw_point = curve.pointFromX(onb.fromCoords(mask))
        if raw_point is None:
            return {"status": "REJECTED_IRRATIONAL_RAW_X", "raw_x_onb": raw_coords,
                    "projected_x_onb": projected_coords}
        point = curve.mul(raw_point, 4)
        if point is None or onb.toCoords(point[0]) != expected_x:
            return {"status": "REJECTED_PROJECTED_X", "raw_x_onb": raw_coords,
                    "projected_x_onb": projected_coords}
        points.append(point)
    for mask in range(16):
        acc = None
        for i, point in enumerate(points):
            acc = curve.add(acc, curve.neg(point) if mask >> i & 1 else point)
        if acc == target:
            return {"status": "VERIFIED_RELATION", "raw_x_onb": raw_coords,
                    "projected_x_onb": projected_coords, "sign_mask": mask}
    return {"status": "REJECTED_GROUP_RELATION", "raw_x_onb": raw_coords,
            "projected_x_onb": projected_coords}


def main(args):
    target, workload = target_fixture(args.kind)
    onb = field.Onb(83)
    target_x = onb.toCoords(target[0])
    started = time.perf_counter_ns()
    if args.variant == "exact":
        formula, raw, projected, middle = build_projected_sparse_chain(83, 5, target_x)
    else:
        formula, raw, projected, middle = relaxed_chain(83, target_x)
    if args.kind == "planted":
        for vector, mask in zip(raw, PLANTED_RAW):
            for i, bit in enumerate(vector):
                formula.clauses.append([bit if mask >> i & 1 else -bit])
    build_s = (time.perf_counter_ns() - started) / 1e9
    label = f"{args.kind}_{args.variant}"
    formula_path = HERE / f"{label}.xcnf"
    formula.write(formula_path)
    command = ["cryptominisat5", "--maxtime", str(args.solver_cap),
               "--verb", "1", "--printsol", "1", str(formula_path)]
    started = time.perf_counter_ns()
    try:
        child = subprocess.run(command, capture_output=True, text=True,
                               timeout=args.wall_cap, check=False)
        stdout, stderr, code, wall_timeout = child.stdout, child.stderr, child.returncode, False
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or b"").decode(errors="replace")
        stderr = (exc.stderr or b"").decode(errors="replace")
        code, wall_timeout = None, True
    solver_s = (time.perf_counter_ns() - started) / 1e9
    values = parse_model(stdout, formula.variables) if not wall_timeout else None
    check = verify_model(formula, raw, projected, middle, target, values) if values else None
    if check:
        status = check["status"]
    elif wall_timeout:
        status = "WALL_TIMEOUT"
    elif "s INDETERMINATE" in stdout:
        status = "INDETERMINATE"
    elif "s UNSATISFIABLE" in stdout:
        status = "UNSAT"
    else:
        status = "SOLVER_FAILURE"
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = {"proposal_id": "Q1515", "candidate_id": None, "run_id": None,
              "isogeny": "none", "kind": args.kind, "variant": args.variant,
              "workload_id": workload, "status": status, "model_check": check,
              "target_x_onb": target_x, "formula_sha256": sha(formula_path.read_bytes()),
              "variables": formula.variables, "cnf_clauses": len(formula.clauses),
              "xor_rows": len(formula.xors), "build_wall_seconds_exploratory": build_s,
              "solver_wall_seconds_exploratory": solver_s,
              "child_peak_rss_bytes_darwin": usage.ru_maxrss,
              "solver_cap_seconds": args.solver_cap, "wall_cap_seconds": args.wall_cap,
              "return_code": code, "command": command,
              "stdout_sha256": sha(stdout.encode()), "stderr_sha256": sha(stderr.encode())}
    (HERE / f"{label}.stdout.txt").write_text(stdout)
    (HERE / f"{label}.stderr.txt").write_text(stderr)
    (HERE / f"{label}.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: result[k] for k in ("kind", "variant", "status", "variables",
                                               "cnf_clauses", "xor_rows",
                                               "solver_wall_seconds_exploratory",
                                               "child_peak_rss_bytes_darwin")}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("planted", "selected", "holdout"))
    parser.add_argument("variant", choices=("exact", "relaxed"))
    parser.add_argument("--solver-cap", type=int, default=10)
    parser.add_argument("--wall-cap", type=int, default=25)
    main(parser.parse_args())
