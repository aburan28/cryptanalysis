#!/usr/bin/env python3
"""Test Q1490's ordinary N53 witness against Q1482's frozen native CNF."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = PARENT.parents[1]
sys.path.insert(0, str(PARENT / "q1420_root_theory"))
sys.path.insert(0, str(PARENT / "q1482_window_s3"))

from build_formula import build_cnf  # noqa: E402
from verify_model import model_relation  # noqa: E402
from q1420_root_theory.verify_archive import (  # noqa: E402
    check_cnf, model_from_file,
)


DESIGN = HERE / "design_protocol.json"
PROTOCOL = HERE / "protocol.json"
OUT = HERE / "runs/r1"
Q1482 = PARENT / "q1482_window_s3"
Q1490 = PARENT / "q1490_ordinary_witness_bridge"
INPUT_PATHS = {
    "q1490_bridge_result": Q1490 / "runs/r2/bridge_result.json",
    "q1490_recovery_protocol": Q1490 / "recovery_protocol.json",
    "q1482_ordinary_input": Q1482 / "inputs/n53_ordinary/input.json",
    "q1482_ordinary_cnf_gz": Q1482 / "inputs/n53_ordinary/system.cnf.gz",
    "q1482_ordinary_variables": Q1482 / "inputs/n53_ordinary/variables.txt",
    "q1482_ordinary_targets": Q1482 / "inputs/n53_ordinary/targets.txt",
    "q1482_protocol": Q1482 / "protocol.json",
    "q1482_formula_source": Q1482 / "build_formula.py",
    "q1482_verifier_source": Q1482 / "verify_model.py",
    "q1480_native_solver": PARENT / "q1480_conditioned_join/native_solver",
    "n53_field": PARENT / "q1420_root_theory/n53_field.txt",
    "sage_runtime_info": HERE / "sage_runtime_info.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_and_check() -> tuple[dict, dict, dict, dict]:
    design = json.loads(DESIGN.read_text())
    protocol = json.loads(PROTOCOL.read_text())
    witness = json.loads(INPUT_PATHS["q1490_bridge_result"].read_text())
    parent = json.loads(INPUT_PATHS["q1482_ordinary_input"].read_text())
    parent_protocol = json.loads(INPUT_PATHS["q1482_protocol"].read_text())
    assert design["proposal_id"] == protocol["proposal_id"] == "Q1491"
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
    assert witness["status"] == "PASS" and witness[
        "attempt_id"] == "Q1490R2"
    assert witness["protocol_sha256"] == sha(INPUT_PATHS[
        "q1490_recovery_protocol"])
    assert witness["q1482_target_preimage_index"] == 141
    assert len(witness["four_raw_lifts"]) == 4
    assert len(witness["raw_pair_mid_x_normal_basis_coordinates"]) == 2
    assert witness["three_direct_s3_links_zero"] is True
    assert witness["three_independent_root_memberships"] is True
    for row in (witness, parent):
        assert row["curve_id"] == design["curve_id"]
        assert row["factor_base_actual_B"] == design[
            "factor_base_actual_B"]
        assert row["factor_base_enumerated_set_sha256"] == design[
            "factor_base_enumerated_set_sha256"]
    assert witness["factor_base_folded_columns_K"] == parent[
        "folded_columns_K"] == design["factor_base_folded_columns_K"]
    entry = parent_protocol["cases"]["n53_ordinary"]
    assert entry["stage_config_id"] == design["parent_stage_config_id"]
    assert entry["workload_id"] == design["parent_workload_id"]
    assert parent_protocol["solver_binary_sha256"] == sha(INPUT_PATHS[
        "q1480_native_solver"])
    assert parent_protocol["field_file_sha256"]["53"] == sha(INPUT_PATHS[
        "n53_field"])
    assert design["decision_policy"] == parent_protocol[
        "decision_policy"]
    assert design["pair_candidate_cap"] == parent_protocol[
        "pair_candidate_cap"]
    return design, protocol, witness, parent


def original_formula(parent: dict):
    raw, varmap, targets, formula, meta, variables, clauses = build_cnf(
        53, "ordinary")
    assert hashlib.sha256(raw).hexdigest() == parent["cnf_raw_sha256"]
    assert gzip.decompress(INPUT_PATHS["q1482_ordinary_cnf_gz"].read_bytes()) == raw
    assert varmap == INPUT_PATHS["q1482_ordinary_variables"].read_bytes()
    assert targets == INPUT_PATHS["q1482_ordinary_targets"].read_bytes()
    assert variables == parent["cnf_variables"] == 51155
    assert clauses == parent["cnf_clauses"] == 215803
    assert meta["public_target"] == parent["public_target"]
    assert meta["target_preimage_x_count"] == parent[
        "target_preimage_x_count"] == 428
    return raw, formula, meta, variables, clauses


def witness_pins(meta: dict, witness: dict) -> list[int]:
    leaves = [row["raw_x_normal_basis_coordinates"]
              for row in witness["four_raw_lifts"]]
    mids = witness["raw_pair_mid_x_normal_basis_coordinates"]
    choice = witness["q1482_target_preimage_index"]
    bit_groups = (list(zip(meta["leaf_variables"], leaves)) +
                  list(zip(meta["pair_mid_variables"], mids)) +
                  [(meta["target_selector_variables"], choice)])
    assert len(bit_groups) == 7
    pins = []
    for bits, value in bit_groups:
        assert 0 <= value < (1 << len(bits))
        pins.extend(var if (value >> position) & 1 else -var
                    for position, var in enumerate(bits))
    assert len(pins) == 327 == len({abs(lit) for lit in pins})
    return pins


def pinned_cnf(raw: bytes, variables: int, clauses: int,
               pins: list[int]) -> bytes:
    header, separator, body = raw.partition(b"\n")
    assert separator and header == f"p cnf {variables} {clauses}".encode()
    assert body.count(b"\n") == clauses
    return (f"p cnf {variables} {clauses + len(pins)}\n".encode() + body +
            b"".join(f"{lit} 0\n".encode() for lit in pins))


def verify_model(path: Path, raw: bytes, pinned: bytes, formula,
                 meta: dict, variables: int, clauses: int,
                 pins: list[int], witness: dict) -> dict:
    model = model_from_file(path)
    check_cnf(pinned, model, variables, clauses + len(pins))
    assert all(model[abs(lit)] == (lit > 0) for lit in pins)
    relation = model_relation(raw, formula, meta, variables, clauses, path)
    assert relation["status"] == "verified_four_point_relation"
    assert relation["raw_leaf_x_coordinates"] == [
        row["raw_x_normal_basis_coordinates"]
        for row in witness["four_raw_lifts"]]
    assert relation["selected_raw_target_index"] == witness[
        "q1482_target_preimage_index"]
    assert relation["public_target"] == witness["ordinary_public_target"]
    return relation


def run() -> None:
    design, protocol, witness, parent = load_and_check()
    raw, formula, meta, variables, clauses = original_formula(parent)
    pins = witness_pins(meta, witness)
    pinned = pinned_cnf(raw, variables, clauses, pins)
    assert not (OUT / "receipt.json").exists()
    cnf_path = OUT / "pinned.cnf"
    model_path = OUT / "solver.model.txt"
    stdout_path = OUT / "solver.stdout.txt"
    stderr_path = OUT / "solver.stderr.txt"
    for path in (cnf_path, model_path, stdout_path, stderr_path):
        assert not path.exists(), path
    OUT.mkdir(parents=True, exist_ok=True)
    cnf_path.write_bytes(pinned)
    command = [str(INPUT_PATHS["q1480_native_solver"]),
               str(INPUT_PATHS["n53_field"]), str(cnf_path),
               str(INPUT_PATHS["q1482_ordinary_variables"]),
               str(model_path), str(design["conflict_cap"]),
               str(design["native_wall_cap_seconds"]),
               str(INPUT_PATHS["q1482_ordinary_targets"]),
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
                                    variables, clauses, pins, witness)
        except Exception as error:
            verification_error = repr(error)
    receipt = {
        "kind": "q1491_ordinary_n53_cnf_witness_run",
        "proposal_id": "Q1491", "candidate_id": None,
        "run_id": None, "isogeny": "none", "attempt_id": "Q1491R1",
        "curve_id": design["curve_id"], "field_degree_n": 53,
        "factor_base_actual_B": design["factor_base_actual_B"],
        "factor_base_folded_columns_K": design[
            "factor_base_folded_columns_K"],
        "factor_base_enumerated_set_sha256": design[
            "factor_base_enumerated_set_sha256"],
        "parent_workload_id": design["parent_workload_id"],
        "input_law": design["input_law"],
        "original_cnf_sha256": hashlib.sha256(raw).hexdigest(),
        "pinned_cnf_sha256": hashlib.sha256(pinned).hexdigest(),
        "pin_count": len(pins),
        "native_status": native_status, "native_exit_code": exit_code,
        "native_report": report,
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
        "status": ("PASS" if relation is not None else
                   "MODEL_REJECTED" if verification_error else native_status),
        "known_witness_control_only": True,
        "successful_unpinned_solver_cost": None,
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "design_sha256": sha(DESIGN),
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "q1490_bridge_result_sha256": sha(INPUT_PATHS[
            "q1490_bridge_result"]),
        "runtime_info_sha256": sha(INPUT_PATHS["sage_runtime_info"]),
    }
    (OUT / "receipt.json").write_text(json.dumps(
        receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "native_status": native_status,
                      "conflicts": (report or {}).get("conflicts"),
                      "propagations": (report or {}).get("propagations")},
                     sort_keys=True))


def check() -> None:
    design, protocol, witness, parent = load_and_check()
    assert design["proposal_id"] == protocol["proposal_id"]
    receipt = json.loads((OUT / "receipt.json").read_text())
    assert receipt["source_sha256"] == sha(Path(__file__))
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["q1490_bridge_result_sha256"] == sha(INPUT_PATHS[
        "q1490_bridge_result"])
    for name in ("stdout", "stderr"):
        assert receipt[f"solver_{name}_sha256"] == sha(
            OUT / f"solver.{name}.txt")
    raw, formula, meta, variables, clauses = original_formula(parent)
    pins = witness_pins(meta, witness)
    pinned = pinned_cnf(raw, variables, clauses, pins)
    assert receipt["pinned_cnf_sha256"] == hashlib.sha256(pinned).hexdigest()
    assert receipt["pin_count"] == len(pins)
    if receipt["status"] == "PASS":
        model_path = OUT / "solver.model.txt"
        assert receipt["solver_model_sha256"] == sha(model_path)
        relation = verify_model(model_path, raw, pinned, formula, meta,
                                variables, clauses, pins, witness)
        assert relation == receipt["independent_model_check"]
    else:
        assert receipt["independent_model_check"] is None
    print(f"Q1491 ordinary CNF witness archive: {receipt['status']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    check() if args.check else run()


if __name__ == "__main__":
    main()
