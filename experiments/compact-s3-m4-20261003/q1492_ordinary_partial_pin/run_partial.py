#!/usr/bin/env python3
"""Locate search difficulty using partial pins on Q1482's ordinary CNF."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1491 = PARENT / "q1491_ordinary_cnf_witness"
sys.path.insert(0, str(Q1491))
import run as q1491  # noqa: E402


DESIGN = HERE / "design_protocol.json"
PROTOCOL = HERE / "protocol.json"
INPUT_PATHS = {
    "q1491_design": Q1491 / "design_protocol.json",
    "q1491_protocol": Q1491 / "protocol.json",
    "q1491_run_source": Q1491 / "run.py",
    "q1491_pinned_receipt": Q1491 / "runs/r1/receipt.json",
    "q1490_bridge_result": PARENT / "q1490_ordinary_witness_bridge/runs/r2/bridge_result.json",
    "sage_runtime_info": HERE / "sage_runtime_info.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_and_check() -> tuple[dict, dict, dict, dict]:
    design = json.loads(DESIGN.read_text())
    protocol = json.loads(PROTOCOL.read_text())
    assert design["proposal_id"] == protocol["proposal_id"] == "Q1492"
    assert design["candidate_id"] is protocol["candidate_id"] is None
    assert design["run_id"] is protocol["run_id"] is None
    assert design["isogeny"] == protocol["isogeny"] == "none"
    assert protocol["design_sha256"] == sha(DESIGN)
    assert protocol["source_sha256"] == sha(Path(__file__))
    for label, path in INPUT_PATHS.items():
        expected = design["frozen_inputs_sha256"][label]
        assert sha(path) == expected == protocol["frozen_inputs_sha256"][label], label
    assert json.loads(INPUT_PATHS["sage_runtime_info"].read_text())[
        "status"] == "verified"
    parent_design, parent_protocol, witness, original = q1491.load_and_check()
    parent_receipt = json.loads(INPUT_PATHS[
        "q1491_pinned_receipt"].read_text())
    assert parent_design["proposal_id"] == parent_protocol[
        "proposal_id"] == "Q1491"
    assert parent_receipt["status"] == "PASS"
    assert parent_receipt["source_sha256"] == sha(INPUT_PATHS[
        "q1491_run_source"])
    assert parent_receipt["q1490_bridge_result_sha256"] == sha(
        INPUT_PATHS["q1490_bridge_result"])
    assert witness["q1482_target_preimage_index"] == design[
        "target_preimage_index"] == 141
    assert witness["curve_id"] == original["curve_id"] == design[
        "curve_id"]
    assert witness["factor_base_actual_B"] == design[
        "factor_base_actual_B"]
    assert witness["factor_base_folded_columns_K"] == design[
        "factor_base_folded_columns_K"]
    assert witness["factor_base_enumerated_set_sha256"] == design[
        "factor_base_enumerated_set_sha256"]
    assert parent_receipt["parent_workload_id"] == design[
        "parent_workload_id"]
    return design, protocol, witness, original


def cell_pins(meta: dict, witness: dict, cell: dict) -> list[int]:
    selector = meta["target_selector_variables"]
    choice = witness["q1482_target_preimage_index"]
    groups = [(selector, choice)]
    mids = witness["raw_pair_mid_x_normal_basis_coordinates"]
    if cell["pin_first_mid"]:
        groups.append((meta["pair_mid_variables"][0], mids[0]))
    if cell["pin_second_mid"]:
        groups.append((meta["pair_mid_variables"][1], mids[1]))
    pins = []
    for bits, value in groups:
        assert 0 <= value < (1 << len(bits))
        pins.extend(var if (value >> position) & 1 else -var
                    for position, var in enumerate(bits))
    assert len(pins) == cell["expected_pin_count"]
    assert len({abs(lit) for lit in pins}) == len(pins)
    return pins


def verify_model(path: Path, raw: bytes, pinned: bytes, formula,
                 meta: dict, variables: int, clauses: int,
                 pins: list[int]) -> dict:
    model = q1491.model_from_file(path)
    q1491.check_cnf(pinned, model, variables, clauses + len(pins))
    assert all(model[abs(lit)] == (lit > 0) for lit in pins)
    return q1491.model_relation(raw, formula, meta, variables, clauses,
                                path)


def run(cell_name: str) -> None:
    design, protocol, witness, original = load_and_check()
    cell = next(row for row in design["cells"] if row["name"] == cell_name)
    assert cell == next(row for row in protocol["cells"]
                        if row["name"] == cell_name)
    raw, formula, meta, variables, clauses = q1491.original_formula(original)
    pins = cell_pins(meta, witness, cell)
    pinned = q1491.pinned_cnf(raw, variables, clauses, pins)
    output = HERE / "runs" / cell_name
    assert not output.exists(), "refusing to overwrite attempted cell"
    output.mkdir(parents=True)
    cnf_path = output / "pinned.cnf"
    model_path = output / "solver.model.txt"
    stdout_path = output / "solver.stdout.txt"
    stderr_path = output / "solver.stderr.txt"
    cnf_path.write_bytes(pinned)
    command = [str(q1491.INPUT_PATHS["q1480_native_solver"]),
               str(q1491.INPUT_PATHS["n53_field"]), str(cnf_path),
               str(q1491.INPUT_PATHS["q1482_ordinary_variables"]),
               str(model_path), str(design["conflict_cap"]),
               str(design["native_wall_cap_seconds"]),
               str(q1491.INPUT_PATHS["q1482_ordinary_targets"]),
               str(design["pair_candidate_cap"]),
               design["decision_policy"]]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.perf_counter_ns()
    try:
        completed = subprocess.run(command, capture_output=True, text=True,
                                   timeout=design[
                                       "external_safeguard_seconds"])
        exit_code = completed.returncode
        stdout, stderr = completed.stdout, completed.stderr
        native_status = {0: "sat", 10: "censored", 20: "unsat"}.get(
            exit_code, "error")
    except subprocess.TimeoutExpired as error:
        exit_code, native_status = None, "external_timeout"
        stdout = (error.stdout or b"").decode(errors="replace")
        stderr = (error.stderr or b"").decode(errors="replace")
    elapsed_ns = time.perf_counter_ns() - started
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    stdout_path.write_text(stdout)
    stderr_path.write_text(stderr)
    cnf_path.unlink()
    report = None
    if stdout.strip():
        try:
            report = json.loads(stdout)
        except json.JSONDecodeError:
            pass
    relation, verification_error = None, None
    if native_status == "sat" and model_path.exists():
        try:
            relation = verify_model(model_path, raw, pinned, formula, meta,
                                    variables, clauses, pins)
        except Exception as error:
            verification_error = repr(error)
    status = ("VERIFIED_RELATION" if relation is not None and
              relation.get("status") == "verified_four_point_relation"
              else "MODEL_REJECTED" if verification_error or relation is not None
              else native_status)
    receipt = {
        "kind": "q1492_ordinary_n53_partial_pin_run",
        "proposal_id": "Q1492", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "cell": cell_name,
        "curve_id": design["curve_id"], "field_degree_n": 53,
        "factor_base_actual_B": design["factor_base_actual_B"],
        "factor_base_folded_columns_K": design[
            "factor_base_folded_columns_K"],
        "factor_base_enumerated_set_sha256": design[
            "factor_base_enumerated_set_sha256"],
        "parent_workload_id": design["parent_workload_id"],
        "input_law": design["input_law"],
        "pin_policy": cell,
        "pin_count": len(pins),
        "original_cnf_sha256": hashlib.sha256(raw).hexdigest(),
        "pinned_cnf_sha256": hashlib.sha256(pinned).hexdigest(),
        "native_status": native_status, "native_exit_code": exit_code,
        "native_report": report, "status": status,
        "solver_process_wall_ns_exploratory": elapsed_ns,
        "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
        "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
        "peak_child_rss_raw": after.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "solver_stdout_sha256": sha(stdout_path),
        "solver_stderr_sha256": sha(stderr_path),
        "solver_model_sha256": sha(model_path) if model_path.exists()
                               else None,
        "independent_model_check": relation,
        "independent_model_check_error": verification_error,
        "verified_relation_count": int(status == "VERIFIED_RELATION"),
        "known_witness_partial_pin_control_only": True,
        "successful_unpinned_solver_cost": None,
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "design_sha256": sha(DESIGN),
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "q1491_pinned_receipt_sha256": sha(INPUT_PATHS[
            "q1491_pinned_receipt"]),
        "runtime_info_sha256": sha(INPUT_PATHS["sage_runtime_info"]),
    }
    (output / "receipt.json").write_text(json.dumps(
        receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cell": cell_name, "status": status,
                      "conflicts": (report or {}).get("conflicts"),
                      "propagations": (report or {}).get("propagations"),
                      "right_evaluations": (report or {}).get(
                          "conditioned_right_s3_evals")}, sort_keys=True))


def check(cell_name: str) -> None:
    design, protocol, witness, original = load_and_check()
    cell = next(row for row in design["cells"] if row["name"] == cell_name)
    receipt = json.loads((HERE / "runs" / cell_name /
                          "receipt.json").read_text())
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["source_sha256"] == sha(Path(__file__))
    assert receipt["cell"] == cell_name and receipt["pin_policy"] == cell
    output = HERE / "runs" / cell_name
    for name in ("stdout", "stderr"):
        assert receipt[f"solver_{name}_sha256"] == sha(
            output / f"solver.{name}.txt")
    raw, formula, meta, variables, clauses = q1491.original_formula(original)
    pins = cell_pins(meta, witness, cell)
    pinned = q1491.pinned_cnf(raw, variables, clauses, pins)
    assert receipt["pinned_cnf_sha256"] == hashlib.sha256(pinned).hexdigest()
    assert receipt["pin_count"] == len(pins)
    if receipt["native_status"] == "sat":
        model_path = output / "solver.model.txt"
        assert receipt["solver_model_sha256"] == sha(model_path)
        relation = verify_model(model_path, raw, pinned, formula, meta,
                                variables, clauses, pins)
        assert relation == receipt["independent_model_check"]
    else:
        assert receipt["solver_model_sha256"] is None
        assert receipt["independent_model_check"] is None
    print(f"Q1492 {cell_name} archive: {receipt['status']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cell", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    check(args.cell) if args.check else run(args.cell)


if __name__ == "__main__":
    main()
