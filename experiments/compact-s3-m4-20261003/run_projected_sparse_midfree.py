#!/usr/bin/env python3
"""Pin known n83 leaves and measure the free S3 intermediate search."""

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

from chain_s3_projected_sparse import build_projected_sparse_chain
from run_base_orbit_probe import read_inputs, witness_points
from run_projected_sparse_probe import check_model
from run_probe import HERE, curves, field, parse_model, sha


def pin_vector(formula, variables, value):
    formula.clauses.extend(([
        bit if value >> position & 1 else -bit]
        for position, bit in enumerate(variables)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("leaf_x", "leaf_x_mid1", "full"),
                        required=True)
    parser.add_argument("--max-seconds", type=int, default=60)
    parser.add_argument("--max-conflicts", type=int, default=200_000)
    args = parser.parse_args()
    stem = f"n83_planted_projected_sparse_{args.mode}_pin"
    output = HERE / "runs" / f"{stem}.json"
    formula_path = HERE / "runs" / f"{stem}.xcnf"
    archive_formula = HERE / "runs" / f"{stem}.xcnf.gz"
    stdout_path = HERE / "runs" / f"{stem}.stdout.txt"
    stderr_path = HERE / "runs" / f"{stem}.stderr.txt"
    assert not any(path.exists() for path in (
        output, formula_path, archive_formula, stdout_path, stderr_path))
    baseline_path, baseline, archive_path, archive, keys = read_inputs(
        83, "planted")
    planted_path = HERE / "runs/n83_planted_projected_sparse.json"
    planted = json.loads(planted_path.read_text())
    assert planted["baseline_receipt_sha256"] == sha(baseline_path)
    runtime_path = HERE / "projected_sparse_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    public = tuple(map(int, baseline["public_subgroup_target"]))
    order = int(archive["curve"]["subgroup_order"])
    witness_path, points = witness_points(
        83, "planted", onb, curve, baseline, 4)
    raw_witness = baseline["fixture"]["planted_leaf_x"]
    projected_witness = [onb.toCoords(point[0]) for point in points]
    first = curve.add(points[0], points[1])
    second = curve.add(first, points[2])
    assert first is not None and second is not None
    assert curve.add(second, points[3]) == public
    mids_witness = [onb.toCoords(first[0]), onb.toCoords(second[0])]
    pin_mid_count = {"leaf_x": 0, "leaf_x_mid1": 1, "full": 2}[
        args.mode]

    started = time.perf_counter()
    formula, raw_leaves, projected_leaves, mids = (
        build_projected_sparse_chain(83, 4, onb.toCoords(public[0])))
    for row, value in zip(raw_leaves, raw_witness):
        pin_vector(formula, row, value)
    for row, value in zip(projected_leaves, projected_witness):
        pin_vector(formula, row, value)
    for row, value in zip(mids[:pin_mid_count],
                          mids_witness[:pin_mid_count]):
        pin_vector(formula, row, value)
    build_seconds = time.perf_counter() - started
    stats = {"variables": formula.variables,
             "cnf_clauses": len(formula.clauses),
             "xor_rows": len(formula.xors),
             "and_gates": len(formula.and_cache)}
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
        assert raw_x == raw_witness
        assert projected_x == projected_witness
        assert relation is not None
    peak_child_rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    with archive_formula.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream,
                           mtime=0, compresslevel=9) as zipped:
            zipped.write(formula_path.read_bytes())
    assert hashlib.sha256(gzip.decompress(
        archive_formula.read_bytes())).hexdigest() == formula_sha
    receipt = {
        "kind": "oracle_assisted_n83_projected_sparse_intermediate_pin",
        "proposal_id": "Q1317", "candidate_id": None,
        "workload_id": None, "run_id": None,
        "is_natural_relation_yield_measurement": False,
        "oracle_assisted_raw_and_projected_leaves": True,
        "curve_id": baseline["curve_id"], "isogeny": "none",
        "n": 83, "mode": args.mode,
        "raw_leaf_count_pinned": 4,
        "projected_leaf_count_pinned": 4,
        "intermediate_x_count_pinned": pin_mid_count,
        "raw_x_witness": raw_witness,
        "projected_x_witness": projected_witness,
        "intermediate_x_witness": mids_witness,
        "public_target": list(baseline["public_subgroup_target"]),
        "factor_base_actual_B": baseline["factor_base_actual_B"],
        "factor_base_folded_columns": baseline[
            "factor_base_folded_columns"],
        "factor_base_enumerated_set_sha256": baseline[
            "factor_base_enumerated_set_sha256"],
        "formula": stats,
        "formula_build_seconds": build_seconds,
        "target_pdp_wall_seconds": charged_seconds,
        "solver_wall_seconds": solver_seconds,
        "xcnf_sha256": formula_sha,
        "xcnf_bytes": formula_bytes,
        "status": status, "return_code": code,
        "solver_conflicts_reported": int(conflicts[-1]) if conflicts else None,
        "raw_x_coordinates": raw_x,
        "projected_x_coordinates": projected_x,
        "lift_status": lift_status,
        "verified_relation": relation,
        "peak_child_rss_raw": peak_child_rss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "max_seconds": args.max_seconds,
        "max_conflicts": args.max_conflicts,
        "solver_command": command,
        "solver_binary_sha256": sha(solver_binary),
        "solver_stdout_sha256": sha(stdout_path),
        "solver_stderr_sha256": sha(stderr_path),
        "baseline_receipt_sha256": sha(baseline_path),
        "base_archive_sha256": sha(archive_path),
        "matched_unassisted_receipt_sha256": sha(planted_path),
        "witness_receipt_sha256": sha(witness_path),
        "protocol_sha256": sha(HERE / "protocol.json"),
        "runtime_info_sha256": sha(runtime_path),
        "core_source_sha256": sha(HERE / "chain_s3.py"),
        "factored_source_sha256": sha(HERE / "chain_s3_factored.py"),
        "projected_source_sha256": sha(HERE / "chain_s3_projected_sparse.py"),
        "base_probe_source_sha256": sha(HERE / "run_base_orbit_probe.py"),
        "stage_probe_source_sha256": sha(
            HERE / "run_projected_sparse_probe.py"),
        "source_sha256": sha(Path(__file__)),
        "field_operations": None,
        "complete_solve_work_log2": None,
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"mode": args.mode, "status": status,
                      "verified_relation": relation is not None,
                      "conflicts": receipt["solver_conflicts_reported"],
                      "charged_seconds": charged_seconds}))


if __name__ == "__main__":
    main()
