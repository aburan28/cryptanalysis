#!/usr/bin/env python3
"""Bounded planted or ordinary four-point S3-chain decomposition probe."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import random
import re
import resource
import subprocess
import sys
import time
from pathlib import Path

from chain_s3 import build, evaluate_s3

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
import curves  # noqa: E402
import field  # noqa: E402


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def curve_record(n):
    paths = list((ROOT / "experiments/koblitz-pair-claw-20260929/candidates").glob(
        f"IC1N{n}Ckb1fb*PDP4qtableRCdirectLAnoneTDdirectISO0h*.json"))
    assert paths, n
    # The n83 holdout manifest is the exact contemporary curve record.
    selected = next((p for p in paths if n != 83 or "h49b47d79e9e3" in p.name),
                    paths[0])
    record = json.loads(selected.read_text())
    assert record["field"]["n"] == n
    assert int(record["curve"]["cofactor"]) * int(
        record["curve"]["subgroup_order"]) == int(record["curve"]["order"])
    assert record["isogeny"] == "none"
    return selected, record


def base_record(n, weight, candidate):
    path = HERE / "bases" / f"n{n}_weight{weight}_orbits.json.gz"
    with gzip.open(path, "rt") as stream:
        base = json.load(stream)
    assert base["field"] == candidate["field"]
    assert base["curve"] == candidate["curve"]
    assert base["isogeny"] == "none"
    fb = base["factor_base"]
    assert fb["normal_basis_weight_bound"] == weight
    assert fb["cofactor_projection"] == candidate["curve"]["cofactor"]
    assert fb["actual_usable_points_B_before_folding"] > 0
    assert fb["signed_frobenius_columns"] > 0
    return path, fb


def random_sparse_point(onb, curve, weight, rng):
    while True:
        size = rng.randrange(1, weight + 1)
        positions = rng.sample(range(onb.m), size)
        coordinates = sum(1 << i for i in positions)
        point = curve.pointFromX(onb.fromCoords(coordinates))
        if point is not None:
            return point


def make_target(onb, curve, generator, order, cofactor, weight, kind, seed):
    rng = random.Random(seed)
    if kind == "planted":
        leaves = [random_sparse_point(onb, curve, weight, rng) for _ in range(4)]
        partial = curve.add(leaves[0], leaves[1])
        triple = curve.add(partial, leaves[2])
        raw = curve.add(triple, leaves[3])
        if raw is None or partial is None or triple is None:
            return make_target(onb, curve, generator, order, cofactor, weight, kind,
                               seed + 1)
        assert all(evaluate_s3(onb, *xs) == 0 for xs in (
            (leaves[0][0], leaves[1][0], partial[0]),
            (partial[0], leaves[2][0], triple[0]),
            (triple[0], leaves[3][0], raw[0])))
        public = curve.mul(raw, cofactor)
        assert public is not None and curve.mul(public, order) is None
        return raw, public, {"planted_leaf_x": [onb.toCoords(p[0])
                                               for p in leaves],
                             "planted_intermediate_x": [onb.toCoords(partial[0]),
                                                        onb.toCoords(triple[0])]}
    scalar = rng.randrange(1, order)
    public = curve.mul(generator, scalar)
    raw = curve.mul(public, pow(cofactor, -1, order))
    assert raw is not None and curve.mul(raw, cofactor) == public
    return raw, public, {"fixture_scalar": str(scalar)}


def parse_model(stdout):
    if "s SATISFIABLE" not in stdout:
        return None
    values = {}
    for line in stdout.splitlines():
        if line.startswith("v "):
            for value in line[2:].split():
                lit = int(value)
                if lit:
                    values[abs(lit)] = lit > 0
    return values


def lift(onb, curve, leaf_variables, values, raw, public, cofactor):
    coords = [sum(1 << i for i, var in enumerate(row) if values.get(var, False))
              for row in leaf_variables]
    points = [curve.pointFromX(onb.fromCoords(value)) for value in coords]
    if any(point is None for point in points):
        return coords, None, "nonrational_x"
    for signs in itertools.product((1, -1), repeat=4):
        total = None
        for point, sign in zip(points, signs):
            total = curve.add(total, point if sign == 1 else curve.neg(point))
        if total == raw:
            projected = [curve.mul(point, cofactor) for point in points]
            if curve.mul(total, cofactor) != public:
                raise AssertionError("cofactor projection mismatch")
            if any(p is None for p in projected):
                return coords, None, "projected_identity"
            return coords, {
                "leaf_x_coordinates": coords,
                "signs": signs,
                "leaf_points": [[str(v) for v in point] for point in points],
                "projected_points": [[str(v) for v in point]
                                     for point in projected],
                "raw_sum": [str(v) for v in total],
                "public_target": [str(v) for v in public],
            }, "verified_four_point_relation"
    return coords, None, "no_sign_lift"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(53, 83), required=True)
    parser.add_argument("--kind", choices=("planted", "ordinary"), required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--max-seconds", type=int, default=30)
    parser.add_argument("--max-conflicts", type=int, default=200000)
    parser.add_argument("--max-models", type=int, default=3)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists()
    weight = {53: 3, 83: 4}[args.n]
    manifest_path, candidate = curve_record(args.n)
    base_path, fb = base_record(args.n, weight, candidate)
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    profile = next(row for row in protocol["profiles"]
                   if row["field"]["n"] == args.n)
    assert profile["curve"] == candidate["curve"]
    assert profile["field"] == candidate["field"]
    assert profile["factor_base"]["enumerated_set_sha256"] == fb[
        "enumerated_set_sha256"]
    assert profile["factor_base_archive_sha256"] == sha(base_path)
    assert args.seed == (profile["planted_control_seed"] if args.kind == "planted"
                         else profile["ordinary_workload"]["seed"])
    pdp = profile["point_decomposition"]
    assert args.max_seconds == pdp["target_pdp_wall_limit_seconds"]
    assert args.max_conflicts == pdp["max_conflicts_per_attempt"]
    assert args.max_models == pdp["max_invalid_models"]
    onb = field.Onb(args.n)
    curve = curves.Curve(onb)
    generator = tuple(candidate["curve"]["generator"])
    order = int(candidate["curve"]["subgroup_order"])
    cofactor = int(candidate["curve"]["cofactor"])
    assert curve.onCurve(generator) and curve.mul(generator, order) is None
    raw, public, fixture = make_target(onb, curve, generator, order, cofactor,
                                       weight, args.kind, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    formula_path = args.out.with_suffix(".xcnf")
    assert not formula_path.exists()
    began = time.perf_counter()
    formula, leaves, intermediates = build(args.n, weight,
                                           onb.toCoords(raw[0]))
    build_seconds = time.perf_counter() - began
    attempts = []
    relation = None
    deadline = began + args.max_seconds
    for index in range(args.max_models):
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            break
        formula.write(formula_path)
        command = ["cryptominisat5", "--verb", "1", "--threads", "1",
                   "--maxtime", str(max(1, int(remaining))), "--maxconfl",
                   str(args.max_conflicts), str(formula_path)]
        start = time.perf_counter()
        try:
            result = subprocess.run(command, capture_output=True, text=True,
                                    timeout=remaining)
            output, error_output, code = (result.stdout, result.stderr,
                                          result.returncode)
            status = ("sat" if code == 10 else "unsat" if code == 20
                      else "censored")
        except subprocess.TimeoutExpired as error:
            output = (error.stdout or b"").decode(errors="replace")
            error_output = (error.stderr or b"").decode(errors="replace")
            code, status = None, "external_timeout"
        elapsed = time.perf_counter() - start
        stdout_path = args.out.with_suffix(f".attempt{index}.stdout.txt")
        stderr_path = args.out.with_suffix(f".attempt{index}.stderr.txt")
        stdout_path.write_text(output)
        stderr_path.write_text(error_output)
        conflict_match = re.findall(r"conflicts\s*[:=]\s*([0-9]+)",
                                    output, flags=re.IGNORECASE)
        attempt = {"index": index, "status": status, "return_code": code,
                   "solver_wall_seconds": elapsed,
                   "solver_stdout_sha256": hashlib.sha256(
                       output.encode()).hexdigest(),
                   "solver_stderr_sha256": hashlib.sha256(
                       error_output.encode()).hexdigest(),
                   "solver_conflicts_reported": (int(conflict_match[-1])
                                                 if conflict_match else None),
                   "solver_command": command}
        values = parse_model(output)
        if values is not None:
            coords, relation, lift_status = lift(onb, curve, leaves, values,
                                                 raw, public, cofactor)
            attempt["lift_status"] = lift_status
            attempt["leaf_x_coordinates"] = coords
            if relation is None:
                formula.clauses.append([
                    -var if values.get(var, False) else var
                    for row in leaves for var in row])
        attempts.append(attempt)
        if relation is not None or status != "sat":
            break
    result = {
        "kind": "compact_four_summand_s3_chain_stage_probe",
        "proposal_id": profile["proposal_id"],
        "candidate_id": None,
        "workload_id": (profile["ordinary_workload_id"]
                        if args.kind == "ordinary" else None),
        "run_id": None,
        "protocol_sha256": sha(protocol_path),
        "curve_id": candidate["curve"]["curve_id"],
        "isogeny": "none", "field_degree_n": args.n,
        "factor_base_policy": f"normal_basis_x_weight_at_most_{weight}_cofactor_{cofactor}",
        "factor_base_actual_B": fb[
            "actual_usable_points_B_before_folding"],
        "factor_base_folded_columns": fb["signed_frobenius_columns"],
        "factor_base_enumerated_set_sha256": fb["enumerated_set_sha256"],
        "factor_base_archive_sha256": sha(base_path),
        "workload_kind": args.kind, "seed": args.seed,
        "raw_target": [str(v) for v in raw],
        "public_subgroup_target": [str(v) for v in public],
        "fixture": fixture,
        "formula_variables": formula.variables,
        "formula_cnf_clauses": len(formula.clauses),
        "formula_xor_rows": len(formula.xors),
        "formula_and_gates": len(formula.and_cache),
        "formula_build_seconds": build_seconds,
        "target_pdp_wall_seconds": time.perf_counter() - began,
        "peak_child_rss_raw": resource.getrusage(
            resource.RUSAGE_CHILDREN).ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "attempts": attempts,
        "verified_relation": relation,
        "natural_relation_yield": (1 if relation and args.kind == "ordinary" else 0),
        "xcnf_sha256": sha(formula_path) if formula_path.exists() else None,
        "xcnf_bytes": formula_path.stat().st_size if formula_path.exists() else None,
        "solver_source_sha256": sha(HERE / "chain_s3.py"),
        "runner_source_sha256": sha(Path(__file__)),
        "curve_manifest_sha256": sha(manifest_path),
        "solver_command_budget_seconds": args.max_seconds,
        "solver_command_budget_conflicts_per_attempt": args.max_conflicts,
        "measured_complete_solve_operations_log2": None,
        "n131_complete_work_projection_log2": None,
    }
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"n": args.n, "kind": args.kind,
                      "status": attempts[-1]["status"] if attempts else "no_attempt",
                      "verified_relation": bool(relation),
                      "pdp_wall_seconds": result["target_pdp_wall_seconds"]}))


if __name__ == "__main__":
    main()
