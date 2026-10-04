#!/usr/bin/env python3
"""Bounded S3 half-trace-root searches on the exact n83 projected base."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import resource
import shutil
import subprocess
import time
from pathlib import Path

from chain_s3_rooted import build_rooted_projected_chain
from run_base_orbit_probe import read_inputs, witness_points
from run_projected_sparse_probe import check_model, lock_control
from run_probe import HERE, curves, field, parse_model, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("ordinary", "planted"),
                        required=True)
    parser.add_argument("--rooted-links", type=int, choices=(1, 2),
                        required=True)
    parser.add_argument("--pin-raw-leaves", action="store_true")
    parser.add_argument("--max-seconds", type=int, default=120)
    parser.add_argument("--max-conflicts", type=int, default=1_000_000)
    args = parser.parse_args()
    assert not args.pin_raw_leaves or args.kind == "planted"
    n, weight, kind = 83, 4, args.kind
    stem = (f"n{n}_{kind}_rooted{args.rooted_links}" +
            ("_rawpin4" if args.pin_raw_leaves else ""))
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
    raw_witness = (baseline["fixture"]["planted_leaf_x"]
                   if kind == "planted" else None)

    started = time.perf_counter()
    target_x = onb.toCoords(public[0])
    formula, raw_leaves, projected_leaves, mids, branches = (
        build_rooted_projected_chain(
            n, weight, target_x, args.rooted_links))
    if args.pin_raw_leaves:
        for variables, value in zip(raw_leaves, raw_witness):
            formula.clauses.extend(([
                bit if value >> position & 1 else -bit]
                for position, bit in enumerate(variables)))
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
    raw_x = projected_x = relation = lift_status = branch_values = None
    if model is not None:
        raw_x, projected_x, relation, lift_status = check_model(
            raw_leaves, projected_leaves, model, onb, curve,
            order, keys, public)
        branch_values = [int(model.get(bit, False)) for bit in branches]
        if args.pin_raw_leaves:
            assert raw_x == raw_witness
            assert relation is not None
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
        "kind": "half_trace_rooted_projected_sparse_s3_stage_probe",
        "proposal_id": "Q1319", "candidate_id": None,
        "run_id": None,
        "workload_id": None if args.pin_raw_leaves else baseline["workload_id"],
        "is_natural_relation_yield_measurement": (
            kind == "ordinary" and not args.pin_raw_leaves),
        "oracle_assisted_raw_leaf_choices": args.pin_raw_leaves,
        "curve_id": baseline["curve_id"], "isogeny": "none",
        "n": n, "workload_kind": kind,
        "rooted_links": args.rooted_links,
        "public_target": list(baseline["public_subgroup_target"]),
        "target_x_coordinates": target_x,
        "base_archive_sha256": sha(archive_path),
        "factor_base_enumerated_set_sha256": baseline[
            "factor_base_enumerated_set_sha256"],
        "factor_base_actual_B": baseline["factor_base_actual_B"],
        "factor_base_folded_columns": len(keys),
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
        "root_branch_values": branch_values,
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
        "oracle_source_sha256": sha(HERE / "s3_root_oracle.py"),
        "rooted_source_sha256": sha(HERE / "chain_s3_rooted.py"),
        "base_probe_source_sha256": sha(HERE / "run_base_orbit_probe.py"),
        "stage_probe_source_sha256": sha(
            HERE / "run_projected_sparse_probe.py"),
        "runner_source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"kind": kind, "rooted_links": args.rooted_links,
                      "pin_raw_leaves": args.pin_raw_leaves,
                      "status": status, "verified_relation": relation is not None,
                      "formula": formula_stats,
                      "conflicts": receipt["solver_conflicts_reported"],
                      "target_pdp_wall_seconds": charged_seconds,
                      "locked_control": control["status"] if control else None}))


if __name__ == "__main__":
    main()
