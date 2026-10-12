#!/usr/bin/env python3
"""Freeze and compare Q1450 linear half-trace on matched ordinary searches."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = HERE.parents[2]
BASE = STAGE / "q20261011_api_budget_stop"
BASE_BINARY = Path("/private/tmp/q1443_insearch")
LINEAR_BINARY = Path("/private/tmp/q1450_insearch")
sys.path.insert(0, str(STAGE / "q20261010_final_link"))
from verify_model import verify  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_row(spec: dict, mode: str) -> dict:
    degree = spec["degree"]
    prefix = Path("/private/tmp/q1430_n53_" + mode if degree == 53 else
                  "/private/tmp/q1430_" + mode)
    target = STAGE / "q20261010_final_link" / f"n{degree}_{mode}.targets"
    meta_path = prefix.with_suffix(".json")
    meta = json.loads(meta_path.read_text())
    manifest = json.loads(target.with_suffix(".targets.json").read_text())
    for key in ("curve_id", "factor_base_actual_B",
                "factor_base_enumerated_set_sha256"):
        assert meta[key] == manifest[key] == spec[key]
    assert (meta["factor_base_folded_columns"] ==
            manifest["factor_base_folded_columns"] ==
            spec["factor_base_folded_columns_K"])
    assert meta["workload_id"] == manifest["workload_id"]
    assert meta["workload_id"] == (
        spec["ordinary_workload_id"] if mode == "ordinary" else None)
    assert meta["isogeny"] == "none"
    assert sha(prefix.with_suffix(".cnf")) == meta["cnf_sha256"]
    assert sha(target) == manifest["target_file_sha256"]
    return {"degree": degree, "mode": mode, "curve_id": meta["curve_id"],
            "workload_id": meta["workload_id"],
            "factor_base_actual_B": meta["factor_base_actual_B"],
            "factor_base_folded_columns_K": meta["factor_base_folded_columns"],
            "factor_base_enumerated_set_sha256": meta[
                "factor_base_enumerated_set_sha256"],
            "cnf": str(prefix.with_suffix(".cnf")),
            "cnf_sha256": sha(prefix.with_suffix(".cnf")),
            "map": str(prefix.with_suffix(".map")),
            "map_sha256": sha(prefix.with_suffix(".map")),
            "meta": str(meta_path), "meta_sha256": sha(meta_path),
            "target": str(target), "target_sha256": sha(target),
            "target_manifest_sha256": sha(target.with_suffix(".targets.json"))}


def run_one(spec: dict, inp: dict, variant: str, protocol: dict) -> dict:
    solver = protocol["solver"]
    control = inp["mode"] == "control"
    binary = BASE_BINARY if variant == "base" else LINEAR_BINARY
    cap = solver["control_conflict_cap" if control else "ordinary_conflict_cap"]
    wall = solver["control_wall_cap_seconds" if control else
                  "ordinary_wall_cap_seconds"]
    budget = solver["control_api_budget" if control else "ordinary_api_budget"]
    seed = 1 if control else spec["branch_seed"]
    cmd = [str(binary), inp["cnf"], inp["map"], inp["target"],
           str(STAGE), str(ROOT / "ecc2k130/codegen"),
           solver["branch_policy"], str(seed), solver["root_encoding"],
           solver["early_target_mode"], str(solver["early_support_cap"]),
           solver["leaf_rationality_mode"], str(spec["leaf_weight_bound"]),
           str(cap), str(wall), str(budget)]
    started = time.monotonic()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          timeout=solver["external_process_timeout_seconds"],
                          check=False)
    elapsed = time.monotonic() - started
    log = HERE / f"n{spec['degree']}_{inp['mode']}_{variant}.log"
    log.write_text(proc.stdout)
    if proc.stderr:
        (HERE / f"n{spec['degree']}_{inp['mode']}_{variant}.stderr.log").write_text(
            proc.stderr)
    assert proc.returncode in (0, 10, 20), proc.stderr
    result = json.loads(proc.stdout.splitlines()[0])
    assert result["status"] == proc.returncode
    assert result["decision_seed"] == seed
    assert result["api_budget"] == budget
    api = sum(result["field_api_calls"].values())
    control_replay = verify(inp["meta"], log) if proc.returncode == 10 else None
    return {"degree": spec["degree"], "mode": inp["mode"],
            "variant": variant, "curve_id": inp["curve_id"],
            "workload_id": inp["workload_id"], "isogeny": "none",
            "factor_base_actual_B": inp["factor_base_actual_B"],
            "factor_base_folded_columns_K": inp["factor_base_folded_columns_K"],
            "factor_base_enumerated_set_sha256": inp[
                "factor_base_enumerated_set_sha256"],
            "conflict_cap": cap, "wall_cap_seconds": wall,
            "api_budget": budget, "exit_code": proc.returncode,
            "status_label": ("ALGEBRAIC_MODEL" if proc.returncode == 10 else
                             "UNSAT" if proc.returncode == 20 else
                             "BOUNDED_UNKNOWN"),
            "field_api_method_entries": api,
            "field_api_method_entries_log2": math.log2(api),
            "linear_halftrace_basis_xors": result.get("linear_halftrace", {}).get(
                "basis_xors", 0),
            "process_wall_seconds": elapsed, "log": log.name,
            "log_sha256": sha(log), "result": result,
            "s3_verification": control_replay,
            "group_relation_verification": None}


def main() -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["proposal_id"] == "Q1450"
    assert not (HERE / "freeze.json").exists()
    assert not (HERE / "measurements.json").exists()
    inputs = {str(spec["degree"]):
              {mode: input_row(spec, mode) for mode in ("control", "ordinary")}
              for spec in protocol["fields"]}
    source_paths = {
        "linear_oracle": HERE / "s3_root_oracle_linear.py",
        "linear_solver": HERE / "insearch.cpp",
        "linear_build": HERE / "build.sh",
        "base_oracle": STAGE / "s3_root_oracle.py",
        "base_solver": BASE / "insearch.cpp",
        "base_build": BASE / "build.sh",
        "counted_field": STAGE / "q20261011_operation_account/counted_onb.py",
        "field": ROOT / "ecc2k130/codegen/field.py",
        "runner": Path(__file__),
        "validator": HERE / "validate_linear.py",
    }
    freeze = {
        "proposal_id": "Q1450", "candidate_id": None, "run_id": None,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "sources_sha256": {name: sha(path) for name, path in source_paths.items()},
        "binaries_sha256": {"base": sha(BASE_BINARY),
                            "linear": sha(LINEAR_BINARY)},
        "inputs": inputs,
    }
    (HERE / "freeze.json").write_text(json.dumps(freeze, indent=2,
                                                   sort_keys=True) + "\n")
    controls = []
    for spec in protocol["fields"]:
        row = run_one(spec, inputs[str(spec["degree"])]["control"],
                      "linear", protocol)
        assert row["status_label"] == "ALGEBRAIC_MODEL"
        assert row["s3_verification"]["status"] == "verified_s3"
        controls.append(row)
    ordinary = []
    for name in protocol["comparison_order"]:
        degree, variant = name[1:].split("_")
        spec = next(s for s in protocol["fields"] if s["degree"] == int(degree))
        row = run_one(spec, inputs[degree]["ordinary"], variant, protocol)
        ordinary.append(row)
        print(json.dumps({"degree": row["degree"], "variant": variant,
                          "status": row["status_label"],
                          "api": row["field_api_method_entries"],
                          "basis_xors": row["linear_halftrace_basis_xors"],
                          "root_queries": row["result"]["root_queries"],
                          "final_checks": row["result"]["final_link_checks"]},
                         sort_keys=True), flush=True)
    for degree in (53, 83):
        base, linear = [next(row for row in ordinary if row["degree"] == degree
                             and row["variant"] == variant)
                        for variant in ("base", "linear")]
        for key in ("root_queries", "final_link_checks", "final_link_matches",
                    "conflicts", "solver_decisions"):
            assert base["result"][key] == linear["result"][key], (degree, key)
    receipt = {
        "proposal_id": "Q1450", "candidate_id": None, "run_id": None,
        "isogeny": "none", "freeze_sha256": sha(HERE / "freeze.json"),
        "controls": controls, "ordinary_attempts": ordinary,
        "complete_solve_work_log2": None,
        "degree131_challenge_gap_bits": None}
    (HERE / "measurements.json").write_text(json.dumps(receipt, indent=2,
                                                        sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
