#!/usr/bin/env python3
"""Source-bound n53 three-leaf pin control without reverse propagation."""

from __future__ import annotations

import json
import resource
import shutil
import time
from pathlib import Path

from chain_group_add import build_exact_base_group_chain
from run_base_orbit_probe import read_inputs, witness_points
from run_group_add_probe import archive, solve, stats, verify_model
from run_group_add_reverse_probe import pin_prefix
from run_probe import HERE, curves, field, sha


def main():
    stem = "n53_ordinary_group_add_forward_pin3"
    output = HERE / "runs" / f"{stem}.json"
    formula_path = HERE / "runs" / f"{stem}.xcnf"
    stdout_path = HERE / "runs" / f"{stem}.stdout.txt"
    stderr_path = HERE / "runs" / f"{stem}.stderr.txt"
    assert not any(path.exists() for path in (
        output, formula_path, formula_path.with_suffix(".xcnf.gz"),
        stdout_path, stderr_path))
    runtime_path = HERE / "group_add_reverse_sage_runtime_info.json"
    assert json.loads(runtime_path.read_text())["status"] == "verified"
    baseline_path, baseline, base_path, base, keys = read_inputs(53,
                                                                 "ordinary")
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    public = tuple(map(int, baseline["public_subgroup_target"]))
    order = int(base["curve"]["subgroup_order"])
    witness_path, points = witness_points(
        53, "ordinary", onb, curve, baseline,
        int(base["curve"]["cofactor"]))
    binary = Path(shutil.which("cryptominisat5"))
    started = time.perf_counter()
    formula, choices, leaves, mids, slopes = build_exact_base_group_chain(
        53, keys, public)
    pin_prefix(formula, None, leaves, baseline, points, onb, 3)
    formula_stats = stats(formula)
    formula.write(formula_path)
    remaining = 20 - (time.perf_counter() - started)
    if remaining > 0:
        result = solve(formula_path, binary, remaining, 1_000_000)
    else:
        result = {"command": None, "status": "no_solver_budget",
                  "return_code": None, "wall_seconds": 0.0,
                  "conflicts_reported": None, "stdout": "", "stderr": "",
                  "model": None}
    charged_seconds = time.perf_counter() - started
    peak_child_rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    stdout_path.write_text(result["stdout"])
    stderr_path.write_text(result["stderr"])
    relation = (verify_model(53, None, choices, leaves, result["model"],
                             onb, curve, order, keys, public)
                if result["model"] is not None else None)
    compressed, formula_bytes, formula_sha = archive(formula_path)
    receipt = {
        "kind": "forward_group_addition_three_leaf_pin_diagnostic",
        "proposal_id": "Q1320", "candidate_id": None,
        "workload_id": None, "run_id": None,
        "curve_id": baseline["curve_id"], "isogeny": "none",
        "n": 53, "workload_kind": "ordinary",
        "public_target": list(baseline["public_subgroup_target"]),
        "factor_base_actual_B": baseline["factor_base_actual_B"],
        "factor_base_folded_columns": baseline[
            "factor_base_folded_columns"],
        "factor_base_enumerated_set_sha256": baseline[
            "factor_base_enumerated_set_sha256"],
        "base_archive_sha256": sha(base_path),
        "pin_leaves": 3, "oracle_assisted": True,
        "target_pdp_wall_seconds": None,
        "oracle_diagnostic_wall_seconds": charged_seconds,
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
        "field_operations": None,
        "complete_solve_work_log2": None,
        "peak_child_rss_raw": peak_child_rss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "max_seconds": 20,
        "max_conflicts": 1_000_000,
        "solver_command": result["command"],
        "solver_binary_sha256": sha(binary),
        "solver_stdout_sha256": sha(stdout_path),
        "solver_stderr_sha256": sha(stderr_path),
        "known_witness_receipt_sha256": sha(witness_path),
        "baseline_receipt_sha256": sha(baseline_path),
        "protocol_sha256": sha(HERE / "protocol.json"),
        "runtime_info_sha256": sha(runtime_path),
        "core_source_sha256": sha(HERE / "chain_s3.py"),
        "group_add_source_sha256": sha(HERE / "chain_group_add.py"),
        "base_orbit_source_sha256": sha(HERE / "chain_s3_base_orbit.py"),
        "base_probe_source_sha256": sha(HERE / "run_base_orbit_probe.py"),
        "group_probe_source_sha256": sha(HERE / "run_group_add_probe.py"),
        "reverse_probe_source_sha256": sha(
            HERE / "run_group_add_reverse_probe.py"),
        "runner_source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": result["status"],
                      "verified_relation": relation is not None,
                      "wall_seconds": charged_seconds,
                      "formula": formula_stats}))


if __name__ == "__main__":
    main()
