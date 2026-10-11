#!/usr/bin/env python3
"""Run the frozen Q1449 N83 control and one ordinary W<=6 attempt."""

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
sys.path.insert(0, str(STAGE))
from chain_s3 import evaluate_s3, field  # noqa: E402

BINARY = Path("/private/tmp/q1443_insearch")
PARENT = STAGE / "q20261011_api_budget_stop"
BASELINE = PARENT / "measurements.json"
PRIOR = STAGE / "q20261011_seed_budget_screen/measurements.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_inputs(inputs: dict) -> None:
    for row in inputs["formula_rows"]:
        for stem in ("cnf", "xcnf", "map", "target"):
            path = Path(row[f"{stem}_file"])
            assert sha(path) == row[f"{stem}_sha256" if stem != "target"
                                    else "target_file_sha256"]
    assert sha(HERE / "protocol.json") == inputs["protocol_sha256"]
    assert sha(HERE / "prepare.py") == inputs["prepare_source_sha256"]
    assert sha(STAGE / "chain_s3_balanced_multitarget.py") == inputs[
        "builder_source_sha256"]
    assert sha(STAGE / "q20261010_insearch_root/prepare.py") == inputs[
        "lowering_source_sha256"]
    assert sha(STAGE / "run_q1325_full_weight5_probe.py") == inputs[
        "pin_source_sha256"]
    assert sha(Path(field.__file__)) == inputs["field_source_sha256"]


def verify_s3(row: dict, log: Path) -> dict:
    lines = log.read_text().splitlines()
    assert json.loads(lines[0])["status"] == 10
    literals = [int(x) for x in lines[1].split()[1:-1]]
    mapping = [[int(x) for x in line.split()]
               for line in Path(row["map_file"]).read_text().splitlines()[1:]]
    assert len(mapping) == 6 and all(len(ids) == 83 for ids in mapping)
    assert len(literals) == 6 * 83
    values = []
    for index, ids in enumerate(mapping):
        assigned = literals[index * 83:(index + 1) * 83]
        assert all(abs(lit) == var for lit, var in zip(assigned, ids))
        values.append(sum((lit > 0) << bit for bit, lit in enumerate(assigned)))
    onb = field.Onb(83)
    x = [onb.fromCoords(value) for value in values]
    assert all(value.bit_count() <= 6 for value in values[:4])
    for a, b, c in ((0, 1, 4), (2, 3, 5)):
        assert evaluate_s3(onb, x[a], x[b], x[c]) == 0
    compatible = [value for value in row["raw_target_preimage_x_coordinates"]
                  if evaluate_s3(onb, x[4], x[5],
                                 onb.fromCoords(value)) == 0]
    assert compatible
    if row["mode"] == "control":
        assert values[:4] == row["fixture_raw_leaf_x"]
    return {"status": "verified_s3", "leaf_x_coordinates": values[:4],
            "middle_x_coordinates": values[4:],
            "compatible_target_x_coordinates": compatible}


def run_one(row: dict, protocol: dict) -> dict:
    mode = row["mode"]
    params = protocol["point_decomposition"]
    control = mode == "control"
    budget = (params["control_field_api_entry_budget"] if control else
              params["ordinary_field_api_entry_budget"])
    cap = (params["control_conflict_cap"] if control else
           params["ordinary_conflict_cap"])
    wall = (params["control_wall_cap_seconds"] if control else
            params["ordinary_wall_cap_seconds"])
    seed = params["control_seed"] if control else params["ordinary_seed"]
    cmd = [str(BINARY), row["cnf_file"], row["map_file"],
           row["target_file"], str(STAGE), str(ROOT / "ecc2k130/codegen"),
           params["branch_policy"], str(seed), params["root_encoding"],
           params["early_target_mode"], str(params["early_support_cap"]),
           params["leaf_rationality_mode"],
           str(protocol["factor_base"]["normal_basis_weight_bound"]),
           str(cap), str(wall),
           str(budget)]
    start = time.monotonic()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          timeout=protocol["limits"]["external_process_timeout_seconds"],
                          check=False)
    elapsed = time.monotonic() - start
    log = HERE / f"{mode}.log"
    log.write_text(proc.stdout)
    if proc.stderr:
        (HERE / f"{mode}.stderr.log").write_text(proc.stderr)
    assert proc.returncode in (0, 10, 20), proc.stderr
    result = json.loads(proc.stdout.splitlines()[0])
    assert result["status"] == proc.returncode
    assert result["api_budget"] == budget
    events = sum(result["field_api_calls"].values())
    verification = verify_s3(row, log) if proc.returncode == 10 else None
    return {
        "mode": mode, "seed": seed, "curve_id": row["curve_id"],
        "workload_id": row["workload_id"], "isogeny": "none",
        "factor_base_actual_B": None, "factor_base_folded_columns_K": None,
        "factor_base_enumerated_set_sha256": None,
        "leaf_weight_bound": 6, "cnf_sha256": row["cnf_sha256"],
        "target_file_sha256": row["target_file_sha256"],
        "api_budget": budget, "conflict_cap": cap, "wall_cap_seconds": wall,
        "process_wall_seconds": elapsed, "exit_code": proc.returncode,
        "status_label": ("ALGEBRAIC_MODEL" if proc.returncode == 10 else
                         "UNSAT" if proc.returncode == 20 else
                         "BOUNDED_UNKNOWN"),
        "field_api_method_entry_events": events,
        "field_api_method_entry_log2": math.log2(events) if events else None,
        "log": log.name, "log_sha256": sha(log),
        "result": result, "s3_verification": verification,
        "group_relation_verification": None,
    }


def main() -> None:
    inputs = json.loads((HERE / "inputs.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert inputs["proposal_id"] == protocol["proposal_id"] == "Q1449"
    assert not (HERE / "freeze.json").exists()
    assert not (HERE / "measurements.json").exists()
    check_inputs(inputs)
    baseline = json.loads(BASELINE.read_text())
    prior = json.loads(PRIOR.read_text())
    matched = next(row for row in baseline["attempts"]
                   if row["degree"] == 83 and row["mode"] == "ordinary"
                   and row["seed"] == 8 and row["early_limit"] == 1)
    assert matched["curve_id"] == protocol["curve_id"]
    assert matched["workload_id"] == protocol["ordinary_workload_id"]
    assert matched["api_budget"] == 500000
    freeze = {
        "proposal_id": "Q1449", "candidate_id": None, "run_id": None,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "inputs_sha256": sha(HERE / "inputs.json"),
        "runner_sha256": sha(Path(__file__)),
        "binary_sha256": sha(BINARY),
        "solver_source_sha256": sha(PARENT / "insearch.cpp"),
        "build_script_sha256": sha(PARENT / "build.sh"),
        "counted_field_source_sha256": sha(
            STAGE / "q20261011_operation_account/counted_onb.py"),
        "matched_weight5_measurements_sha256": sha(BASELINE),
        "prior_campaign_measurements_sha256": sha(PRIOR),
        "operation_boundary": protocol["comparison"]["operation_unit"],
        "matched_weight5_api_entries": matched[
            "field_api_method_entry_events"],
        "matched_weight5_final_link_checks": matched["result"][
            "final_link_checks"],
    }
    (HERE / "freeze.json").write_text(json.dumps(freeze, indent=2,
                                                   sort_keys=True) + "\n")
    rows = [run_one(row, protocol) for row in inputs["formula_rows"]]
    assert rows[0]["status_label"] == "ALGEBRAIC_MODEL"
    assert rows[0]["s3_verification"]["status"] == "verified_s3"
    prior_campaign = next(row for row in prior["cumulative_campaigns"]
                          if row["degree"] == 83)
    cumulative = prior_campaign["cumulative_api_events"] + rows[1][
        "field_api_method_entry_events"]
    receipt = {
        "proposal_id": "Q1449", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"],
        "ordinary_workload_id": protocol["ordinary_workload_id"],
        "isogeny": "none", "factor_base_actual_B": None,
        "factor_base_folded_columns_K": None,
        "factor_base_enumerated_set_sha256": None,
        "freeze_sha256": sha(HERE / "freeze.json"),
        "control": rows[0], "ordinary_attempt": rows[1],
        "matched_weight5_api_entries": matched[
            "field_api_method_entry_events"],
        "matched_weight5_final_link_checks": matched["result"][
            "final_link_checks"],
        "prior_same_point_sat_api_entries": prior_campaign[
            "cumulative_api_events"],
        "new_same_point_sat_api_entries": rows[1][
            "field_api_method_entry_events"],
        "cumulative_same_point_sat_api_entries": cumulative,
        "cumulative_same_point_sat_api_log2": math.log2(cumulative),
        "complete_solve_work_log2": None,
        "degree131_challenge_gap_bits": None,
    }
    (HERE / "measurements.json").write_text(json.dumps(receipt, indent=2,
                                                        sort_keys=True) + "\n")
    print(json.dumps({"control": rows[0]["status_label"],
                      "ordinary": rows[1]["status_label"],
                      "ordinary_api_entries": rows[1][
                          "field_api_method_entry_events"],
                      "ordinary_final_checks": rows[1]["result"][
                          "final_link_checks"]}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
