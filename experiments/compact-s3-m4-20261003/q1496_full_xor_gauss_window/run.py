#!/usr/bin/env python3
"""Frozen bounded-Gauss rerun of Q1494's exact full three-S3 XCNF."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import resource
import subprocess
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1494 = PARENT / "q1494_full_xor_window_s3"
SPEC = importlib.util.spec_from_file_location("q1494_run", Q1494 / "run.py")
assert SPEC is not None and SPEC.loader is not None
q1494 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(q1494)

DESIGN = HERE / "design_protocol.json"
PROTOCOL = HERE / "protocol.json"
INPUTS = {
    "q1494_design": Q1494 / "design_protocol.json",
    "q1494_protocol": Q1494 / "protocol.json",
    "q1494_runner": Q1494 / "run.py",
    "q1494_control_receipt": Q1494 / "control/r1/receipt.json",
    "cms_binary": q1494.INPUTS["cms_binary"],
    "sage_runtime_info": HERE / "sage_runtime_info.json",
}
for cell in ("n53_known_rotation_44", "n53_ordinary_rotation_0",
             "n83_ordinary_rotation_0"):
    INPUTS[f"q1494_{cell}_receipt"] = Q1494 / f"runs/{cell}/receipt.json"


def sha(path: Path) -> str:
    return q1494.sha(path)


def load_and_check() -> tuple[dict, dict]:
    design = json.loads(DESIGN.read_text())
    protocol = json.loads(PROTOCOL.read_text())
    assert design["proposal_id"] == protocol["proposal_id"] == "Q1496"
    assert design["candidate_id"] is protocol["candidate_id"] is None
    assert design["run_id"] is protocol["run_id"] is None
    assert design["isogeny"] == protocol["isogeny"] == "none"
    assert design["degree_profiles"] == protocol["degree_profiles"]
    assert design["run_order"] == protocol["run_order"]
    assert design["runs"] == protocol["runs"]
    assert protocol["design_sha256"] == sha(DESIGN)
    assert protocol["runner_source_sha256"] == sha(Path(__file__))
    for label, path in INPUTS.items():
        assert protocol["input_sha256"][label] == sha(path), label
    assert json.loads(INPUTS["sage_runtime_info"].read_text())[
        "status"] == "verified"
    parent_design, _ = q1494.load_and_check()
    assert design["degree_profiles"] == parent_design["degree_profiles"]
    assert design["run_order"] == parent_design["run_order"]
    assert design["runs"] == parent_design["runs"]
    return design, protocol


def solver_options(design: dict, cap: int) -> list[str]:
    setting = design["matrix_settings"]
    assert setting["auto_disable_gauss"] is False
    return ["--verb", "1", "--threads", "1", "--maxtime", str(cap),
            "--maxconfl", str(design["conflict_cap"]),
            "--maxmatrixcols", str(setting["max_matrix_columns"]),
            "--maxmatrixrows", str(setting["max_matrix_rows"]),
            "--maxnummatrices", str(setting["max_matrices"]),
            "--autodisablegauss", "0"]


def matrix_log(stdout: str) -> dict:
    counts = [int(value) for value in re.findall(
        r"\[matrix\] Using (\d+) matrices recovered from", stdout)]
    good = [(int(rows), int(columns)) for rows, columns in re.findall(
        r"\[matrix\] Good\s+matrix\s+\d+\s+(\d+)\s*x\s*(\d+)", stdout)]
    rejected = [(int(rows), int(columns)) for rows, columns in re.findall(
        r"\[matrix\] UNused matrix\s+(\d+)\s*x\s*(\d+)", stdout)]
    return {
        "initial_matrix_count": counts[0] if counts else None,
        "maximum_matrix_count": max(counts) if counts else None,
        "last_matrix_count": counts[-1] if counts else None,
        "matrix_initializations": len(counts),
        "maximum_good_matrix_columns": max((cols for _, cols in good),
                                           default=None),
        "first_good_dimensions": [list(value) for value in good[:8]],
        "first_rejected_dimensions": [list(value) for value in rejected[:8]],
        "too_many_columns_messages": stdout.count("Too many columns in matrix"),
        "too_many_rows_messages": stdout.count("Too many rows in matrix"),
    }


def counter_display(stdout: str) -> dict[str, str | None]:
    result = {}
    for name in ("conflicts", "decisions", "propagations", "restarts"):
        match = re.findall(rf"^c {name}\s*:\s*(\S+)", stdout, re.MULTILINE)
        result[name] = match[-1] if match else None
    return result


def build(name: str, control: bool, design: dict):
    spec = design["runs"][name]
    n, k = spec["degree_n"], spec["rotation"]
    profile = next(item for item in design["degree_profiles"]
                   if item["field_degree_n"] == n)
    formula, meta, original_q, rotated_q, selected, original_hash, first_hash = (
        q1494.build_full_formula(n, k, profile))
    pins = []
    if control:
        assert name == "n53_known_rotation_44"
        witness = json.loads(q1494.INPUTS["q1490_witness"].read_text())
        pins = q1494.rotated_witness_pins(meta, witness, k)
        formula.clauses.extend([[literal] for literal in pins])
    parent_file = (INPUTS["q1494_control_receipt"] if control else
                   INPUTS[f"q1494_{name}_receipt"])
    parent = json.loads(parent_file.read_text())
    assert parent["curve_id"] == profile["curve_id"]
    assert parent["control_pins"] == len(pins)
    return (formula, meta, original_q, rotated_q, selected, original_hash,
            first_hash, pins, profile, parent)


def execute(name: str, control: bool) -> dict:
    design, _ = load_and_check()
    spec = design["runs"][name]
    output = HERE / ("control/r1" if control else f"runs/{name}")
    assert not output.exists(), "refusing to overwrite a previous attempt"
    output.mkdir(parents=True)
    build_started = time.perf_counter_ns()
    (formula, meta, original_q, rotated_q, selected, original_hash,
     first_hash, pins, profile, parent) = build(name, control, design)
    path = output / "system.xcnf"
    formula.write(path)
    formula_hash, formula_bytes = sha(path), path.stat().st_size
    assert formula_hash == parent["full_xcnf_sha256"]
    assert formula_bytes == parent["full_xcnf_bytes"]
    build_ns = time.perf_counter_ns() - build_started
    cap = (design["control_wall_cap_seconds"] if control else
           spec["solver_wall_cap_seconds"])
    command = [str(INPUTS["cms_binary"]), *solver_options(design, cap),
               str(path)]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    process_started = time.perf_counter_ns()
    try:
        completed = subprocess.run(command, capture_output=True, text=True,
                                   timeout=cap + 15 if control else spec[
                                       "external_safeguard_seconds"])
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
    process_ns = time.perf_counter_ns() - process_started
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    (output / "solver.stdout.txt").write_text(stdout)
    (output / "solver.stderr.txt").write_text(stderr)
    model = q1494.parse_model(stdout)
    verify_started = time.perf_counter_ns()
    relation, error = None, None
    if model is not None:
        try:
            relation = q1494.verify_relation(model, formula, meta, original_q,
                                             rotated_q, spec["rotation"], selected)
            if control:
                assert all(model[abs(lit)] == (lit > 0) for lit in pins)
                assert relation["status"] == "verified_four_point_relation"
        except Exception as exc:
            error = repr(exc)
    verify_ns = time.perf_counter_ns() - verify_started
    path.unlink()
    status = ("verified_relation" if relation and relation["status"] ==
              "verified_four_point_relation" else "model_rejected" if model
              is not None else native_status)
    charged = build_ns + process_ns + verify_ns
    receipt = {
        "kind": "q1496_bounded_gauss_control" if control else
                "q1496_bounded_gauss_ordinary_attempt",
        "proposal_id": "Q1496", "candidate_id": None, "run_id": None,
        "isogeny": "none", "cell": name, "status": status,
        "native_status": native_status, "native_exit_code": exit_code,
        "curve_id": profile["curve_id"], "field_degree_n": spec["degree_n"],
        "factor_base_actual_B": profile["factor_base_actual_B"],
        "factor_base_folded_columns_K": profile["factor_base_folded_columns_K"],
        "factor_base_enumerated_set_sha256": profile[
            "factor_base_enumerated_set_sha256"],
        "parent_workload_id": profile["parent_workload_id"],
        "rotation": spec["rotation"], "first_window_zero": True,
        "known_satisfiable_from_q1490": spec["known_satisfiable_from_q1490"],
        "control_pins": len(pins),
        "original_public_target": list(original_q),
        "rotated_public_target": list(rotated_q),
        "q1482_original_cnf_sha256": original_hash,
        "q1493_first_window_cnf_sha256": first_hash,
        "full_xcnf_sha256": formula_hash,
        "q1494_matched_formula_sha256": parent["full_xcnf_sha256"],
        "full_xcnf_bytes": formula_bytes,
        "full_xcnf_variables": formula.variables,
        "full_xcnf_clauses": len(formula.clauses),
        "full_xcnf_xor_rows": len(formula.xors),
        "solver_command_options": solver_options(design, cap),
        "solver_counters": q1494.solver_counters(stdout),
        "solver_counter_display": counter_display(stdout),
        "matrix_log": matrix_log(stdout),
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
    output = HERE / ("control/r1" if control else f"runs/{name}")
    receipt = json.loads((output / "receipt.json").read_text())
    assert receipt["source_sha256"] == sha(Path(__file__))
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["solver_stdout_sha256"] == sha(output / "solver.stdout.txt")
    assert receipt["solver_stderr_sha256"] == sha(output / "solver.stderr.txt")
    (formula, meta, original_q, rotated_q, selected, original_hash,
     first_hash, pins, profile, parent) = build(name, control, design)
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "system.xcnf"
        formula.write(path)
        assert sha(path) == receipt["full_xcnf_sha256"] == parent[
            "full_xcnf_sha256"]
    assert receipt["q1482_original_cnf_sha256"] == original_hash
    assert receipt["q1493_first_window_cnf_sha256"] == first_hash
    assert receipt["full_xcnf_variables"] == formula.variables
    assert receipt["full_xcnf_clauses"] == len(formula.clauses)
    assert receipt["full_xcnf_xor_rows"] == len(formula.xors)
    assert receipt["control_pins"] == len(pins)
    assert receipt["charged_stage_ns"] == sum(receipt["phase_ns"].values())
    stdout = (output / "solver.stdout.txt").read_text()
    assert receipt["solver_counters"] == q1494.solver_counters(stdout)
    assert receipt["solver_counter_display"] == counter_display(stdout)
    assert receipt["matrix_log"] == matrix_log(stdout)
    model = q1494.parse_model(stdout)
    if model is None:
        assert receipt["verified_relation"] is None
        assert receipt["successful_unpinned_stage_ns_exploratory"] is None
    else:
        relation = q1494.verify_relation(model, formula, meta, original_q,
                                         rotated_q, design["runs"][name][
                                             "rotation"], selected)
        assert relation == receipt["verified_relation"]
        assert (receipt["status"] == "verified_relation") == (
            relation["status"] == "verified_four_point_relation")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cell", choices=json.loads(DESIGN.read_text())[
                        "run_order"])
    parser.add_argument("--control", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert args.cell or args.control
    name = "n53_known_rotation_44" if args.control else args.cell
    assert name is not None
    receipt = check(name, args.control) if args.check else execute(
        name, args.control)
    print(json.dumps({"cell": name, "status": receipt["status"],
                      "charged_stage_seconds": receipt["charged_stage_ns"] / 1e9,
                      "matrix_log": receipt["matrix_log"]}, sort_keys=True))


if __name__ == "__main__":
    main()
