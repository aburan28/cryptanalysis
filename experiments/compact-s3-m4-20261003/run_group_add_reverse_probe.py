#!/usr/bin/env python3
"""Bounded reverse-link four-point SAT search on frozen exact bases."""

from __future__ import annotations

import argparse
import json
import resource
import shutil
import time
from pathlib import Path

from chain_group_add_reverse import (build_exact_base_reverse_chain,
                                     build_projected_sparse_reverse_chain)
from run_base_orbit_probe import read_inputs, witness_points
from run_group_add_probe import archive, solve, stats, verify_model
from run_probe import HERE, curves, field, sha


def pin_prefix(formula, raw_leaves, leaves, baseline, points, onb, count):
    if raw_leaves is not None:
        for bits, value in zip(raw_leaves[:count],
                               baseline["fixture"]["planted_leaf_x"][:count]):
            formula.clauses.extend(([
                bit if value >> position & 1 else -bit]
                for position, bit in enumerate(bits)))
    for (x_bits, y_bits), point in zip(leaves[:count], points[:count]):
        for bits, value in ((x_bits, onb.toCoords(point[0])),
                            (y_bits, onb.toCoords(point[1]))):
            formula.clauses.extend(([
                bit if value >> position & 1 else -bit]
                for position, bit in enumerate(bits)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(53, 83), required=True)
    parser.add_argument("--kind", choices=("ordinary", "planted"),
                        required=True)
    parser.add_argument("--pin-leaves", type=int, choices=(0, 2, 3),
                        required=True)
    parser.add_argument("--max-seconds", type=int, default=60)
    parser.add_argument("--max-conflicts", type=int, default=1_000_000)
    args = parser.parse_args()
    n, kind, pinned = args.n, args.kind, args.pin_leaves
    assert n == 83 or kind == "ordinary"
    assert args.max_seconds > 0 and args.max_conflicts > 0
    stem = f"n{n}_{kind}_group_add_reverse_pin{pinned}"
    output = HERE / "runs" / f"{stem}.json"
    formula_path = HERE / "runs" / f"{stem}.xcnf"
    archive_path = formula_path.with_suffix(".xcnf.gz")
    stdout_path = HERE / "runs" / f"{stem}.stdout.txt"
    stderr_path = HERE / "runs" / f"{stem}.stderr.txt"
    assert not any(path.exists() for path in (
        output, formula_path, archive_path, stdout_path, stderr_path))
    runtime_path = HERE / "group_add_reverse_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    baseline_path, baseline, base_path, base, keys = read_inputs(n, kind)
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    public = tuple(map(int, baseline["public_subgroup_target"]))
    order = int(base["curve"]["subgroup_order"])
    assert curve.onCurve(public) and curve.mul(public, order) is None
    witness_path, points = witness_points(
        n, kind, onb, curve, baseline, int(base["curve"]["cofactor"]))
    assert pinned == 0 or points is not None
    binary = Path(shutil.which("cryptominisat5"))
    started = time.perf_counter()
    if n == 53:
        formula, choices, leaves, mids, slopes, recovered, reverse_slope = (
            build_exact_base_reverse_chain(n, keys, public))
        raw_leaves = None
    else:
        (formula, raw_leaves, leaves, mids, slopes, recovered,
         reverse_slope) = build_projected_sparse_reverse_chain(n, 4, public)
        choices = None
    assert len(mids) == 2 and len(slopes) == 3
    assert len(recovered) == 2 and len(reverse_slope) == n
    build_seconds = time.perf_counter() - started
    if pinned:
        pin_prefix(formula, raw_leaves, leaves, baseline, points, onb,
                   pinned)
    formula_stats = stats(formula)
    formula.write(formula_path)
    remaining = args.max_seconds - (time.perf_counter() - started)
    if remaining > 0:
        result = solve(formula_path, binary, remaining, args.max_conflicts)
    else:
        result = {"command": None, "status": "no_solver_budget",
                  "return_code": None, "wall_seconds": 0.0,
                  "conflicts_reported": None, "stdout": "", "stderr": "",
                  "model": None}
    charged_seconds = time.perf_counter() - started
    peak_child_rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    stdout_path.write_text(result["stdout"])
    stderr_path.write_text(result["stderr"])
    relation = (verify_model(n, raw_leaves, choices, leaves,
                             result["model"], onb, curve, order, keys,
                             public) if result["model"] is not None else None)
    if relation is not None and pinned:
        assert relation["leaf_points"][:pinned] == [
            [int(x), int(y)] for x, y in points[:pinned]]
        if pinned == 3:
            assert relation["leaf_points"][3] == [
                int(points[3][0]), int(points[3][1])]
    compressed, formula_bytes, formula_sha = archive(formula_path)
    receipt = {
        "kind": "reverse_last_link_four_point_stage_probe",
        "proposal_id": "Q1322" if n == 53 else "Q1323",
        "candidate_id": None,
        "workload_id": baseline["workload_id"] if pinned == 0 else None,
        "run_id": None,
        "curve_id": baseline["curve_id"], "isogeny": "none",
        "n": n, "workload_kind": kind,
        "public_target": list(baseline["public_subgroup_target"]),
        "factor_base_actual_B": baseline["factor_base_actual_B"],
        "factor_base_folded_columns": baseline[
            "factor_base_folded_columns"],
        "factor_base_enumerated_set_sha256": baseline[
            "factor_base_enumerated_set_sha256"],
        "base_archive_sha256": sha(base_path),
        "pin_leaves": pinned,
        "oracle_assisted": pinned > 0,
        "additional_restriction": "x(public target) != x(first three leaf sum)",
        "formula_build_seconds": build_seconds,
        "target_pdp_wall_seconds": charged_seconds if pinned == 0 else None,
        "oracle_diagnostic_wall_seconds": charged_seconds if pinned else None,
        "solver_wall_seconds": result["wall_seconds"],
        "status": result["status"],
        "return_code": result["return_code"],
        "solver_conflicts_reported": result["conflicts_reported"],
        "formula": formula_stats,
        "xcnf_archive": compressed.name,
        "xcnf_sha256": formula_sha,
        "xcnf_bytes": formula_bytes,
        "verified_relation": relation,
        "observed_verified_relation_count": int(relation is not None),
        "natural_relation_yield_estimate": None,
        "field_operations": None,
        "complete_solve_work_log2": None,
        "peak_child_rss_raw": peak_child_rss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "max_seconds": args.max_seconds,
        "max_conflicts": args.max_conflicts,
        "solver_command": result["command"],
        "solver_binary_sha256": sha(binary),
        "solver_stdout_sha256": sha(stdout_path),
        "solver_stderr_sha256": sha(stderr_path),
        "known_witness_receipt_sha256": (sha(witness_path) if pinned
                                         else None),
        "baseline_receipt_sha256": sha(baseline_path),
        "protocol_sha256": sha(HERE / "protocol.json"),
        "runtime_info_sha256": sha(runtime_path),
        "core_source_sha256": sha(HERE / "chain_s3.py"),
        "group_add_source_sha256": sha(HERE / "chain_group_add.py"),
        "reverse_source_sha256": sha(HERE / "chain_group_add_reverse.py"),
        "projected_source_sha256": (sha(
            HERE / "chain_s3_projected_sparse.py") if n == 83 else None),
        "base_orbit_source_sha256": sha(HERE / "chain_s3_base_orbit.py"),
        "base_probe_source_sha256": sha(HERE / "run_base_orbit_probe.py"),
        "group_probe_source_sha256": sha(HERE / "run_group_add_probe.py"),
        "probe_source_sha256": sha(HERE / "run_probe.py"),
        "runner_source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"n": n, "kind": kind, "pinned": pinned,
                      "status": result["status"],
                      "verified_relation": relation is not None,
                      "formula": formula_stats,
                      "wall_seconds": charged_seconds}))


if __name__ == "__main__":
    main()
