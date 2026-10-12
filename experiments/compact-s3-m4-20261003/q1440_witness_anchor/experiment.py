#!/usr/bin/env python3
"""Q1440 witness-anchor search diagnostic on Q1439's exact S3 reduction."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import resource
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parents[1]
sys.path.insert(0, str(PARENT))
from q1419_partial_pin.run_cell import pin_bits  # noqa: E402
from q1439_fixed_leaf import experiment as parent  # noqa: E402
from run_group_add_probe import archive, solve, stats  # noqa: E402
from run_probe import parse_model, sha  # noqa: E402

PROTOCOL = HERE / "protocol.json"
Q1439 = PARENT / "q1439_fixed_leaf"
CAP = {"wall_seconds": 60, "conflicts": 1_000_000}
CELLS = ("choice_pinned", "choice_free")


def inputs(n):
    prepared = parent.prepare(n, "control")
    q1439_protocol = json.loads((Q1439 / "protocol.json").read_text())
    q1439_cell = q1439_protocol["cells"][f"n{n}_control"]
    assert q1439_cell["anchor_raw_x"] == prepared["anchor_mask"]
    assert q1439_cell["adjustment_cases_sha256"] == parent.digest(
        prepared["cases"])
    assert q1439_cell["control_target_choice"] == prepared["control_choice"]
    return prepared


def build(prepared, cell):
    assert cell in CELLS
    symbolic = dict(prepared)
    symbolic["cell"] = "ordinary"  # Q1439 builder then leaves all B,C,D bits free.
    formula, leaves, mid, selector = parent.build(symbolic)
    if cell == "choice_pinned":
        pin_bits(formula, selector, prepared["control_choice"])
    return formula, leaves, mid, selector


def input_record(prepared, cell):
    n = prepared["n"]
    instance, base = prepared["instance"], prepared["base"]
    target_origin = ("archived ordinary public point with a known relation"
                     if n == 53 else "archived planted control public point")
    law = ("known-witness first anchor, B/C/D unpinned, adjusted-target "
           "selector pinned to archived witness" if cell == "choice_pinned"
           else "known-witness first anchor, B/C/D and adjusted-target "
                "selector unpinned")
    return {
        "curve_id": instance["curve_id"],
        "subgroup_order_r": instance["subgroup_order"],
        "factor_base_enumerated_set_sha256": base["enumerated_set_sha256"],
        "public_target": parent.point_record(prepared["public"]),
        "target_origin": target_origin,
        "input_law": law,
        "anchor_source": "Q1419 archived witness first raw leaf",
        "anchor_raw_x": prepared["anchor_mask"],
        "raw_target_preimage_x_sha256": parent.digest(
            prepared["parent"]["raw_preimage_x_coordinates"]),
        "adjusted_target_x_sha256": parent.digest(prepared["target_xs"]),
        "known_witness_adjusted_target_choice": (
            prepared["control_choice"] if cell == "choice_pinned" else None),
        "cold_or_warm_target_count": 1,
        "cache_state": "cold",
    }


def frozen_cell(prepared, cell, formula, formula_sha):
    n = prepared["n"]
    instance, base = prepared["instance"], prepared["base"]
    workload = input_record(prepared, cell)
    config = {
        "curve_id": instance["curve_id"],
        "factor_base_enumerated_set_sha256": base["enumerated_set_sha256"],
        "factor_base_actual_B": base["actual_usable_points_B_before_folding"],
        "anchor_raw_x": prepared["anchor_mask"],
        "m": 4,
        "solver": "two factored S3 links in XCNF with CryptoMiniSat5",
        "solver_source_sha256": sha(Q1439 / "experiment.py"),
        "point_decomposition_stage_code": "PDP4sat",
        "pinning_policy": cell,
        "isogeny": "none",
    }
    config_sha = parent.digest(config)
    stage_id = (f"PS1N{n}Ckb1fb{config['factor_base_actual_B']}"
                f"PDP4sath{config_sha[:12]}")
    workload_id = parent.digest(workload)[:12]
    return {
        "curve_id": instance["curve_id"],
        "factor_base_actual_B": config["factor_base_actual_B"],
        "folded_columns_K": base["signed_frobenius_columns_K"],
        "factor_base_enumerated_set_sha256": base["enumerated_set_sha256"],
        "base_receipt_sha256": sha(prepared["base_path"]),
        "public_target": parent.point_record(prepared["public"]),
        "target_origin": workload["target_origin"],
        "input_law": workload["input_law"],
        "anchor_raw_x": prepared["anchor_mask"],
        "adjustment_case_count": len(prepared["cases"]),
        "adjusted_target_x_count": len(prepared["target_xs"]),
        "known_witness_adjusted_target_choice": prepared["control_choice"],
        "fixture_raw_leaf_x": prepared["fixture"]["fixture"]["raw_leaf_x"],
        "formula_stats": stats(formula),
        "formula_raw_sha256": formula_sha,
        "stage_config_id": stage_id,
        "stage_config_sha256": config_sha,
        "workload_id": workload_id,
        "workload_record": workload,
        "stage_run_id": f"{stage_id}W{workload_id}R1",
        "solver_wall_cap_seconds": CAP["wall_seconds"],
        "solver_conflict_cap": CAP["conflicts"],
    }


def frozen_formula(prepared, cell, name):
    formula, leaves, mid, selector = build(prepared, cell)
    temp = HERE / f".freeze_{name}.xcnf"
    assert not temp.exists()
    try:
        formula.write(temp)
        formula_sha = sha(temp)
    finally:
        temp.unlink(missing_ok=True)
    return formula, leaves, mid, selector, formula_sha


def check_protocol():
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["proposal_id"] == "Q1440"
    assert protocol["candidate_id"] is None and protocol["isogeny"] == "none"
    assert protocol["source_sha256"] == sha(Path(__file__))
    assert protocol["runtime_info_sha256"] == sha(HERE / "sage_runtime_info.json")
    assert json.loads((HERE / "sage_runtime_info.json").read_text())[
        "status"] == "verified"
    assert protocol["solver_binary_sha256"] == sha(Path(
        shutil.which("cryptominisat5")))
    for name, expected in protocol["input_sha256"].items():
        assert sha(ROOT / name) == expected
    return protocol


def freeze():
    assert not PROTOCOL.exists(), "refuse to overwrite frozen protocol"
    runtime = HERE / "sage_runtime_info.json"
    assert runtime.exists() and json.loads(runtime.read_text())["status"] == "verified"
    q1439_verified = json.loads((Q1439 / "verification.json").read_text())
    assert q1439_verified["status"] == "passed"
    assert [row["verified_relation_count"] for row in q1439_verified["rows"]] == [
        1, 0, 1, 0]
    path_set = {Q1439 / "experiment.py", Q1439 / "protocol.json",
                Q1439 / "verification.json",
                PARENT / "q1419_partial_pin/protocol.json",
                PARENT / "q1438_dense_base/solver_protocol.json"}
    cells = {}
    for n in (53, 83):
        prepared = inputs(n)
        assert prepared["identity_adjustment_count"] == 0
        path_set.add(prepared["base_path"])
        q1419 = json.loads((PARENT / "q1419_partial_pin/protocol.json").read_text())
        profile = q1419["profiles"][str(n)]
        for name in ("parent_receipt", "fixture_receipt"):
            path_set.add(ROOT / profile[name]["path"])
        for cell in CELLS:
            key = f"n{n}_{cell}"
            formula, _, _, _, formula_sha = frozen_formula(prepared, cell, key)
            cells[key] = frozen_cell(prepared, cell, formula, formula_sha)
    protocol = {
        "kind": "q1440_frozen_witness_anchor_three_leaf_search_protocol",
        "proposal_id": "Q1440", "candidate_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4sat",
        "scope": "witness-informed diagnostic only; neither cell estimates natural relation yield or online IC speed",
        "claim_boundary": "N53 target is the archived ordinary public point, but the anchor comes from its known relation. N83 target and anchor come from a planted control. All other leaves are free. Successful cells measure conditioned search, not unbiased ordinary-query cost. Timeouts remain censored; complete N131 work stays null.",
        "source_sha256": sha(Path(__file__)),
        "input_sha256": {str(path.relative_to(ROOT)): sha(path)
                         for path in sorted(path_set)},
        "runtime_info_sha256": sha(runtime),
        "solver_binary_sha256": sha(Path(shutil.which("cryptominisat5"))),
        "run_order": [f"n{n}_{cell}" for n in (53, 83) for cell in CELLS],
        "cells": cells,
    }
    PROTOCOL.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "frozen", "proposal_id": "Q1440",
                      "cells": {key: {"formula_stats": row["formula_stats"],
                                       "formula_raw_sha256": row["formula_raw_sha256"],
                                       "workload_id": row["workload_id"]}
                                for key, row in cells.items()}}, sort_keys=True),
          flush=True)


def run(n, cell):
    protocol = check_protocol()
    key = f"n{n}_{cell}"
    assert key in protocol["run_order"]
    frozen = protocol["cells"][key]
    output = HERE / "runs" / key
    assert not output.exists(), "refuse to overwrite frozen run"
    build_started = time.perf_counter()
    prepared = inputs(n)
    formula, leaves, mid, selector = build(prepared, cell)
    assert stats(formula) == frozen["formula_stats"]
    build_seconds = time.perf_counter() - build_started
    output.mkdir(parents=True)
    formula_path = output / "system.xcnf"
    formula.write(formula_path)
    assert sha(formula_path) == frozen["formula_raw_sha256"]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = solve(formula_path, Path(shutil.which("cryptominisat5")),
                   frozen["solver_wall_cap_seconds"],
                   frozen["solver_conflict_cap"])
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    stdout_path, stderr_path = output / "solver.stdout.txt", output / "solver.stderr.txt"
    stdout_path.write_text(result["stdout"])
    stderr_path.write_text(result["stderr"])
    check_started = time.perf_counter()
    checked = check_error = None
    if result["model"] is not None:
        try:
            checked = parent.check_relation(prepared, formula, leaves, mid,
                                            selector, result["model"])
        except Exception as error:
            check_error = repr(error)
    check_seconds = time.perf_counter() - check_started
    archive_path, raw_bytes, raw_sha = archive(formula_path)
    verified = int(checked is not None and checked.get("status") ==
                   "verified_four_point_relation")
    receipt = {
        "kind": "q1440_witness_anchor_three_leaf_search_stage_run",
        "proposal_id": "Q1440", "candidate_id": None,
        "curve_id": frozen["curve_id"], "isogeny": "none",
        "degree_n": n, "cell": cell,
        "target_origin": frozen["target_origin"],
        "input_law": frozen["input_law"],
        "factor_base_actual_B": frozen["factor_base_actual_B"],
        "folded_columns_K": frozen["folded_columns_K"],
        "factor_base_enumerated_set_sha256": frozen[
            "factor_base_enumerated_set_sha256"],
        "public_target": frozen["public_target"],
        "anchor_raw_x": frozen["anchor_raw_x"],
        "adjustment_case_count": frozen["adjustment_case_count"],
        "adjusted_target_x_count": frozen["adjusted_target_x_count"],
        "stage_config_id": frozen["stage_config_id"],
        "workload_id": frozen["workload_id"],
        "stage_run_id": frozen["stage_run_id"],
        "formula": stats(formula),
        "formula_raw_bytes": raw_bytes,
        "formula_raw_sha256": raw_sha,
        "formula_archive_sha256": sha(archive_path),
        "solver_status": result["status"],
        "solver_return_code": result["return_code"],
        "solver_conflicts_reported": result["conflicts_reported"],
        "target_preparation_and_formula_wall_seconds_exploratory": build_seconds,
        "solver_wall_seconds_exploratory": result["wall_seconds"],
        "relation_check_wall_seconds_exploratory": check_seconds,
        "charged_stage_wall_seconds_exploratory": build_seconds + result["wall_seconds"] + check_seconds,
        "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
        "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
        "peak_child_rss_raw": after.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "model_check": checked,
        "model_check_error": check_error,
        "verified_relation_count": verified,
        "solver_stdout_sha256": sha(stdout_path),
        "solver_stderr_sha256": sha(stderr_path),
        "natural_relation_yield_estimate": None,
        "cost_per_useful_row": None,
        "complete_solve_work_log2": None,
        "cpu_wall_speedup_claim": False,
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2,
                                                     sort_keys=True) + "\n")
    print(json.dumps({"key": key, "status": result["status"],
                      "verified_relation_count": verified,
                      "model_check_error": check_error,
                      "solver_wall_seconds": result["wall_seconds"]},
                     sort_keys=True), flush=True)


def verify(emit):
    protocol = check_protocol()
    rows = []
    for key in protocol["run_order"]:
        n = int(key[1:3])
        cell = key.split("_", 1)[1]
        frozen = protocol["cells"][key]
        output = HERE / "runs" / key
        receipt_path = output / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["protocol_sha256"] == sha(PROTOCOL)
        assert receipt["source_sha256"] == sha(Path(__file__))
        assert receipt["stage_run_id"] == frozen["stage_run_id"]
        assert receipt["formula_raw_sha256"] == frozen["formula_raw_sha256"]
        assert receipt["formula_archive_sha256"] == sha(output / "system.xcnf.gz")
        assert receipt["solver_stdout_sha256"] == sha(output / "solver.stdout.txt")
        assert receipt["solver_stderr_sha256"] == sha(output / "solver.stderr.txt")
        prepared = inputs(n)
        formula, leaves, mid, selector = build(prepared, cell)
        assert stats(formula) == frozen["formula_stats"]
        temp = HERE / f".verify_{key}.xcnf"
        assert not temp.exists()
        try:
            formula.write(temp)
            assert sha(temp) == frozen["formula_raw_sha256"]
            assert temp.read_bytes() == gzip.decompress(
                (output / "system.xcnf.gz").read_bytes())
        finally:
            temp.unlink(missing_ok=True)
        model = parse_model((output / "solver.stdout.txt").read_text())
        if model is not None:
            checked = parent.check_relation(prepared, formula, leaves, mid,
                                            selector, model)
            assert checked == receipt["model_check"]
            assert receipt["model_check_error"] is None
        else:
            assert receipt["model_check"] is None
        assert receipt["verified_relation_count"] == int(
            receipt["model_check"] is not None and
            receipt["model_check"]["status"] == "verified_four_point_relation")
        assert receipt["natural_relation_yield_estimate"] is None
        assert receipt["cost_per_useful_row"] is None
        assert receipt["complete_solve_work_log2"] is None
        rows.append({"key": key, "solver_status": receipt["solver_status"],
                     "verified_relation_count": receipt["verified_relation_count"],
                     "receipt_sha256": sha(receipt_path)})
    result = {"kind": "q1440_witness_anchor_archive_replay",
              "status": "passed", "proposal_id": "Q1440",
              "candidate_id": None, "isogeny": "none", "rows": rows,
              "protocol_sha256": sha(PROTOCOL),
              "source_sha256": sha(Path(__file__)),
              "scope": "rebuilds every XCNF and replays SAT models; all cells are witness-informed diagnostics, not ordinary-yield estimates"}
    if emit:
        path = HERE / "verification.json"
        assert not path.exists(), "refuse to overwrite verification"
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True), flush=True)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("freeze")
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    run_parser.add_argument("--cell", choices=CELLS, required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--emit", action="store_true")
    args = parser.parse_args()
    if args.command == "freeze":
        freeze()
    elif args.command == "run":
        run(args.degree, args.cell)
    else:
        verify(args.emit)


if __name__ == "__main__":
    main()
