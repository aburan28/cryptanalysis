#!/usr/bin/env python3
"""Sweep Frobenius target rotations with Q1482's first window fixed to zero."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1482 = PARENT / "q1482_window_s3"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(Q1482))

import build_formula as q1482_formula  # noqa: E402
from verify_model import model_relation  # noqa: E402
from q1420_root_theory.verify_archive import (  # noqa: E402
    check_cnf, model_from_file,
)
from q1481_window_orbit_base.enumerate_base import (  # noqa: E402
    OrbitKey, canonical_rotation,
)
from q1423_target_coupled.target_inputs import encode_targets  # noqa: E402
from run_probe import curves, field  # noqa: E402


DESIGN = HERE / "design_protocol.json"
PROTOCOL = HERE / "protocol.json"
INPUT_PATHS = {
    "q1482_protocol": Q1482 / "protocol.json",
    "q1482_formula_source": Q1482 / "build_formula.py",
    "q1482_verifier_source": Q1482 / "verify_model.py",
    "q1490_n53_witness": PARENT / "q1490_ordinary_witness_bridge/runs/r2/bridge_result.json",
    "q1491_n53_sat_control": PARENT / "q1491_ordinary_cnf_witness/runs/r1/receipt.json",
    "q1480_native_solver": PARENT / "q1480_conditioned_join/native_solver",
    "sage_runtime_info": HERE / "sage_runtime_info.json",
}
for degree, dimension in ((53, 14), (83, 23)):
    INPUT_PATHS.update({
        f"n{degree}_base_receipt": PARENT /
        f"q1481_window_orbit_base/n{degree}_d{dimension}_base.json",
        f"n{degree}_ordinary_input": Q1482 /
        f"inputs/n{degree}_ordinary/input.json",
        f"n{degree}_ordinary_cnf_gz": Q1482 /
        f"inputs/n{degree}_ordinary/system.cnf.gz",
        f"n{degree}_ordinary_variables": Q1482 /
        f"inputs/n{degree}_ordinary/variables.txt",
        f"n{degree}_ordinary_targets": Q1482 /
        f"inputs/n{degree}_ordinary/targets.txt",
        f"n{degree}_field": PARENT /
        f"q1420_root_theory/n{degree}_field.txt",
    })


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_and_check() -> tuple[dict, dict]:
    design = json.loads(DESIGN.read_text())
    protocol = json.loads(PROTOCOL.read_text())
    assert design["proposal_id"] == protocol["proposal_id"] == "Q1493"
    assert design["candidate_id"] is protocol["candidate_id"] is None
    assert design["run_id"] is protocol["run_id"] is None
    assert design["isogeny"] == protocol["isogeny"] == "none"
    assert protocol["design_sha256"] == sha(DESIGN)
    assert protocol["source_sha256"] == sha(Path(__file__))
    assert design["profiles"] == protocol["profiles"]
    assert design["runs"] == protocol["runs"]
    for label, path in INPUT_PATHS.items():
        expected = design["frozen_inputs_sha256"][label]
        assert sha(path) == expected == protocol["frozen_inputs_sha256"][label], label
    assert json.loads(INPUT_PATHS["sage_runtime_info"].read_text())[
        "status"] == "verified"
    q1482 = json.loads(INPUT_PATHS["q1482_protocol"].read_text())
    assert q1482["solver_binary_sha256"] == sha(INPUT_PATHS[
        "q1480_native_solver"])
    assert q1482["decision_policy"] == design["decision_policy"]
    assert q1482["pair_candidate_cap"] == design["pair_candidate_cap"]
    for profile in design["profiles"]:
        n = profile["field_degree_n"]
        base = json.loads(INPUT_PATHS[f"n{n}_base_receipt"].read_text())
        inp = json.loads(INPUT_PATHS[f"n{n}_ordinary_input"].read_text())
        assert base["curve_id"] == inp["curve_id"] == profile["curve_id"]
        assert base["actual_usable_points_B_before_folding"] == inp[
            "factor_base_actual_B"] == profile["factor_base_actual_B"]
        assert base["signed_frobenius_columns_K"] == inp[
            "folded_columns_K"] == profile["factor_base_folded_columns_K"]
        assert base["enumerated_set_sha256"] == inp[
            "factor_base_enumerated_set_sha256"] == profile[
                "factor_base_enumerated_set_sha256"]
        assert inp["target_preimage_x_count"] == profile[
            "original_target_preimage_count"]
        assert q1482["cases"][f"n{n}_ordinary"]["workload_id"] == profile[
            "parent_workload_id"]
        assert q1482["field_file_sha256"][str(n)] == sha(INPUT_PATHS[
            f"n{n}_field"])
    witness = json.loads(INPUT_PATHS["q1490_n53_witness"].read_text())
    control = json.loads(INPUT_PATHS["q1491_n53_sat_control"].read_text())
    assert witness["status"] == control["status"] == "PASS"
    assert witness["curve_id"] == design["profiles"][0]["curve_id"]
    assert control["q1490_bridge_result_sha256"] == sha(INPUT_PATHS[
        "q1490_n53_witness"])
    return design, protocol


def frob_field(onb, element: int, k: int) -> int:
    for _ in range(k):
        element = onb.sqr(element)
    return element


def rotated_input(n: int, k: int, profile: dict):
    assert 0 <= k < n
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    original_x, original_q = q1482_formula.raw_targets_and_public(
        n, "ordinary")
    assert encode_targets(n, original_x) == INPUT_PATHS[
        f"n{n}_ordinary_targets"].read_bytes()
    original_q = tuple(original_q)
    assert curve.onCurve(original_q)
    rotated_q = curve.frob(original_q, k)
    rotated_x = [onb.toCoords(frob_field(onb, onb.fromCoords(x), k))
                 for x in original_x]
    assert len(rotated_x) == len(set(rotated_x)) == profile[
        "original_target_preimage_count"]
    saved = q1482_formula.raw_targets_and_public
    try:
        q1482_formula.raw_targets_and_public = (
            lambda degree, role: (rotated_x, list(rotated_q))
            if degree == n and role == "ordinary" else saved(degree, role))
        raw, varmap, targets, formula, meta, variables, clauses = (
            q1482_formula.build_cnf(n, "ordinary"))
    finally:
        q1482_formula.raw_targets_and_public = saved
    inp = json.loads(INPUT_PATHS[f"n{n}_ordinary_input"].read_text())
    assert variables == inp["cnf_variables"]
    assert clauses == inp["cnf_clauses"]
    assert varmap == INPUT_PATHS[f"n{n}_ordinary_variables"].read_bytes()
    assert targets == encode_targets(n, rotated_x)
    assert meta["public_target"] == list(rotated_q)
    assert meta["raw_target_x_coordinates"] == rotated_x
    if k == 0:
        assert hashlib.sha256(raw).hexdigest() == inp["cnf_raw_sha256"]
        assert gzip.decompress(INPUT_PATHS[
            f"n{n}_ordinary_cnf_gz"].read_bytes()) == raw
        assert targets == INPUT_PATHS[f"n{n}_ordinary_targets"].read_bytes()
    selected = meta["window_selector_variables"][0][0]
    header, sep, body = raw.partition(b"\n")
    assert sep and header == f"p cnf {variables} {clauses}".encode()
    assert body.count(b"\n") == clauses
    pinned = (f"p cnf {variables} {clauses + 1}\n".encode() + body +
              f"{selected} 0\n".encode())
    return (raw, pinned, targets, formula, meta, variables, clauses,
            original_q, rotated_q, selected)


def replay_model(model_path: Path, raw: bytes, pinned: bytes, formula,
                 meta: dict, variables: int, clauses: int,
                 original_q: tuple, k: int, selected: int) -> dict:
    n = meta["degree_n"]
    model = model_from_file(model_path)
    check_cnf(pinned, model, variables, clauses + 1)
    assert model[selected]
    relation = model_relation(raw, formula, meta, variables, clauses,
                              model_path)
    if relation["status"] != "verified_four_point_relation":
        return relation
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    transported = []
    for point, sign, key in zip(relation["projected_points"],
                                relation["signs"],
                                relation["projected_columns"]):
        rotated = tuple(point)
        if sign == -1:
            rotated = curve.neg(rotated)
        restored = curve.frob(rotated, (n - k) % n)
        assert canonical_rotation(orbit.cycle_bits(restored[0]), n) == key
        transported.append(restored)
    total = None
    for point in transported:
        total = curve.add(total, point)
    assert total == original_q
    assert len(set(relation["projected_columns"])) == 4
    relation["transported_original_target"] = list(total)
    relation["inverse_frobenius_exponent"] = (n - k) % n
    relation["transported_projected_points"] = [list(point)
                                                 for point in transported]
    return relation


def known_witness_preflight() -> dict:
    design, _ = load_and_check()
    profile = design["profiles"][0]
    n, k = 53, 44
    data = rotated_input(n, k, profile)
    _, _, _, _, meta, _, _, original_q, rotated_q, selected = data
    witness = json.loads(INPUT_PATHS["q1490_n53_witness"].read_text())
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    from q1490_ordinary_witness_bridge.bridge_v2 import window_starts
    raw = [tuple(row["raw_point"]) for row in witness["four_raw_lifts"]]
    rotated = [curve.frob(point, k) for point in raw]
    first_starts = window_starts(orbit.cycle_bits(rotated[0][0]), n, 14)
    assert first_starts == [0]
    assert selected in meta["window_selector_variables"][0]
    total = None
    for point in rotated:
        total = curve.add(total, point)
    assert total is not None and onb.toCoords(total[0]) in meta[
        "raw_target_x_coordinates"]
    assert curve.mul(total, 428) == rotated_q
    assert curve.frob(rotated_q, n - k) == original_q
    assert original_q == tuple(witness["ordinary_public_target"])
    return {"status": "PASS", "degree_n": n, "rotation": k,
            "first_window_starts": first_starts,
            "rotated_target_preimage_index": meta[
                "raw_target_x_coordinates"].index(onb.toCoords(total[0])),
            "q1490_witness_sha256": sha(INPUT_PATHS[
                "q1490_n53_witness"]),
            "design_sha256": sha(DESIGN),
            "protocol_sha256": sha(PROTOCOL),
            "source_sha256": sha(Path(__file__))}


def run_cell(cell_name: str) -> None:
    design, protocol = load_and_check()
    assert cell_name in design["run_order"]
    cell = design["runs"][cell_name]
    n = cell["degree_n"]
    profile = next(row for row in design["profiles"]
                   if row["field_degree_n"] == n)
    output = HERE / "runs" / cell_name
    assert not output.exists(), "refusing to overwrite attempted cell"
    output.mkdir(parents=True)
    attempts_path = output / "attempts.jsonl"
    totals = {"target_encoding_ns": 0, "materialization_ns": 0,
              "native_process_ns": 0, "relation_check_ns": 0}
    operation_keys = ("conflicts", "decisions", "propagations",
                      "field_mul_calls", "field_sqr_calls",
                      "field_inv_calls", "field_s3_root_calls",
                      "conditioned_right_s3_evals")
    operations = {key: 0 for key in operation_keys}
    operation_vector_complete = True
    verified = None
    for k in cell["rotations"]:
        began = time.perf_counter_ns()
        data = rotated_input(n, k, profile)
        (raw, pinned, targets, formula, meta, variables, clauses,
         original_q, rotated_q, selected) = data
        encoding_ns = time.perf_counter_ns() - began
        totals["target_encoding_ns"] += encoding_ns
        with tempfile.TemporaryDirectory(prefix=f"q1493_{cell_name}_{k}_",
                                         dir="/private/tmp") as temporary:
            temp = Path(temporary)
            cnf_path = temp / "system.cnf"
            targets_path = temp / "targets.txt"
            model_path = temp / "solver.model.txt"
            began = time.perf_counter_ns()
            cnf_path.write_bytes(pinned)
            targets_path.write_bytes(targets)
            materialization_ns = time.perf_counter_ns() - began
            totals["materialization_ns"] += materialization_ns
            command = [str(INPUT_PATHS["q1480_native_solver"]),
                       str(INPUT_PATHS[f"n{n}_field"]), str(cnf_path),
                       str(INPUT_PATHS[f"n{n}_ordinary_variables"]),
                       str(model_path), str(design[
                           "conflict_cap_per_rotation"]),
                       str(cell["native_wall_cap_seconds_per_rotation"]),
                       str(targets_path), str(design[
                           "pair_candidate_cap"]), design["decision_policy"]]
            before = resource.getrusage(resource.RUSAGE_CHILDREN)
            began = time.perf_counter_ns()
            try:
                completed = subprocess.run(
                    command, capture_output=True, text=True,
                    timeout=cell[
                        "external_safeguard_seconds_per_rotation"])
                exit_code = completed.returncode
                stdout, stderr = completed.stdout, completed.stderr
                native_status = {0: "sat", 10: "censored", 20: "unsat"}.get(
                    exit_code, "error")
            except subprocess.TimeoutExpired as error:
                exit_code, native_status = None, "external_timeout"
                stdout = (error.stdout or b"").decode(errors="replace")
                stderr = (error.stderr or b"").decode(errors="replace")
            native_ns = time.perf_counter_ns() - began
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            totals["native_process_ns"] += native_ns
            try:
                report = json.loads(stdout) if stdout.strip() else None
            except json.JSONDecodeError:
                report = None
            if report is None or any(report.get(key) is None
                                     for key in operation_keys):
                operation_vector_complete = False
            else:
                for key in operation_keys:
                    operations[key] += report[key]
            began = time.perf_counter_ns()
            relation, verification_error = None, None
            model_digest = None
            if native_status == "sat" and model_path.exists():
                model_digest = sha(model_path)
                (output / f"model_k{k}.txt.gz").write_bytes(
                    gzip.compress(model_path.read_bytes()))
                try:
                    relation = replay_model(
                        model_path, raw, pinned, formula, meta, variables,
                        clauses, original_q, k, selected)
                except Exception as error:
                    verification_error = repr(error)
            check_ns = time.perf_counter_ns() - began
            totals["relation_check_ns"] += check_ns
        status = ("verified_relation" if relation is not None and
                  relation.get("status") == "verified_four_point_relation"
                  else "model_rejected" if verification_error or
                  relation is not None else native_status)
        attempt = {
            "rotation": k, "degree_n": n, "status": status,
            "native_status": native_status, "native_exit_code": exit_code,
            "native_report": report, "native_stdout": stdout,
            "native_stderr": stderr,
            "model_sha256": model_digest,
            "independent_relation": relation,
            "verification_error": verification_error,
            "original_target": list(original_q),
            "rotated_target": list(rotated_q),
            "target_preimage_count": len(meta[
                "raw_target_x_coordinates"]),
            "original_cnf_sha256": hashlib.sha256(raw).hexdigest(),
            "first_window_cnf_sha256": hashlib.sha256(pinned).hexdigest(),
            "rotated_targets_sha256": hashlib.sha256(targets).hexdigest(),
            "first_window_selector_variable": selected,
            "target_encoding_ns_exploratory": encoding_ns,
            "materialization_ns_exploratory": materialization_ns,
            "native_process_ns_exploratory": native_ns,
            "relation_check_ns_exploratory": check_ns,
            "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
            "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
            "peak_child_rss_so_far_raw": after.ru_maxrss,
        }
        with attempts_path.open("a") as stream:
            stream.write(json.dumps(attempt, sort_keys=True) + "\n")
            stream.flush()
        print(json.dumps({"cell": cell_name, "rotation": k,
                          "status": status,
                          "conflicts": (report or {}).get("conflicts"),
                          "propagations": (report or {}).get("propagations")},
                         sort_keys=True), flush=True)
        if status == "verified_relation":
            verified = attempt
            break
    attempts = [json.loads(line) for line in attempts_path.read_text().splitlines()]
    assert attempts
    status = ("verified_relation" if verified is not None else
              "incomplete" if len(attempts) != len(cell["rotations"]) or
              any(row["native_status"] == "error" for row in attempts)
              else "no_verified_relation_at_caps")
    receipt = {
        "kind": "q1493_frobenius_first_window_sweep_stage",
        "proposal_id": "Q1493", "candidate_id": None,
        "run_id": None, "isogeny": "none",
        "cell": cell_name, "status": status,
        "curve_id": profile["curve_id"], "field_degree_n": n,
        "factor_base_actual_B": profile["factor_base_actual_B"],
        "factor_base_folded_columns_K": profile[
            "factor_base_folded_columns_K"],
        "factor_base_enumerated_set_sha256": profile[
            "factor_base_enumerated_set_sha256"],
        "parent_workload_id": profile["parent_workload_id"],
        "input_law": ("oracle_assisted_known_rotation_control"
                      if cell["oracle_assisted_rotation"] else
                      "deterministic_complete_frobenius_sweep_of_one_ordinary_target"),
        "native_wall_cap_seconds_per_rotation": cell[
            "native_wall_cap_seconds_per_rotation"],
        "rotation_attempt_count": len(attempts),
        "rotation_attempts_sha256": sha(attempts_path),
        "verified_relation_count": int(verified is not None),
        "verified_rotation": verified["rotation"] if verified else None,
        "operation_vector_complete": operation_vector_complete,
        "summed_native_operations": operations if operation_vector_complete
                                    else None,
        "exclusive_phase_ns_exploratory": totals,
        "charged_stage_wall_ns_exploratory": sum(totals.values()),
        "peak_child_rss_raw": max(row["peak_child_rss_so_far_raw"]
                                  for row in attempts),
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "natural_relation_yield_estimate": None,
        "novel_rank_per_query": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "design_sha256": sha(DESIGN),
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(INPUT_PATHS["sage_runtime_info"]),
    }
    (output / "receipt.json").write_text(json.dumps(
        receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cell": cell_name, "status": status,
                      "attempts": len(attempts),
                      "verified_rotation": receipt["verified_rotation"]},
                     sort_keys=True), flush=True)


def check_cell(cell_name: str) -> None:
    design, _ = load_and_check()
    cell = design["runs"][cell_name]
    n = cell["degree_n"]
    profile = next(row for row in design["profiles"]
                   if row["field_degree_n"] == n)
    output = HERE / "runs" / cell_name
    receipt = json.loads((output / "receipt.json").read_text())
    attempts_path = output / "attempts.jsonl"
    attempts = [json.loads(line) for line in attempts_path.read_text().splitlines()]
    assert receipt["source_sha256"] == sha(Path(__file__))
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["rotation_attempts_sha256"] == sha(attempts_path)
    assert receipt["rotation_attempt_count"] == len(attempts)
    assert [row["rotation"] for row in attempts] == cell["rotations"][:len(attempts)]
    assert receipt["charged_stage_wall_ns_exploratory"] == sum(
        receipt["exclusive_phase_ns_exploratory"].values())
    for attempt in attempts:
        k = attempt["rotation"]
        data = rotated_input(n, k, profile)
        (raw, pinned, targets, formula, meta, variables, clauses,
         original_q, rotated_q, selected) = data
        assert attempt["original_cnf_sha256"] == hashlib.sha256(raw).hexdigest()
        assert attempt["first_window_cnf_sha256"] == hashlib.sha256(pinned).hexdigest()
        assert attempt["rotated_targets_sha256"] == hashlib.sha256(targets).hexdigest()
        assert attempt["first_window_selector_variable"] == selected
        assert attempt["rotated_target"] == list(rotated_q)
        if attempt["model_sha256"] is not None:
            model_data = gzip.decompress((output / f"model_k{k}.txt.gz").read_bytes())
            assert hashlib.sha256(model_data).hexdigest() == attempt["model_sha256"]
            with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
                path = Path(temporary) / "model.txt"
                path.write_bytes(model_data)
                relation = replay_model(path, raw, pinned, formula, meta,
                                        variables, clauses, original_q, k,
                                        selected)
            assert relation == attempt["independent_relation"]
    print(f"Q1493 {cell_name} archive: {receipt['status']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cell")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        result = known_witness_preflight()
        encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
        output = HERE / "known_witness_preflight.json"
        if args.check:
            assert output.read_text() == encoded
            print("Q1493 known-witness rotation preflight PASS (archived)")
        else:
            assert not output.exists()
            output.write_text(encoded)
            print("Q1493 known-witness rotation preflight PASS")
    else:
        assert args.cell, "--cell is required unless --preflight"
        check_cell(args.cell) if args.check else run_cell(args.cell)


if __name__ == "__main__":
    main()
