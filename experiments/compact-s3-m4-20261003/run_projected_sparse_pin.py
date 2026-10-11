#!/usr/bin/env python3
"""Oracle-assisted raw-leaf pin diagnostic for the n83 projected S3 chain."""

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
from run_base_orbit_probe import read_inputs
from run_projected_sparse_probe import check_model
from run_probe import HERE, curves, field, parse_model, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pin-count", type=int, choices=(2, 3, 4),
                        required=True)
    parser.add_argument("--max-seconds", type=int, default=60)
    parser.add_argument("--max-conflicts", type=int, default=200_000)
    args = parser.parse_args()
    stem = f"n83_planted_projected_sparse_rawpin{args.pin_count}"
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
    assert planted["status"] == "external_timeout"
    runtime_path = HERE / "projected_sparse_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    public = tuple(map(int, baseline["public_subgroup_target"]))
    order = int(archive["curve"]["subgroup_order"])
    raw_witness = baseline["fixture"]["planted_leaf_x"]
    assert len(raw_witness) == 4

    started = time.perf_counter()
    formula, raw_leaves, projected_leaves, mids = (
        build_projected_sparse_chain(83, 4, onb.toCoords(public[0])))
    for variables, value in zip(raw_leaves[:args.pin_count],
                                raw_witness[:args.pin_count]):
        formula.clauses.extend(([
            bit if value >> position & 1 else -bit]
            for position, bit in enumerate(variables)))
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
        assert raw_x[:args.pin_count] == raw_witness[:args.pin_count]
    peak_child_rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    with archive_formula.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream,
                           mtime=0, compresslevel=9) as zipped:
            zipped.write(formula_path.read_bytes())
    assert hashlib.sha256(gzip.decompress(
        archive_formula.read_bytes())).hexdigest() == formula_sha
    receipt = {
        "kind": "oracle_assisted_n83_projected_sparse_raw_leaf_pin",
        "proposal_id": "Q1317", "candidate_id": None,
        "workload_id": None, "run_id": None,
        "is_natural_relation_yield_measurement": False,
        "oracle_assisted_raw_leaf_choices": True,
        "curve_id": baseline["curve_id"], "isogeny": "none",
        "n": 83, "pin_count": args.pin_count,
        "pinned_leaf_positions": list(range(args.pin_count)),
        "pinned_raw_x_coordinates": raw_witness[:args.pin_count],
        "intermediate_x_coordinates_pinned": False,
        "projected_x_coordinates_pinned": False,
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
    print(json.dumps({"pin_count": args.pin_count, "status": status,
                      "verified_relation": relation is not None,
                      "conflicts": receipt["solver_conflicts_reported"],
                      "charged_seconds": charged_seconds}))


if __name__ == "__main__":
    main()
