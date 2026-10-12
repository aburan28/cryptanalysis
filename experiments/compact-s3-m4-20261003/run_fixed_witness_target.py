#!/usr/bin/env python3
"""Separate S3 search hardness from cofactor-preimage selection.

The n=53 raw target is selected using an independently found relation. This
is an oracle-assisted diagnostic, never an ordinary-query IC measurement.
The n=83 raw target comes from a planted control. Neither run receives leaf
or intermediate coordinates until a separate, post-run encoding control.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import resource
import subprocess
import tempfile
import time
from pathlib import Path

from chain_s3_factored import build_factored
from run_probe import HERE, curves, field, lift, parse_model, sha


def target_fixture(n):
    kind = "ordinary" if n == 53 else "planted"
    baseline_path = HERE / "runs" / f"n{n}_{kind}_frozen.json"
    baseline = json.loads(baseline_path.read_text())
    coset_path = HERE / "runs" / f"n{n}_{kind}_raw_preimages.json"
    coset = json.loads(coset_path.read_text())
    assert coset["stage_receipt_sha256"] == sha(baseline_path)
    if n == 53:
        witness_path = HERE / "runs/n53_ordinary_raw_pair_witness.json"
        witness = json.loads(witness_path.read_text())
        assert witness["preimage_coset_sha256"] == sha(coset_path)
        raw = tuple(map(int, witness["raw_target"]))
        x = witness["raw_target_x_coordinates"]
        onb = field.Onb(n)
        leaf_xs = [onb.toCoords(point[0]) for point in
                   (tuple(map(int, row)) for row in witness["raw_leaf_points"])]
        mids = witness["intermediate_x_coordinates"]
    else:
        witness_path = baseline_path
        raw = tuple(map(int, baseline["raw_target"]))
        onb = field.Onb(n)
        x = onb.toCoords(raw[0])
        leaf_xs = baseline["fixture"]["planted_leaf_x"]
        mids = baseline["fixture"]["planted_intermediate_x"]
    assert x == onb.toCoords(raw[0])
    assert x in coset["raw_target_x_coordinates"]
    assert len(leaf_xs) == 4 and len(mids) == 2
    return baseline_path, baseline, coset_path, coset, witness_path, raw, x, leaf_xs, mids


def lock_and_verify(formula, leaves, intermediates, leaf_xs, mids,
                    onb, curve, raw, public, cofactor):
    with tempfile.TemporaryDirectory() as directory:
        for row, value in zip(leaves + intermediates, leaf_xs + mids):
            formula.clauses.extend(([var if value >> bit & 1 else -var]
                                    for bit, var in enumerate(row)))
        locked = Path(directory) / "locked.xcnf"
        formula.write(locked)
        start = time.perf_counter()
        result = subprocess.run(
            ["cryptominisat5", "--verb", "0", "--threads", "1", str(locked)],
            capture_output=True, text=True, timeout=30)
        wall = time.perf_counter() - start
        assert result.returncode == 10, result.stdout[-1000:]
        values = parse_model(result.stdout)
        assert values is not None
        coords, relation, status = lift(
            onb, curve, leaves, values, raw, public, cofactor)
        assert coords == leaf_xs
        assert status == "verified_four_point_relation"
        assert relation is not None
        return {"status": "locked_sat_verified_relation",
                "solver_wall_seconds": wall,
                "locked_formula_sha256": sha(locked),
                "relation": relation}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(53, 83), required=True)
    parser.add_argument("--max-seconds", type=int, default=120)
    parser.add_argument("--max-conflicts", type=int, default=1_000_000)
    args = parser.parse_args()
    n = args.n
    stem = ("n53_ordinary_known_preimage_fixed" if n == 53
            else "n83_planted_raw_target_fixed")
    output = HERE / "runs" / f"{stem}.json"
    raw_formula = HERE / "runs" / f"{stem}.xcnf"
    archive = HERE / "runs" / f"{stem}.xcnf.gz"
    stdout_path = HERE / "runs" / f"{stem}.stdout.txt"
    stderr_path = HERE / "runs" / f"{stem}.stderr.txt"
    assert not any(path.exists() for path in
                   (output, raw_formula, archive, stdout_path, stderr_path))
    (baseline_path, baseline, coset_path, coset, witness_path,
     raw, target_x, leaf_xs, mids) = target_fixture(n)
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    public = tuple(map(int, baseline["public_subgroup_target"]))
    cofactor = int(coset["cofactor"])
    assert curve.mul(raw, cofactor) == public
    runtime_info = HERE / "fixed_sage_runtime_info.json"
    assert json.loads(runtime_info.read_text())["status"] == "verified"

    build_start = time.perf_counter()
    formula, leaves, intermediates = build_factored(
        n, {53: 3, 83: 4}[n], target_x)
    initial_clauses = len(formula.clauses)
    formula.write(raw_formula)
    build_seconds = time.perf_counter() - build_start
    formula_sha = sha(raw_formula)
    formula_bytes = raw_formula.stat().st_size
    command = ["cryptominisat5", "--verb", "1", "--threads", "1",
               "--maxtime", str(args.max_seconds), "--maxconfl",
               str(args.max_conflicts), str(raw_formula)]
    start = time.perf_counter()
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=args.max_seconds + 2)
        stdout, stderr, code = result.stdout, result.stderr, result.returncode
        status = ("sat" if code == 10 else "unsat" if code == 20
                  else "censored")
    except subprocess.TimeoutExpired as error:
        stdout = (error.stdout or b"").decode(errors="replace")
        stderr = (error.stderr or b"").decode(errors="replace")
        code, status = None, "external_timeout"
    solver_seconds = time.perf_counter() - start
    stdout_path.write_text(stdout)
    stderr_path.write_text(stderr)
    matches = re.findall(r"conflicts\s*[:=]\s*([0-9]+)", stdout,
                         flags=re.IGNORECASE)
    model = parse_model(stdout)
    relation = None
    lift_status = None
    if model is not None:
        _, relation, lift_status = lift(
            onb, curve, leaves, model, raw, public, cofactor)
    main_peak_rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    control = lock_and_verify(formula, leaves, intermediates, leaf_xs, mids,
                              onb, curve, raw, public, cofactor)
    with archive.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream,
                           mtime=0, compresslevel=9) as zipped:
            zipped.write(raw_formula.read_bytes())
    assert hashlib.sha256(gzip.decompress(archive.read_bytes())).hexdigest() == formula_sha
    receipt = {
        "kind": "fixed_witness_target_s3_search_hardness_diagnostic",
        "proposal_id": {53: "Q1313", 83: "Q1314"}[n],
        "candidate_id": None, "workload_id": None, "run_id": None,
        "comparison_workload_id": baseline["workload_id"],
        "oracle_assisted_raw_target_selection": n == 53,
        "is_natural_relation_yield_measurement": False,
        "curve_id": baseline["curve_id"], "isogeny": "none", "n": n,
        "factor_base_actual_B": baseline["factor_base_actual_B"],
        "factor_base_folded_columns": baseline["factor_base_folded_columns"],
        "factor_base_enumerated_set_sha256": baseline[
            "factor_base_enumerated_set_sha256"],
        "raw_target": [str(v) for v in raw],
        "public_target": [str(v) for v in public],
        "raw_target_x_coordinates": target_x,
        "raw_preimage_index": coset["raw_target_x_coordinates"].index(target_x),
        "target_pdp_wall_seconds": build_seconds + solver_seconds,
        "formula_build_seconds": build_seconds,
        "solver_wall_seconds": solver_seconds,
        "status": status, "return_code": code,
        "solver_conflicts_reported": int(matches[-1]) if matches else None,
        "lift_status": lift_status,
        "verified_relation": relation,
        "observed_verified_relation_count": int(relation is not None),
        "natural_relation_yield_estimate": None,
        "field_operations": None,
        "complete_solve_work_log2": None,
        "formula_variables": formula.variables,
        "formula_cnf_clauses": initial_clauses,
        "formula_xor_rows": len(formula.xors),
        "formula_and_gates": len(formula.and_cache),
        "xcnf_sha256": formula_sha, "xcnf_bytes": formula_bytes,
        "solver_command": command,
        "max_seconds": args.max_seconds,
        "max_conflicts": args.max_conflicts,
        "peak_child_rss_raw_before_control": main_peak_rss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "locked_control": control,
        "baseline_receipt_sha256": sha(baseline_path),
        "coset_receipt_sha256": sha(coset_path),
        "witness_receipt_sha256": sha(witness_path),
        "runtime_info_sha256": sha(runtime_info),
        "core_source_sha256": sha(HERE / "chain_s3.py"),
        "factored_source_sha256": sha(HERE / "chain_s3_factored.py"),
        "runner_source_sha256": sha(Path(__file__)),
        "solver_binary_sha256": sha(Path("/opt/homebrew/bin/cryptominisat5")),
        "stdout_sha256": sha(stdout_path),
        "stderr_sha256": sha(stderr_path),
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"n": n, "status": status,
                      "solver_conflicts": receipt["solver_conflicts_reported"],
                      "verified_relation": relation is not None,
                      "locked_control": control["status"],
                      "target_pdp_wall_seconds": receipt["target_pdp_wall_seconds"]}))


if __name__ == "__main__":
    main()
