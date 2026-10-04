#!/usr/bin/env python3
"""Bounded public-target S3 search over the cofactor-four sparse-x base."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import resource
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from chain_s3_projected_sparse import build_projected_sparse_chain
from run_base_orbit_probe import read_inputs, witness_points
from run_probe import HERE, curves, field, lift, parse_model, sha


def coordinates(bits, model):
    return sum(1 << position for position, bit in enumerate(bits)
               if model.get(bit, False))


def check_model(raw_leaves, projected_leaves, model, onb, curve, order,
                keys, public):
    raw_x = [coordinates(bits, model) for bits in raw_leaves]
    projected_x = [coordinates(bits, model) for bits in projected_leaves]
    key_set = set(keys)
    for raw, projected in zip(raw_x, projected_x):
        assert 0 < raw < 1 << onb.m and raw.bit_count() <= 4
        point = curve.pointFromX(onb.fromCoords(raw))
        assert point is not None
        subgroup = curve.mul(point, 4)
        assert subgroup is not None
        assert onb.toCoords(subgroup[0]) == projected
        assert curve.mul(subgroup, order) is None
        orbit = [onb.toCoords(onb.frob(subgroup[0], shift))
                 for shift in range(onb.m)]
        assert min(orbit) in key_set
    leaf_x, relation, lift_status = lift(
        onb, curve, projected_leaves, model, public, public, 1)
    assert leaf_x == projected_x
    return raw_x, projected_x, relation, lift_status


def lock_control(formula, raw_leaves, projected_leaves, mids, baseline,
                 onb, curve, order, keys, public, witness_path, points):
    assert points is not None and witness_path is not None
    raw_values = baseline["fixture"]["planted_leaf_x"]
    assert len(raw_values) == len(points) == 4
    projected_values = [onb.toCoords(point[0]) for point in points]
    first = curve.add(points[0], points[1])
    second = curve.add(first, points[2])
    assert first is not None and second is not None
    assert curve.add(second, points[3]) == public
    for variables, value in zip(raw_leaves, raw_values):
        formula.clauses.extend(([
            bit if value >> position & 1 else -bit]
            for position, bit in enumerate(variables)))
    for variables, value in zip(projected_leaves, projected_values):
        formula.clauses.extend(([
            bit if value >> position & 1 else -bit]
            for position, bit in enumerate(variables)))
    for variables, point in zip(mids, (first, second)):
        value = onb.toCoords(point[0])
        formula.clauses.extend(([
            bit if value >> position & 1 else -bit]
            for position, bit in enumerate(variables)))
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "locked.xcnf"
        formula.write(path)
        started = time.perf_counter()
        result = subprocess.run(["cryptominisat5", "--verb", "0",
                                 "--threads", "1", str(path)],
                                capture_output=True, text=True, timeout=60)
        wall = time.perf_counter() - started
        assert result.returncode == 10, result.stdout[-1000:]
        model = parse_model(result.stdout)
        assert model is not None
        raw_x, projected_x, relation, status = check_model(
            raw_leaves, projected_leaves, model, onb, curve, order,
            keys, public)
        assert raw_x == raw_values
        assert projected_x == projected_values
        assert status == "verified_four_point_relation"
        assert relation is not None
        return {
            "status": "locked_sat_verified_public_relation",
            "raw_x_coordinates": raw_x,
            "projected_x_coordinates": projected_x,
            "solver_wall_seconds": wall,
            "locked_formula_sha256": sha(path),
            "witness_receipt_sha256": sha(witness_path),
            "relation": relation,
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("ordinary", "planted"),
                        required=True)
    parser.add_argument("--max-seconds", type=int, default=120)
    parser.add_argument("--max-conflicts", type=int, default=1_000_000)
    args = parser.parse_args()
    n, weight, kind = 83, 4, args.kind
    stem = f"n{n}_{kind}_projected_sparse"
    output = HERE / "runs" / f"{stem}.json"
    formula_path = HERE / "runs" / f"{stem}.xcnf"
    archive_formula = HERE / "runs" / f"{stem}.xcnf.gz"
    stdout_path = HERE / "runs" / f"{stem}.stdout.txt"
    stderr_path = HERE / "runs" / f"{stem}.stderr.txt"
    assert not any(path.exists() for path in (
        output, formula_path, archive_formula, stdout_path, stderr_path))
    runtime_path = HERE / "projected_sparse_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    setup_started = time.perf_counter()
    baseline_path, baseline, archive_path, archive, keys = read_inputs(
        n, kind)
    assert int(archive["curve"]["cofactor"]) == 4
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    public = tuple(map(int, baseline["public_subgroup_target"]))
    order = int(archive["curve"]["subgroup_order"])
    assert curve.onCurve(public) and curve.mul(public, order) is None
    setup_seconds = time.perf_counter() - setup_started

    started = time.perf_counter()
    target_x = onb.toCoords(public[0])
    formula, raw_leaves, projected_leaves, mids = (
        build_projected_sparse_chain(n, weight, target_x))
    build_seconds = time.perf_counter() - started
    formula_stats = {"variables": formula.variables,
                     "cnf_clauses": len(formula.clauses),
                     "xor_rows": len(formula.xors),
                     "and_gates": len(formula.and_cache),
                     "cnf_literal_occurrences": sum(
                         len(row) for row in formula.clauses),
                     "xor_literal_occurrences": sum(
                         len(row) for row, _ in formula.xors)}
    formula.write(formula_path)
    formula_sha = sha(formula_path)
    formula_bytes = formula_path.stat().st_size
    remaining = args.max_seconds - (time.perf_counter() - started)
    solver_binary = Path(shutil.which("cryptominisat5"))
    command = [str(solver_binary), "--verb", "1", "--threads", "1",
               "--maxtime", str(max(1, int(remaining))), "--maxconfl",
               str(args.max_conflicts), str(formula_path)]
    if remaining <= 0:
        stdout, stderr, code, status = "", "", None, "no_solver_budget"
        solver_seconds = 0.0
    else:
        solver_started = time.perf_counter()
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
        solver_seconds = time.perf_counter() - solver_started
    charged_seconds = time.perf_counter() - started
    stdout_path.write_text(stdout)
    stderr_path.write_text(stderr)
    conflicts = re.findall(r"conflicts\s*[:=]\s*([0-9]+)", stdout,
                           flags=re.IGNORECASE)
    model = parse_model(stdout)
    raw_x = projected_x = relation = lift_status = None
    if model is not None:
        raw_x, projected_x, relation, lift_status = check_model(
            raw_leaves, projected_leaves, model, onb, curve,
            order, keys, public)
    peak_child_rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    witness_path, points = witness_points(
        n, kind, onb, curve, baseline, 4)
    control = (lock_control(formula, raw_leaves, projected_leaves, mids,
                            baseline, onb, curve, order, keys, public,
                            witness_path, points) if points is not None
               else None)
    with archive_formula.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream,
                           mtime=0, compresslevel=9) as zipped:
            zipped.write(formula_path.read_bytes())
    assert hashlib.sha256(gzip.decompress(
        archive_formula.read_bytes())).hexdigest() == formula_sha
    receipt = {
        "kind": "cofactor_four_projected_sparse_s3_stage_probe",
        "proposal_id": "Q1317", "candidate_id": None, "run_id": None,
        "workload_id": baseline["workload_id"],
        "curve_id": baseline["curve_id"], "isogeny": "none",
        "n": n, "workload_kind": kind,
        "public_target": list(baseline["public_subgroup_target"]),
        "target_x_coordinates": target_x,
        "base_archive_sha256": sha(archive_path),
        "factor_base_enumerated_set_sha256": baseline[
            "factor_base_enumerated_set_sha256"],
        "factor_base_actual_B": baseline["factor_base_actual_B"],
        "factor_base_folded_columns": len(keys),
        "leaf_policy": "four rational raw x values of normal-basis weight at most 4, each projected by exact cofactor 4; signs checked by group replay",
        "target_policy": "one exact public subgroup point; no raw cofactor-preimage selector",
        "target_independent_base_load_seconds": setup_seconds,
        "formula_build_seconds": build_seconds,
        "target_pdp_wall_seconds": charged_seconds,
        "solver_wall_seconds": solver_seconds,
        "formula": formula_stats,
        "xcnf_sha256": formula_sha,
        "xcnf_bytes": formula_bytes,
        "status": status, "return_code": code,
        "solver_conflicts_reported": (int(conflicts[-1]) if conflicts else None),
        "raw_x_coordinates": raw_x,
        "projected_x_coordinates": projected_x,
        "lift_status": lift_status,
        "verified_relation": relation,
        "observed_verified_relation_count": int(relation is not None),
        "natural_relation_yield_estimate": None,
        "field_operations": None,
        "complete_solve_work_log2": None,
        "locked_control": control,
        "peak_child_rss_raw_before_control": peak_child_rss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "max_seconds": args.max_seconds,
        "max_conflicts": args.max_conflicts,
        "solver_command": command,
        "solver_binary_sha256": sha(solver_binary),
        "solver_stdout_sha256": sha(stdout_path),
        "solver_stderr_sha256": sha(stderr_path),
        "baseline_receipt_sha256": sha(baseline_path),
        "protocol_sha256": sha(HERE / "protocol.json"),
        "runtime_info_sha256": sha(runtime_path),
        "core_source_sha256": sha(HERE / "chain_s3.py"),
        "factored_source_sha256": sha(HERE / "chain_s3_factored.py"),
        "projected_source_sha256": sha(HERE / "chain_s3_projected_sparse.py"),
        "base_probe_source_sha256": sha(HERE / "run_base_orbit_probe.py"),
        "runner_source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"n": n, "kind": kind, "status": status,
                      "verified_relation": relation is not None,
                      "formula": formula_stats,
                      "solver_conflicts": receipt["solver_conflicts_reported"],
                      "target_pdp_wall_seconds": charged_seconds,
                      "locked_control": control["status"] if control else None}))


if __name__ == "__main__":
    main()
