#!/usr/bin/env python3
"""Bounded S3 solve over the full raw cofactor preimage coset of one target."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import resource
import subprocess
import time
from pathlib import Path

from chain_s3_multitarget import build_multitarget, decode_choice
from run_probe import HERE, curves, field, lift, parse_model, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(53, 83), required=True)
    parser.add_argument("--kind", choices=("planted", "ordinary"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists()
    baseline_path = HERE / "runs" / f"n{args.n}_{args.kind}_frozen.json"
    coset_path = HERE / "runs" / f"n{args.n}_{args.kind}_raw_preimages.json"
    protocol_path = HERE / "protocol.json"
    baseline = json.loads(baseline_path.read_text())
    coset = json.loads(coset_path.read_text())
    profile = next(row for row in json.loads(protocol_path.read_text())["profiles"]
                   if row["field"]["n"] == args.n)
    assert baseline["protocol_sha256"] == sha(protocol_path)
    assert baseline["curve_id"] == coset["curve_id"] == profile["curve"][
        "curve_id"]
    assert baseline["workload_kind"] == coset["workload_kind"] == args.kind
    assert coset["stage_receipt_sha256"] == sha(baseline_path)
    assert coset["raw_target_preimage_count"] == profile["curve"]["cofactor"]
    assert baseline["factor_base_enumerated_set_sha256"] == profile[
        "factor_base"]["enumerated_set_sha256"]
    xs = coset["raw_target_x_coordinates"]
    raw_points = [tuple(int(v) for v in point)
                  for point in coset["raw_target_points"]]
    assert len(xs) == len(raw_points)
    onb = field.Onb(args.n)
    curve = curves.Curve(onb)
    assert all(onb.toCoords(point[0]) == x for point, x in zip(raw_points, xs))
    public = tuple(int(v) for v in baseline["public_subgroup_target"])
    cofactor = int(coset["cofactor"])
    assert all(curve.mul(point, cofactor) == public for point in raw_points)

    max_seconds = profile["point_decomposition"][
        "target_pdp_wall_limit_seconds"]
    max_conflicts = profile["point_decomposition"][
        "max_conflicts_per_attempt"]
    max_models = profile["point_decomposition"]["max_invalid_models"]
    formula_path = args.out.with_suffix(".xcnf")
    assert not formula_path.exists()
    began = time.perf_counter()
    formula, leaves, _, target, selector = build_multitarget(
        args.n, profile["factor_base"]["normal_basis_weight_bound"], xs)
    build_seconds = time.perf_counter() - began
    initial_clauses = len(formula.clauses)
    deadline = began + max_seconds
    attempts = []
    relation = None
    chosen_preimage_index = None
    for index in range(max_models):
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            break
        attempt_formula_path = (formula_path if index == 0 else
                                args.out.with_suffix(f".attempt{index}.xcnf"))
        formula.write(attempt_formula_path)
        command = ["cryptominisat5", "--verb", "1", "--threads", "1",
                   "--maxtime", str(max(1, int(remaining))), "--maxconfl",
                   str(max_conflicts), str(attempt_formula_path)]
        start = time.perf_counter()
        try:
            result = subprocess.run(command, capture_output=True, text=True,
                                    timeout=remaining)
            stdout, stderr, code = (result.stdout, result.stderr,
                                    result.returncode)
            status = ("sat" if code == 10 else "unsat" if code == 20
                      else "censored")
        except subprocess.TimeoutExpired as error:
            stdout = (error.stdout or b"").decode(errors="replace")
            stderr = (error.stderr or b"").decode(errors="replace")
            code, status = None, "external_timeout"
        elapsed = time.perf_counter() - start
        stdout_path = args.out.with_suffix(f".attempt{index}.stdout.txt")
        stderr_path = args.out.with_suffix(f".attempt{index}.stderr.txt")
        stdout_path.write_text(stdout)
        stderr_path.write_text(stderr)
        matches = re.findall(r"conflicts\s*[:=]\s*([0-9]+)", stdout,
                             flags=re.IGNORECASE)
        attempt = {"index": index, "status": status, "return_code": code,
                   "solver_wall_seconds": elapsed,
                   "formula_cnf_clauses": len(formula.clauses),
                   "xcnf_sha256": sha(attempt_formula_path),
                   "xcnf_bytes": attempt_formula_path.stat().st_size,
                   "solver_conflicts_reported": int(matches[-1]) if matches else None,
                   "solver_stdout_sha256": hashlib.sha256(
                       stdout.encode()).hexdigest(),
                   "solver_stderr_sha256": hashlib.sha256(
                       stderr.encode()).hexdigest(),
                   "solver_command": command}
        values = parse_model(stdout)
        if values is not None:
            choice = decode_choice(selector, values)
            assert choice < len(xs)
            chosen_x = sum(1 << position
                           for position, var in enumerate(target)
                           if values.get(var, False))
            assert chosen_x == xs[choice]
            coords, relation, lift_status = lift(
                onb, curve, leaves, values, raw_points[choice], public,
                cofactor)
            attempt["chosen_preimage_index"] = choice
            attempt["chosen_preimage_x"] = chosen_x
            attempt["leaf_x_coordinates"] = coords
            attempt["lift_status"] = lift_status
            if relation is None:
                # Preserve other raw-target choices for the same leaves.
                formula.clauses.append([
                    -var if values.get(var, False) else var
                    for row in leaves for var in row] +
                    [-var if values.get(var, False) else var
                     for var in selector])
            else:
                chosen_preimage_index = choice
        attempts.append(attempt)
        if relation is not None or status != "sat":
            break
    receipt = {
        "kind": "full_cofactor_preimage_compact_s3_stage_probe",
        "proposal_id": {53: "Q1306", 83: "Q1307"}[args.n],
        "candidate_id": None,
        "run_id": None,
        "workload_id": baseline["workload_id"],
        "curve_id": baseline["curve_id"],
        "isogeny": "none",
        "n": args.n,
        "workload_kind": args.kind,
        "public_target": list(baseline["public_subgroup_target"]),
        "matched_baseline_receipt_sha256": sha(baseline_path),
        "protocol_sha256": sha(protocol_path),
        "factor_base_actual_B": baseline["factor_base_actual_B"],
        "factor_base_folded_columns": baseline[
            "factor_base_folded_columns"],
        "factor_base_enumerated_set_sha256": baseline[
            "factor_base_enumerated_set_sha256"],
        "cofactor": cofactor,
        "raw_preimage_count": len(xs),
        "raw_preimage_x_sha256": coset["raw_target_x_sha256"],
        "raw_preimage_receipt_sha256": sha(coset_path),
        "chosen_preimage_index": chosen_preimage_index,
        "formula_variables": formula.variables,
        "formula_cnf_clauses": initial_clauses,
        "formula_xor_rows": len(formula.xors),
        "formula_and_gates": len(formula.and_cache),
        "formula_build_seconds": build_seconds,
        "target_pdp_wall_seconds": time.perf_counter() - began,
        "attempts": attempts,
        "verified_relation": relation,
        "observed_verified_relation_count": int(relation is not None),
        "natural_relation_yield_estimate": None,
        "peak_child_rss_raw": resource.getrusage(
            resource.RUSAGE_CHILDREN).ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "xcnf_sha256": sha(formula_path) if formula_path.exists() else None,
        "xcnf_bytes": formula_path.stat().st_size if formula_path.exists() else None,
        "multitarget_source_sha256": sha(HERE / "chain_s3_multitarget.py"),
        "factored_source_sha256": sha(HERE / "chain_s3_factored.py"),
        "core_source_sha256": sha(HERE / "chain_s3.py"),
        "runner_source_sha256": sha(Path(__file__)),
        "complete_solve_work_log2": None,
    }
    args.out.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"n": args.n, "kind": args.kind,
                      "status": attempts[-1]["status"] if attempts else "no_attempt",
                      "verified_relation": relation is not None,
                      "preimages": len(xs),
                      "formula_and_gates": receipt["formula_and_gates"],
                      "target_pdp_wall_seconds":
                      receipt["target_pdp_wall_seconds"]}))


if __name__ == "__main__":
    main()
