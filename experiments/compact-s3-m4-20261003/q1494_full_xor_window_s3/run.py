#!/usr/bin/env python3
"""Run full symbolic three-S3 XCNF on Q1481's exact window bases."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1493 = PARENT / "q1493_frobenius_window_sweep"
sys.path.insert(0, str(Q1493))

SPEC = importlib.util.spec_from_file_location("q1493_run", Q1493 / "run.py")
assert SPEC is not None and SPEC.loader is not None
q1493 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(q1493)
from chain_s3 import multiplication_table, square_destinations  # noqa: E402
from chain_s3_factored import s3_link_factored  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402
from verify_model import (  # noqa: E402
    archived_key_contains, cyclic_window_contains,
)

DESIGN = HERE / "design_protocol.json"
PROTOCOL = HERE / "protocol.json"
INPUTS = {
    "q1493_protocol": Q1493 / "protocol.json",
    "q1493_source": Q1493 / "run.py",
    "q1493_control_source": Q1493 / "run_control.py",
    "q1490_witness": PARENT /
    "q1490_ordinary_witness_bridge/runs/r2/bridge_result.json",
    "q1482_formula_source": PARENT / "q1482_window_s3/build_formula.py",
    "q1482_verifier_source": PARENT / "q1482_window_s3/verify_model.py",
    "q1481_protocol": PARENT / "q1481_window_orbit_base/protocol.json",
    "chain_s3_source": PARENT / "chain_s3.py",
    "chain_s3_factored_source": PARENT / "chain_s3_factored.py",
    "cms_binary": Path("/opt/homebrew/bin/cryptominisat5"),
    "sage_runtime_info": HERE / "sage_runtime_info.json",
}
for degree, dimension in ((53, 14), (83, 23)):
    INPUTS[f"n{degree}_base_receipt"] = (PARENT /
        f"q1481_window_orbit_base/n{degree}_d{dimension}_base.json")
    INPUTS[f"n{degree}_projected_keys"] = (PARENT /
        f"q1481_window_orbit_base/n{degree}_d{dimension}_projected_keys.bin")
    INPUTS[f"n{degree}_ordinary_input"] = (PARENT /
        f"q1482_window_s3/inputs/n{degree}_ordinary/input.json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_and_check() -> tuple[dict, dict]:
    design = json.loads(DESIGN.read_text())
    protocol = json.loads(PROTOCOL.read_text())
    assert design["proposal_id"] == protocol["proposal_id"] == "Q1494"
    assert design["candidate_id"] is protocol["candidate_id"] is None
    assert design["run_id"] is protocol["run_id"] is None
    assert design["isogeny"] == protocol["isogeny"] == "none"
    assert design["run_order"] == protocol["run_order"]
    assert design["runs"] == protocol["runs"]
    assert design["degree_profiles"] == protocol["degree_profiles"]
    assert protocol["design_sha256"] == sha(DESIGN)
    assert protocol["runner_source_sha256"] == sha(Path(__file__))
    for label, path in INPUTS.items():
        assert sha(path) == protocol["input_sha256"][label], label
    assert json.loads(INPUTS["sage_runtime_info"].read_text())[
        "status"] == "verified"
    parent_design, parent_protocol = q1493.load_and_check()
    assert parent_design["proposal_id"] == parent_protocol[
        "proposal_id"] == "Q1493"
    for own, parent in zip(design["degree_profiles"], parent_design["profiles"]):
        assert own["curve_id"] == parent["curve_id"]
        assert own["factor_base_actual_B"] == parent[
            "factor_base_actual_B"]
        assert own["factor_base_folded_columns_K"] == parent[
            "factor_base_folded_columns_K"]
        assert own["factor_base_enumerated_set_sha256"] == parent[
            "factor_base_enumerated_set_sha256"]
        assert own["parent_workload_id"] == parent["parent_workload_id"]
    return design, protocol


def build_full_formula(n: int, k: int, profile: dict):
    parent_design, _ = q1493.load_and_check()
    parent_profile = next(row for row in parent_design["profiles"]
                          if row["field_degree_n"] == n)
    assert parent_profile["curve_id"] == profile["curve_id"]
    (original_cnf, first_window_cnf, _, formula, meta, _, _,
     original_q, rotated_q, selected) = q1493.rotated_input(
         n, k, parent_profile)
    assert len(meta["leaf_variables"]) == 4
    assert len(meta["pair_mid_variables"]) == 2
    onb = q1493.field.Onb(n)
    s3_link_factored(formula, meta["leaf_variables"][0],
                     meta["leaf_variables"][1],
                     meta["pair_mid_variables"][0],
                     multiplication_table(onb),
                     square_destinations(onb))
    formula.clauses.append([selected])
    return (formula, meta, original_q, rotated_q, selected,
            sha_bytes(original_cnf), sha_bytes(first_window_cnf))


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rotated_witness_pins(meta: dict, witness: dict, k: int) -> list[int]:
    n = meta["degree_n"]
    assert n == 53 and k == 44
    onb = q1493.field.Onb(n)
    curve = q1493.curves.Curve(onb)
    raw_points = [tuple(row["raw_point"])
                  for row in witness["four_raw_lifts"]]
    mids = [tuple(row) for row in witness["raw_pair_mid_points"]]
    leaf_x = [onb.toCoords(curve.frob(point, k)[0])
              for point in raw_points]
    mid_x = [onb.toCoords(curve.frob(point, k)[0]) for point in mids]
    target_x = onb.toCoords(curve.frob(
        tuple(witness["raw_target_point"]), k)[0])
    assert meta["raw_target_x_coordinates"][141] == target_x
    groups = (list(zip(meta["leaf_variables"], leaf_x)) +
              list(zip(meta["pair_mid_variables"], mid_x)) +
              [(meta["target_selector_variables"], 141)])
    pins = []
    for bits, value in groups:
        assert 0 <= value < (1 << len(bits))
        pins.extend(bit if (value >> j) & 1 else -bit
                    for j, bit in enumerate(bits))
    assert len(pins) == 327 == len({abs(lit) for lit in pins})
    return pins


def parse_model(stdout: str) -> dict[int, bool] | None:
    if "s SATISFIABLE" not in stdout:
        return None
    model = {}
    for line in stdout.splitlines():
        if line.startswith("v "):
            for token in line[2:].split():
                literal = int(token)
                if literal:
                    assert abs(literal) not in model
                    model[abs(literal)] = literal > 0
    return model


def solver_counters(stdout: str) -> dict[str, int | None]:
    result = {}
    for name in ("conflicts", "decisions", "propagations", "restarts"):
        found = None
        for line in stdout.splitlines():
            prefix = f"c {name}"
            if line.startswith(prefix) and line[len(prefix):].lstrip().startswith(":"):
                number = line.split(":", 1)[1].split()[0]
                if number.isdigit():
                    found = int(number)
                elif number.endswith("M"):
                    found = int(float(number[:-1]) * 1_000_000)
                elif number.endswith("K"):
                    found = int(float(number[:-1]) * 1_000)
        result[name] = found
    return result


def verify_relation(model: dict[int, bool], formula, meta: dict,
                    original_q: tuple, rotated_q: tuple, k: int,
                    selected: int) -> dict:
    assert set(model) == set(range(1, formula.variables + 1))
    assert model[selected]
    assert all(any(model[abs(lit)] == (lit > 0) for lit in clause)
               for clause in formula.clauses)
    assert all((sum(model[bit] for bit in row) & 1) == int(rhs)
               for row, rhs in formula.xors)
    n = meta["degree_n"]
    d = meta["nominal_window_dimension_d"]
    onb = q1493.field.Onb(n)
    curve = q1493.curves.Curve(onb)
    orbit = q1493.OrbitKey(onb)
    base = json.loads(INPUTS[f"n{n}_base_receipt"].read_text())
    subgroup = json.loads(INPUTS["q1481_protocol"].read_text())[
        "instances"][str(n)]
    packed = INPUTS[f"n{n}_projected_keys"].read_bytes()
    assert base["actual_usable_points_B_before_folding"] == meta[
        "factor_base_actual_B"]
    assert base["signed_frobenius_columns_K"] == meta["folded_columns_K"]
    assert base["enumerated_set_sha256"] == meta[
        "factor_base_enumerated_set_sha256"]

    def value(bits):
        return sum(1 << i for i, bit in enumerate(bits) if model[bit])

    leaf_x = [value(bits) for bits in meta["leaf_variables"]]
    mid_x = [value(bits) for bits in meta["pair_mid_variables"]]
    choice = value(meta["target_selector_variables"])
    assert 0 <= choice < len(meta["raw_target_x_coordinates"])
    target_x = meta["raw_target_x_coordinates"][choice]
    for a, b, c in ((leaf_x[0], leaf_x[1], mid_x[0]),
                    (leaf_x[2], leaf_x[3], mid_x[1]),
                    (mid_x[0], mid_x[1], target_x)):
        roots = {onb.toCoords(z) for z in s3_roots(
            onb, onb.fromCoords(a), onb.fromCoords(b))}
        assert c in roots
    points, projected, keys = [], [], []
    for x_mask in leaf_x:
        assert x_mask != 0
        field_x = onb.fromCoords(x_mask)
        assert cyclic_window_contains(orbit.cycle_bits(field_x), n, d)
        point = curve.pointFromX(field_x)
        if point is None:
            return {"status": "nonrational_raw_x", "raw_leaf_x": leaf_x}
        subgroup_point = curve.mul(point, subgroup["cofactor"])
        if subgroup_point is None:
            return {"status": "identity_projection", "raw_leaf_x": leaf_x}
        assert curve.mul(subgroup_point, subgroup["subgroup_order"]) is None
        key = q1493.canonical_rotation(
            orbit.cycle_bits(subgroup_point[0]), n)
        assert archived_key_contains(packed, key, n)
        points.append(point)
        projected.append(subgroup_point)
        keys.append(key)
    if len(set(keys)) != 4:
        return {"status": "duplicate_columns", "raw_leaf_x": leaf_x}
    for signs in itertools.product((1, -1), repeat=4):
        total = None
        for point, sign in zip(points, signs):
            total = curve.add(total, point if sign == 1 else curve.neg(point))
        if total is None or onb.toCoords(total[0]) != target_x:
            continue
        if curve.mul(total, subgroup["cofactor"]) != rotated_q:
            continue
        transported = []
        for point, sign in zip(projected, signs):
            signed = point if sign == 1 else curve.neg(point)
            transported.append(curve.frob(signed, (n - k) % n))
        restored_sum = None
        for point in transported:
            restored_sum = curve.add(restored_sum, point)
        assert restored_sum == original_q
        return {
            "status": "verified_four_point_relation",
            "raw_leaf_x_coordinates": leaf_x,
            "pair_mid_x_coordinates": mid_x,
            "selected_raw_target_index": choice,
            "signs": list(signs),
            "projected_columns": keys,
            "distinct_columns": 4,
            "projected_points": [list(p) for p in projected],
            "original_public_target": list(original_q),
            "rotated_public_target": list(rotated_q),
            "inverse_frobenius_exponent": (n - k) % n,
            "transported_original_target": list(restored_sum),
        }
    return {"status": "no_signed_public_sum", "raw_leaf_x": leaf_x}


def execute(name: str, control: bool = False) -> dict:
    design, protocol = load_and_check()
    run_spec = design["runs"][name]
    n, k = run_spec["degree_n"], run_spec["rotation"]
    profile = next(row for row in design["degree_profiles"]
                   if row["field_degree_n"] == n)
    output = HERE / ("control/r1" if control else f"runs/{name}")
    assert not output.exists(), "refusing to overwrite a previous attempt"
    output.mkdir(parents=True)
    build_started = time.perf_counter_ns()
    formula, meta, original_q, rotated_q, selected, original_hash, first_hash = (
        build_full_formula(n, k, profile))
    pins = []
    if control:
        assert name == "n53_known_rotation_44"
        witness = json.loads(INPUTS["q1490_witness"].read_text())
        pins = rotated_witness_pins(meta, witness, k)
        formula.clauses.extend([[lit] for lit in pins])
    formula_path = output / "system.xcnf"
    formula.write(formula_path)
    formula_hash = sha(formula_path)
    formula_bytes = formula_path.stat().st_size
    build_ns = time.perf_counter_ns() - build_started
    command = [str(INPUTS["cms_binary"]), "--verb", "1", "--threads", "1",
               "--maxtime", str(design["control_wall_cap_seconds"] if control
                                else run_spec["solver_wall_cap_seconds"]),
               "--maxconfl", str(design["conflict_cap"]), str(formula_path)]
    process_started = time.perf_counter_ns()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True,
            timeout=(design["control_wall_cap_seconds"] + 15 if control
                     else run_spec["external_safeguard_seconds"]))
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
    model = parse_model(stdout)
    verify_started = time.perf_counter_ns()
    relation, error = None, None
    if model is not None:
        try:
            relation = verify_relation(model, formula, meta, original_q,
                                       rotated_q, k, selected)
            if control:
                assert all(model[abs(lit)] == (lit > 0) for lit in pins)
                assert relation["status"] == "verified_four_point_relation"
        except Exception as exc:
            error = repr(exc)
    verify_ns = time.perf_counter_ns() - verify_started
    formula_path.unlink()
    status = ("verified_relation" if relation and relation["status"] ==
              "verified_four_point_relation" else
              "model_rejected" if model is not None else native_status)
    receipt = {
        "kind": "q1494_full_native_xor_three_s3_control" if control else
                "q1494_full_native_xor_three_s3_ordinary_attempt",
        "proposal_id": "Q1494", "candidate_id": None, "run_id": None,
        "isogeny": "none", "cell": name, "status": status,
        "native_status": native_status, "native_exit_code": exit_code,
        "curve_id": profile["curve_id"], "field_degree_n": n,
        "factor_base_actual_B": profile["factor_base_actual_B"],
        "factor_base_folded_columns_K": profile[
            "factor_base_folded_columns_K"],
        "factor_base_enumerated_set_sha256": profile[
            "factor_base_enumerated_set_sha256"],
        "parent_workload_id": profile["parent_workload_id"],
        "rotation": k, "first_window_zero": True,
        "known_satisfiable_from_q1490": run_spec[
            "known_satisfiable_from_q1490"],
        "control_pins": len(pins),
        "original_public_target": list(original_q),
        "rotated_public_target": list(rotated_q),
        "q1482_original_cnf_sha256": original_hash,
        "q1493_first_window_cnf_sha256": first_hash,
        "full_xcnf_sha256": formula_hash,
        "full_xcnf_bytes": formula_bytes,
        "full_xcnf_variables": formula.variables,
        "full_xcnf_clauses": len(formula.clauses),
        "full_xcnf_xor_rows": len(formula.xors),
        "solver_counters": solver_counters(stdout),
        "phase_ns": {
            "target_formula_build": build_ns,
            "target_solver_process": process_ns,
            "target_relation_check": verify_ns,
        },
        "charged_stage_ns": build_ns + process_ns + verify_ns,
        "charged_stage_wall_exploratory": True,
        "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
        "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
        "peak_child_rss_raw": after.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "solver_stdout_sha256": sha(output / "solver.stdout.txt"),
        "solver_stderr_sha256": sha(output / "solver.stderr.txt"),
        "verified_relation": relation,
        "verification_error": error,
        "successful_unpinned_stage_ns_exploratory": None if control or status !=
            "verified_relation" else build_ns + process_ns + verify_ns,
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "design_sha256": sha(DESIGN),
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "cms_binary_sha256": sha(INPUTS["cms_binary"]),
    }
    (output / "receipt.json").write_text(json.dumps(
        receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def check(name: str, control: bool = False) -> dict:
    design, _ = load_and_check()
    spec = design["runs"][name]
    n, k = spec["degree_n"], spec["rotation"]
    profile = next(row for row in design["degree_profiles"]
                   if row["field_degree_n"] == n)
    output = HERE / ("control/r1" if control else f"runs/{name}")
    receipt = json.loads((output / "receipt.json").read_text())
    assert receipt["source_sha256"] == sha(Path(__file__))
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["solver_stdout_sha256"] == sha(output / "solver.stdout.txt")
    assert receipt["solver_stderr_sha256"] == sha(output / "solver.stderr.txt")
    assert receipt["control_pins"] == (327 if control else 0)
    formula, meta, original_q, rotated_q, selected, original_hash, first_hash = (
        build_full_formula(n, k, profile))
    if control:
        witness = json.loads(INPUTS["q1490_witness"].read_text())
        pins = rotated_witness_pins(meta, witness, k)
        formula.clauses.extend([[lit] for lit in pins])
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "system.xcnf"
        formula.write(path)
        assert sha(path) == receipt["full_xcnf_sha256"]
        assert path.stat().st_size == receipt["full_xcnf_bytes"]
    assert receipt["full_xcnf_variables"] == formula.variables
    assert receipt["full_xcnf_clauses"] == len(formula.clauses)
    assert receipt["full_xcnf_xor_rows"] == len(formula.xors)
    assert receipt["q1482_original_cnf_sha256"] == original_hash
    assert receipt["q1493_first_window_cnf_sha256"] == first_hash
    assert receipt["charged_stage_ns"] == sum(receipt["phase_ns"].values())
    stdout = (output / "solver.stdout.txt").read_text()
    assert receipt["solver_counters"] == solver_counters(stdout)
    model = parse_model(stdout)
    if model is not None:
        relation = verify_relation(model, formula, meta, original_q,
                                   rotated_q, k, selected)
        assert relation == receipt["verified_relation"]
        assert (receipt["status"] == "verified_relation") == (
            relation["status"] == "verified_four_point_relation")
    else:
        assert receipt["verified_relation"] is None
        assert receipt["successful_unpinned_stage_ns_exploratory"] is None
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
    result = check(name, args.control) if args.check else execute(
        name, args.control)
    print(json.dumps({"cell": name, "status": result["status"],
                      "charged_stage_seconds": result[
                          "charged_stage_ns"] / 1e9,
                      "conflicts": result["solver_counters"]["conflicts"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
