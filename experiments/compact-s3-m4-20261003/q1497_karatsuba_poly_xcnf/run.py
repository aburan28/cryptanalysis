#!/usr/bin/env python3
"""Build and run Q1497's full Karatsuba three-S3 decomposition stage."""

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
PARENT = HERE.parent
Q1496 = PARENT / "q1496_full_xor_gauss_window"
SPEC = importlib.util.spec_from_file_location("q1496_run", Q1496 / "run.py")
assert SPEC is not None and SPEC.loader is not None
q1496 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(q1496)
q1494 = q1496.q1494
q1493 = q1494.q1493
q1482 = q1493.q1482_formula
sys.path.insert(0, str(PARENT))

from chain_s3 import Formula, square_destinations  # noqa: E402
from chain_s3_multitarget import choose_target_x  # noqa: E402
from karatsuba_circuit import s3_link  # noqa: E402

DESIGN = HERE / "design_protocol.json"
PROTOCOL = HERE / "protocol.json"
INPUTS = {
    "q1496_design": Q1496 / "design_protocol.json",
    "q1496_protocol": Q1496 / "protocol.json",
    "q1496_runner": Q1496 / "run.py",
    "q1494_runner": q1494.HERE / "run.py",
    "q1493_runner": q1493.HERE / "run.py",
    "q1482_formula": q1482.HERE / "build_formula.py",
    "q1482_n83_fixture": q1482.HERE / "n83_planted_fixture.json",
    "q1490_n53_witness": q1494.INPUTS["q1490_witness"],
    "circuit_validation": HERE / "circuit_validation.json",
    "cms_binary": q1496.INPUTS["cms_binary"],
    "sage_runtime_info": HERE / "sage_runtime_info.json",
}
for n, d in ((53, 14), (83, 23)):
    INPUTS[f"n{n}_bridge"] = PARENT / "field_bridges" / (
        f"n{n}_onb_poly.json")
    INPUTS[f"n{n}_base_receipt"] = PARENT / (
        f"q1481_window_orbit_base/n{n}_d{d}_base.json")
    INPUTS[f"n{n}_ordinary_input"] = q1482.HERE / (
        f"inputs/n{n}_ordinary/input.json")
for cell in ("n53_known_rotation_44", "n53_ordinary_rotation_0",
             "n83_ordinary_rotation_0"):
    INPUTS[f"q1496_{cell}_receipt"] = Q1496 / f"runs/{cell}/receipt.json"


def sha(path: Path) -> str:
    return q1496.sha(path)


def load_and_check() -> tuple[dict, dict]:
    design = json.loads(DESIGN.read_text())
    protocol = json.loads(PROTOCOL.read_text())
    assert design["proposal_id"] == protocol["proposal_id"] == "Q1497"
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
    assert protocol["circuit_source_sha256"] == sha(
        HERE / "karatsuba_circuit.py")
    for label, path in INPUTS.items():
        assert protocol["input_sha256"][label] == sha(path), label
    assert json.loads(INPUTS["sage_runtime_info"].read_text())[
        "status"] == "verified"
    parent_design, _ = q1496.load_and_check()
    assert design["degree_profiles"] == parent_design["degree_profiles"]
    assert design["solver_matrix_settings"] == parent_design[
        "matrix_settings"]
    validation = json.loads(INPUTS["circuit_validation"].read_text())
    assert all(row["status"] == "PASS" for row in validation["cases"])
    return design, protocol


def solver_options(design: dict, cap: int) -> list[str]:
    return q1496.solver_options({
        "matrix_settings": design["solver_matrix_settings"],
        "conflict_cap": design["conflict_cap"]}, cap)


def pin_value(formula: Formula, bits: list[int], value: int) -> list[int]:
    assert 0 <= value < (1 << len(bits))
    literals = [bit if (value >> i) & 1 else -bit
                for i, bit in enumerate(bits)]
    formula.clauses.extend([[literal] for literal in literals])
    return literals


def build(name: str, control: bool, design: dict):
    spec = design["runs"][name]
    n, k = spec["degree_n"], spec["rotation"]
    role = spec["target_role"]
    profile = next(row for row in design["degree_profiles"]
                   if row["field_degree_n"] == n)
    bridge = json.loads(INPUTS[f"n{n}_bridge"].read_text())
    assert bridge["curve_id"] == profile["curve_id"]
    assert bridge["isogeny"] == "none"
    base = json.loads(INPUTS[f"n{n}_base_receipt"].read_text())
    assert base["actual_usable_points_B_before_folding"] == profile[
        "factor_base_actual_B"]
    assert base["signed_frobenius_columns_K"] == profile[
        "factor_base_folded_columns_K"]
    assert base["enumerated_set_sha256"] == profile[
        "factor_base_enumerated_set_sha256"]
    onb = q1493.field.Onb(n)
    curve = q1493.curves.Curve(onb)
    orbit = q1493.OrbitKey(onb)
    if role == "ordinary":
        original_x, original_q = q1482.raw_targets_and_public(n, role)
    else:
        assert n == 83 and k == 0 and role == "planted"
        fixture = json.loads(INPUTS["q1482_n83_fixture"].read_text())
        assert fixture["curve_id"] == profile["curve_id"]
        assert fixture["factor_base_actual_B"] == profile[
            "factor_base_actual_B"]
        original_x = [fixture["raw_target_x_coordinate"]]
        original_q = fixture["public_target"]
    original_q = tuple(original_q)
    assert curve.onCurve(original_q)
    rotated_q = curve.frob(original_q, k)
    rotated_x = [onb.toCoords(onb.frob(onb.fromCoords(x), k))
                 for x in original_x]
    assert len(rotated_x) == len(set(rotated_x))
    formula = Formula()
    leaves = [[formula.new() for _ in range(n)] for _ in range(4)]
    mids = [[formula.new() for _ in range(n)] for _ in range(2)]
    windows = [q1482.window_membership(
        formula, leaf, orbit.coordinate_cycle,
        profile["window_dimension_d"]) for leaf in leaves]
    target, selector = choose_target_x(formula, n, rotated_x)
    square_dest = square_destinations(onb)
    s3_link(formula, mids[0], mids[1], target, bridge, square_dest)
    s3_link(formula, leaves[2], leaves[3], mids[1], bridge, square_dest)
    s3_link(formula, leaves[0], leaves[1], mids[0], bridge, square_dest)
    selected = windows[0][0]
    formula.clauses.append([selected])
    meta = {
        "degree_n": n,
        "nominal_window_dimension_d": profile["window_dimension_d"],
        "factor_base_actual_B": profile["factor_base_actual_B"],
        "folded_columns_K": profile["factor_base_folded_columns_K"],
        "factor_base_enumerated_set_sha256": profile[
            "factor_base_enumerated_set_sha256"],
        "raw_target_x_coordinates": rotated_x,
        "leaf_variables": leaves,
        "pair_mid_variables": mids,
        "target_selector_variables": selector,
        "window_selector_variables": windows,
    }
    pins = []
    if control and n == 53:
        witness = json.loads(INPUTS["q1490_n53_witness"].read_text())
        pins = q1494.rotated_witness_pins(meta, witness, k)
        formula.clauses.extend([[literal] for literal in pins])
    elif control:
        assert n == 83 and role == "planted"
        for bits, value in zip(leaves, fixture["raw_leaf_x_coordinates"]):
            pins.extend(pin_value(formula, bits, value))
        for bits, value in zip(mids, fixture[
                "raw_pair_mid_x_coordinates"]):
            pins.extend(pin_value(formula, bits, value))
        pins.extend(pin_value(formula, selector, 0))
    if role == "ordinary":
        parent = json.loads(INPUTS[f"q1496_{name}_receipt"].read_text())
        assert list(original_q) == parent["original_public_target"]
        assert list(rotated_q) == parent["rotated_public_target"]
        if k == 0:
            assert rotated_x == original_x
        else:
            assert len(rotated_x) == len(original_x)
    return formula, meta, original_q, rotated_q, selected, pins, profile


def execute(name: str, control: bool) -> dict:
    design, _ = load_and_check()
    spec = design["runs"][name]
    assert not control or spec["known_satisfiable"]
    output = HERE / (f"control/n{spec['degree_n']}_r1" if control else
                     f"runs/{name}")
    assert not output.exists(), "refusing to overwrite previous attempt"
    output.mkdir(parents=True)
    began = time.perf_counter_ns()
    formula, meta, original_q, rotated_q, selected, pins, profile = build(
        name, control, design)
    path = output / "system.xcnf"
    formula.write(path)
    formula_hash, formula_bytes = sha(path), path.stat().st_size
    build_ns = time.perf_counter_ns() - began
    cap = (design["control_wall_cap_seconds"] if control else
           spec["solver_wall_cap_seconds"])
    command = [str(INPUTS["cms_binary"]), *solver_options(design, cap),
               str(path)]
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
    model = q1494.parse_model(stdout)
    began = time.perf_counter_ns()
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
    verify_ns = time.perf_counter_ns() - began
    path.unlink()
    status = ("verified_relation" if relation and relation["status"] ==
              "verified_four_point_relation" else "model_rejected" if model
              is not None else native_status)
    charged = build_ns + process_ns + verify_ns
    receipt = {
        "kind": "q1497_karatsuba_s3_control" if control else
                "q1497_karatsuba_s3_attempt",
        "proposal_id": "Q1497", "candidate_id": None, "run_id": None,
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
        "full_xcnf_bytes": formula_bytes,
        "full_xcnf_variables": formula.variables,
        "full_xcnf_clauses": len(formula.clauses),
        "full_xcnf_xor_rows": len(formula.xors),
        "and_gates": len(formula.and_cache),
        "solver_command_options": solver_options(design, cap),
        "solver_counters": q1494.solver_counters(stdout),
        "solver_counter_display": q1496.counter_display(stdout),
        "matrix_log": q1496.matrix_log(stdout),
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
        "circuit_source_sha256": sha(HERE / "karatsuba_circuit.py"),
        "cms_binary_sha256": sha(INPUTS["cms_binary"]),
    }
    (output / "receipt.json").write_text(json.dumps(
        receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def check(name: str, control: bool) -> dict:
    design, _ = load_and_check()
    spec = design["runs"][name]
    output = HERE / (f"control/n{spec['degree_n']}_r1" if control else
                     f"runs/{name}")
    receipt = json.loads((output / "receipt.json").read_text())
    assert receipt["source_sha256"] == sha(Path(__file__))
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["solver_stdout_sha256"] == sha(output / "solver.stdout.txt")
    assert receipt["solver_stderr_sha256"] == sha(output / "solver.stderr.txt")
    formula, meta, original_q, rotated_q, selected, pins, profile = build(
        name, control, design)
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "system.xcnf"
        formula.write(path)
        assert receipt["full_xcnf_sha256"] == sha(path)
        assert receipt["full_xcnf_bytes"] == path.stat().st_size
    assert receipt["full_xcnf_variables"] == formula.variables
    assert receipt["full_xcnf_clauses"] == len(formula.clauses)
    assert receipt["full_xcnf_xor_rows"] == len(formula.xors)
    assert receipt["and_gates"] == len(formula.and_cache)
    assert receipt["control_pins"] == len(pins)
    assert receipt["charged_stage_ns"] == sum(receipt["phase_ns"].values())
    stdout = (output / "solver.stdout.txt").read_text()
    assert receipt["solver_counters"] == q1494.solver_counters(stdout)
    assert receipt["solver_counter_display"] == q1496.counter_display(stdout)
    assert receipt["matrix_log"] == q1496.matrix_log(stdout)
    model = q1494.parse_model(stdout)
    if model is None:
        assert receipt["verified_relation"] is None
        assert receipt["successful_unpinned_stage_ns_exploratory"] is None
    else:
        relation = q1494.verify_relation(model, formula, meta, original_q,
                                         rotated_q, spec["rotation"], selected)
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
    parser.add_argument("--inspect-formula", action="store_true")
    args = parser.parse_args()
    if args.inspect_formula:
        formula, *_ = build(args.cell, args.control, design)
        print(json.dumps({"cell": args.cell,
                          "variables": formula.variables,
                          "clauses": len(formula.clauses),
                          "xor_rows": len(formula.xors),
                          "and_gates": len(formula.and_cache)},
                         sort_keys=True))
        return
    receipt = check(args.cell, args.control) if args.check else execute(
        args.cell, args.control)
    print(json.dumps({"cell": args.cell, "status": receipt["status"],
                      "charged_stage_seconds": receipt[
                          "charged_stage_ns"] / 1e9,
                      "conflicts": receipt["solver_counters"]["conflicts"],
                      "and_gates": receipt["and_gates"]}, sort_keys=True))


if __name__ == "__main__":
    main()
