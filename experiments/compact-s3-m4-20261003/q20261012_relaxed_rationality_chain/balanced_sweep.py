#!/usr/bin/env python3
"""Bounded weight sweep of the existing balanced raw-preimage S3 solver."""
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
from chain_s3_balanced_multitarget import build_balanced  # noqa: E402
from run import PLANTED_RAW, TARGETS, parse_model, coord  # noqa: E402
import curves  # noqa: E402
import field  # noqa: E402


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def input_data(kind):
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    if kind == "planted":
        raw_points = [curve.pointFromX(onb.fromCoords(mask)) for mask in PLANTED_RAW]
        assert all(point is not None for point in raw_points)
        raw_sum = None
        for point in raw_points:
            raw_sum = curve.add(raw_sum, point)
        assert raw_sum is not None
        target = curve.mul(raw_sum, 4)
        assert target is not None
        return target, [onb.toCoords(raw_sum[0])], None
    source = json.loads(TARGETS[kind].read_text())
    target = tuple(map(int, source["public_target"]))
    assert curve.onCurve(target)
    return target, source["raw_preimage_x_coordinates"], source["workload_id"]


def verify(formula, leaves, target, weight, model):
    assert all(any(model[abs(lit)] == (lit > 0) for lit in row)
               for row in formula.clauses)
    assert all((sum(model[var] for var in row) & 1) == int(rhs)
               for row, rhs in formula.xors)
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    raw_x = [coord(bits, model) for bits in leaves]
    assert all(0 < x < 1 << 83 and x.bit_count() <= weight for x in raw_x)
    raw_points = [curve.pointFromX(onb.fromCoords(x)) for x in raw_x]
    if any(point is None for point in raw_points):
        return {"status": "REJECTED_IRRATIONAL_RAW_X", "raw_x_onb": raw_x}
    projected = [curve.mul(point, 4) for point in raw_points]
    if any(point is None for point in projected):
        return {"status": "REJECTED_IDENTITY_PROJECTION", "raw_x_onb": raw_x}
    order = 2417851639230796216685689
    assert all(curve.mul(point, order) is None for point in projected)
    for mask in range(16):
        acc = None
        for i, point in enumerate(projected):
            acc = curve.add(acc, curve.neg(point) if mask >> i & 1 else point)
        if acc == target:
            return {"status": "VERIFIED_RELATION", "raw_x_onb": raw_x,
                    "sign_mask": mask,
                    "projected_points": [[int(x), int(y)] for x, y in projected]}
    return {"status": "REJECTED_GROUP_RELATION", "raw_x_onb": raw_x}


def main(args):
    target, preimages, workload = input_data(args.kind)
    started = time.perf_counter_ns()
    formula, leaves, mids, chosen, selector = build_balanced(83, args.weight, preimages)
    if args.kind == "planted":
        for bits, mask in zip(leaves, PLANTED_RAW):
            for i, bit in enumerate(bits):
                formula.clauses.append([bit if mask >> i & 1 else -bit])
        if args.pin_middle:
            onb = field.Onb(83)
            curve = curves.Curve(onb)
            points = [curve.pointFromX(onb.fromCoords(mask)) for mask in PLANTED_RAW]
            for vector, pair in zip(mids, ((0, 1), (2, 3))):
                middle = curve.add(points[pair[0]], points[pair[1]])
                assert middle is not None
                x = onb.toCoords(middle[0])
                for i, bit in enumerate(vector):
                    formula.clauses.append([bit if x >> i & 1 else -bit])
    build_s = (time.perf_counter_ns() - started) / 1e9
    label = f"{args.kind}_w{args.weight}" + ("_midpin" if args.pin_middle else "")
    path = HERE / f"{label}.xcnf"
    formula.write(path)
    command = ["cryptominisat5", "--maxtime", str(args.solver_cap),
               "--verb", "1", "--printsol", "1", str(path)]
    started = time.perf_counter_ns()
    try:
        child = subprocess.run(command, capture_output=True, text=True,
                               timeout=args.wall_cap, check=False)
        stdout, stderr, code, timeout = child.stdout, child.stderr, child.returncode, False
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or b"").decode(errors="replace")
        stderr = (exc.stderr or b"").decode(errors="replace")
        code, timeout = None, True
    elapsed = (time.perf_counter_ns() - started) / 1e9
    model = parse_model(stdout, formula.variables) if not timeout else None
    check = verify(formula, leaves, target, args.weight, model) if model else None
    if check:
        status = check["status"]
    elif timeout:
        status = "WALL_TIMEOUT"
    elif "s INDETERMINATE" in stdout:
        status = "INDETERMINATE"
    elif "s UNSATISFIABLE" in stdout:
        status = "UNSAT"
    else:
        status = "SOLVER_FAILURE"
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt = {"proposal_id": "Q1515", "candidate_id": None, "run_id": None,
               "isogeny": "none", "kind": args.kind, "weight_bound": args.weight,
               "middle_roots_pinned": args.pin_middle,
               "workload_id": workload, "status": status, "model_check": check,
               "raw_target_preimage_x_onb": preimages,
               "formula_sha256": sha(path.read_bytes()),
               "variables": formula.variables, "cnf_clauses": len(formula.clauses),
               "xor_rows": len(formula.xors), "build_wall_seconds_exploratory": build_s,
               "solver_wall_seconds_exploratory": elapsed,
               "child_peak_rss_bytes_darwin": usage.ru_maxrss,
               "solver_cap_seconds": args.solver_cap, "wall_cap_seconds": args.wall_cap,
               "return_code": code, "command": command,
               "stdout_sha256": sha(stdout.encode()), "stderr_sha256": sha(stderr.encode())}
    (HERE / f"{label}.stdout.txt").write_text(stdout)
    (HERE / f"{label}.stderr.txt").write_text(stderr)
    (HERE / f"{label}.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: receipt[k] for k in ("kind", "weight_bound", "status",
                                                 "variables", "cnf_clauses", "xor_rows",
                                                 "solver_wall_seconds_exploratory")}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("planted", "selected", "holdout"))
    parser.add_argument("--weight", type=int, choices=(5, 6, 7), required=True)
    parser.add_argument("--solver-cap", type=int, default=10)
    parser.add_argument("--wall-cap", type=int, default=25)
    parser.add_argument("--pin-middle", action="store_true")
    main(parser.parse_args())
