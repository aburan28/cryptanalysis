#!/usr/bin/env python3
"""Rerun byte-identical Q1497 XCNFs with large Gaussian row admission."""

from __future__ import annotations

import argparse
import importlib.util
import json
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1497 = HERE.parent / "q1497_karatsuba_poly_xcnf"
sys.path.insert(0, str(Q1497))
SPEC = importlib.util.spec_from_file_location("q1497_run", Q1497 / "run.py")
assert SPEC is not None and SPEC.loader is not None
q1497 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(q1497)

DESIGN = HERE / "design_protocol.json"
PROTOCOL = HERE / "protocol.json"
INPUTS = {
    "q1497_design": Q1497 / "design_protocol.json",
    "q1497_protocol": Q1497 / "protocol.json",
    "q1497_runner": Q1497 / "run.py",
    "q1497_circuit": Q1497 / "karatsuba_circuit.py",
    "q1497_validation": Q1497 / "circuit_validation.json",
    "cms_binary": q1497.INPUTS["cms_binary"],
    "sage_runtime_info": HERE / "sage_runtime_info.json",
}
for folder, cell in (("control/n53_r1", "n53_known_rotation_44"),
                     ("control/n83_r1", "n83_planted_rotation_0"),
                     *((f"runs/{name}", name) for name in (
                         "n53_known_rotation_44", "n53_ordinary_rotation_0",
                         "n83_planted_rotation_0", "n83_ordinary_rotation_0"))):
    INPUTS[f"q1497_{cell}_{'control' if folder.startswith('control') else 'run'}_receipt"] = (
        Q1497 / folder / "receipt.json")


def sha(path: Path) -> str:
    return q1497.sha(path)


def folder_for(name: str, control: bool) -> str:
    if control:
        return f"control/n{53 if name.startswith('n53_') else 83}_r1"
    return f"runs/{name}"


def parent_receipt_path(name: str, control: bool) -> Path:
    return Q1497 / folder_for(name, control) / "receipt.json"


def load_and_check() -> tuple[dict, dict]:
    design = json.loads(DESIGN.read_text())
    protocol = json.loads(PROTOCOL.read_text())
    assert design["proposal_id"] == protocol["proposal_id"] == "Q1498"
    assert design["candidate_id"] is protocol["candidate_id"] is None
    assert design["run_id"] is protocol["run_id"] is None
    assert design["isogeny"] == protocol["isogeny"] == "none"
    assert design["degree_profiles"] == protocol["degree_profiles"]
    assert design["run_order"] == protocol["run_order"]
    assert design["runs"] == protocol["runs"]
    assert design["solver_matrix_settings"] == protocol[
        "solver_matrix_settings"]
    assert protocol["design_sha256"] == sha(DESIGN)
    assert protocol["runner_source_sha256"] == sha(Path(__file__))
    for label, path in INPUTS.items():
        assert protocol["input_sha256"][label] == sha(path), label
    assert json.loads(INPUTS["sage_runtime_info"].read_text())[
        "status"] == "verified"
    parent_design, _ = q1497.load_and_check()
    assert design["degree_profiles"] == parent_design["degree_profiles"]
    assert design["run_order"] == parent_design["run_order"]
    assert design["runs"] == parent_design["runs"]
    current = dict(design["solver_matrix_settings"])
    parent = dict(parent_design["solver_matrix_settings"])
    assert current.pop("max_matrix_rows") == 16384
    assert parent.pop("max_matrix_rows") == 512
    assert current == parent
    return design, protocol


def build(name: str, control: bool, design: dict):
    parent_design = json.loads(INPUTS["q1497_design"].read_text())
    assert design["runs"][name] == parent_design["runs"][name]
    return q1497.build(name, control, parent_design)


def execute(name: str, control: bool) -> dict:
    design, _ = load_and_check()
    spec = design["runs"][name]
    assert not control or spec["known_satisfiable"]
    output = HERE / folder_for(name, control)
    assert not output.exists(), "refusing to overwrite a previous attempt"
    output.mkdir(parents=True)
    parent = json.loads(parent_receipt_path(name, control).read_text())
    began = time.perf_counter_ns()
    formula, meta, original_q, rotated_q, selected, pins, profile = build(
        name, control, design)
    path = output / "system.xcnf"
    formula.write(path)
    formula_hash, formula_bytes = sha(path), path.stat().st_size
    assert formula_hash == parent["full_xcnf_sha256"]
    assert formula_bytes == parent["full_xcnf_bytes"]
    build_ns = time.perf_counter_ns() - began
    cap = (design["control_wall_cap_seconds"] if control else
           spec["solver_wall_cap_seconds"])
    options = q1497.solver_options(design, cap)
    command = [str(INPUTS["cms_binary"]), *options, str(path)]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    began = time.perf_counter_ns()
    try:
        completed = subprocess.run(command, capture_output=True, text=True,
                                   timeout=(cap + 15 if control else spec[
                                       "external_safeguard_seconds"]))
        stdout, stderr, exit_code = (completed.stdout, completed.stderr,
                                     completed.returncode)
        native_status = ("sat" if "s SATISFIABLE" in stdout else
                         "unsat" if "s UNSATISFIABLE" in stdout else
                         "censored" if "s INDETERMINATE" in stdout else
                         "error")
    except subprocess.TimeoutExpired as error:
        stdout = (error.stdout or b"").decode(errors="replace")
        stderr = (error.stderr or b"").decode(errors="replace")
        exit_code, native_status = None, "external_timeout"
    process_ns = time.perf_counter_ns() - began
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    (output / "solver.stdout.txt").write_text(stdout)
    (output / "solver.stderr.txt").write_text(stderr)
    model = q1497.q1494.parse_model(stdout)
    began = time.perf_counter_ns()
    relation, error = None, None
    if model is not None:
        try:
            relation = q1497.q1494.verify_relation(
                model, formula, meta, original_q, rotated_q, spec["rotation"],
                selected)
            if control:
                assert all(model[abs(lit)] == (lit > 0) for lit in pins)
                assert relation["status"] == "verified_four_point_relation"
        except Exception as exc:
            error = repr(exc)
    verify_ns = time.perf_counter_ns() - began
    path.unlink()
    status = ("verified_relation" if relation and relation["status"] ==
              "verified_four_point_relation" else "model_rejected" if model
              is not None else native_status)
    charged = build_ns + process_ns + verify_ns
    receipt = {
        "kind": "q1498_large_gauss_control" if control else
                "q1498_large_gauss_attempt",
        "proposal_id": "Q1498", "candidate_id": None, "run_id": None,
        "isogeny": "none", "cell": name, "target_role": spec["target_role"],
        "status": status, "native_status": native_status,
        "native_exit_code": exit_code,
        "curve_id": profile["curve_id"], "field_degree_n": spec["degree_n"],
        "factor_base_actual_B": profile["factor_base_actual_B"],
        "factor_base_folded_columns_K": profile[
            "factor_base_folded_columns_K"],
        "factor_base_enumerated_set_sha256": profile[
            "factor_base_enumerated_set_sha256"],
        "parent_workload_id": (profile["parent_workload_id"] if spec[
            "target_role"] == "ordinary" else None),
        "rotation": spec["rotation"], "first_window_zero": True,
        "known_satisfiable": spec["known_satisfiable"],
        "control_pins": len(pins),
        "original_public_target": list(original_q),
        "rotated_public_target": list(rotated_q),
        "full_xcnf_sha256": formula_hash,
        "q1497_matched_full_xcnf_sha256": parent["full_xcnf_sha256"],
        "full_xcnf_bytes": formula_bytes,
        "full_xcnf_variables": formula.variables,
        "full_xcnf_clauses": len(formula.clauses),
        "full_xcnf_xor_rows": len(formula.xors),
        "and_gates": len(formula.and_cache),
        "solver_command_options": options,
        "solver_counters": q1497.q1494.solver_counters(stdout),
        "solver_counter_display": q1497.q1496.counter_display(stdout),
        "matrix_log": q1497.q1496.matrix_log(stdout),
        "phase_ns": {"target_formula_build": build_ns,
                     "target_solver_process": process_ns,
                     "target_relation_check": verify_ns},
        "charged_stage_ns": charged,
        "charged_stage_wall_exploratory": True,
        "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
        "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
        "peak_child_rss_raw": after.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "solver_stdout_sha256": sha(output / "solver.stdout.txt"),
        "solver_stderr_sha256": sha(output / "solver.stderr.txt"),
        "verified_relation": relation,
        "verification_error": error,
        "successful_unpinned_stage_ns_exploratory": (charged if not control and
            status == "verified_relation" else None),
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "design_sha256": sha(DESIGN), "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "cms_binary_sha256": sha(INPUTS["cms_binary"]),
    }
    (output / "receipt.json").write_text(json.dumps(
        receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def check(name: str, control: bool) -> dict:
    design, _ = load_and_check()
    spec = design["runs"][name]
    output = HERE / folder_for(name, control)
    receipt = json.loads((output / "receipt.json").read_text())
    parent = json.loads(parent_receipt_path(name, control).read_text())
    assert receipt["source_sha256"] == sha(Path(__file__))
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["solver_stdout_sha256"] == sha(output / "solver.stdout.txt")
    assert receipt["solver_stderr_sha256"] == sha(output / "solver.stderr.txt")
    formula, meta, original_q, rotated_q, selected, pins, profile = build(
        name, control, design)
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "system.xcnf"
        formula.write(path)
        assert receipt["full_xcnf_sha256"] == sha(path) == parent[
            "full_xcnf_sha256"]
        assert receipt["full_xcnf_bytes"] == path.stat().st_size
    assert receipt["full_xcnf_variables"] == formula.variables
    assert receipt["full_xcnf_clauses"] == len(formula.clauses)
    assert receipt["full_xcnf_xor_rows"] == len(formula.xors)
    assert receipt["and_gates"] == len(formula.and_cache)
    assert receipt["control_pins"] == len(pins)
    assert receipt["charged_stage_ns"] == sum(receipt["phase_ns"].values())
    stdout = (output / "solver.stdout.txt").read_text()
    assert receipt["solver_counters"] == q1497.q1494.solver_counters(stdout)
    assert receipt["solver_counter_display"] == q1497.q1496.counter_display(
        stdout)
    assert receipt["matrix_log"] == q1497.q1496.matrix_log(stdout)
    model = q1497.q1494.parse_model(stdout)
    if model is None:
        assert receipt["verified_relation"] is None
        assert receipt["successful_unpinned_stage_ns_exploratory"] is None
    else:
        relation = q1497.q1494.verify_relation(
            model, formula, meta, original_q, rotated_q, spec["rotation"],
            selected)
        assert relation == receipt["verified_relation"]
        assert (receipt["status"] == "verified_relation") == (
            relation["status"] == "verified_four_point_relation")
    return receipt


def main() -> None:
    design = json.loads(DESIGN.read_text())
    parser = argparse.ArgumentParser()
    parser.add_argument("--cell", choices=design["run_order"], required=True)
    parser.add_argument("--control", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    receipt = check(args.cell, args.control) if args.check else execute(
        args.cell, args.control)
    print(json.dumps({"cell": args.cell, "status": receipt["status"],
                      "charged_stage_seconds": receipt[
                          "charged_stage_ns"] / 1e9,
                      "conflicts": receipt["solver_counters"]["conflicts"],
                      "matrix_log": receipt["matrix_log"]}, sort_keys=True))


if __name__ == "__main__":
    main()
