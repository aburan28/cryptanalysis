#!/usr/bin/env python3
"""Pin Q1490's relation inside Q1493's rotated ordinary N53 CNF."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import time
from pathlib import Path

import run as q1493


HERE = Path(__file__).resolve().parent
DESIGN = HERE / "design_control.json"
PROTOCOL = HERE / "control_protocol.json"
OUT = HERE / "control/r1"
INPUT_PATHS = {
    "q1493_design": HERE / "design_protocol.json",
    "q1493_protocol": HERE / "protocol.json",
    "q1493_source": HERE / "run.py",
    "q1493_preflight": HERE / "known_witness_preflight.json",
    "q1490_witness": HERE.parent /
    "q1490_ordinary_witness_bridge/runs/r2/bridge_result.json",
    "q1491_sat_control": HERE.parent /
    "q1491_ordinary_cnf_witness/runs/r1/receipt.json",
    "q1482_n53_ordinary_input": HERE.parent /
    "q1482_window_s3/inputs/n53_ordinary/input.json",
    "q1482_n53_variables": HERE.parent /
    "q1482_window_s3/inputs/n53_ordinary/variables.txt",
    "q1480_native_solver": HERE.parent /
    "q1480_conditioned_join/native_solver",
    "n53_field": HERE.parent / "q1420_root_theory/n53_field.txt",
    "sage_runtime_info": HERE / "sage_runtime_info.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_and_check() -> tuple[dict, dict, dict, dict]:
    design = json.loads(DESIGN.read_text())
    protocol = json.loads(PROTOCOL.read_text())
    assert design["proposal_id"] == protocol["proposal_id"] == "Q1493"
    assert design["control_id"] == protocol["control_id"] == "Q1493C1"
    assert design["candidate_id"] is protocol["candidate_id"] is None
    assert design["run_id"] is protocol["run_id"] is None
    assert design["isogeny"] == protocol["isogeny"] == "none"
    assert protocol["design_sha256"] == sha(DESIGN)
    assert protocol["source_sha256"] == sha(Path(__file__))
    for label, path in INPUT_PATHS.items():
        expected = design["frozen_inputs_sha256"][label]
        assert sha(path) == expected == protocol["frozen_inputs_sha256"][label], label
    parent_design, parent_protocol = q1493.load_and_check()
    assert parent_design["proposal_id"] == parent_protocol[
        "proposal_id"] == "Q1493"
    witness = json.loads(INPUT_PATHS["q1490_witness"].read_text())
    preflight = json.loads(INPUT_PATHS["q1493_preflight"].read_text())
    assert witness["status"] == preflight["status"] == "PASS"
    assert preflight["rotation"] == design["rotation"] == 44
    assert preflight["rotated_target_preimage_index"] == design[
        "target_preimage_index"] == 141
    assert witness["curve_id"] == design["curve_id"]
    return design, protocol, witness, parent_design


def rotated_witness_pins(meta: dict, witness: dict, k: int) -> list[int]:
    n = meta["degree_n"]
    assert n == 53 and k == 44
    onb = q1493.field.Onb(n)
    curve = q1493.curves.Curve(onb)
    raw_points = [tuple(row["raw_point"])
                  for row in witness["four_raw_lifts"]]
    mids = [tuple(point) for point in witness["raw_pair_mid_points"]]
    rotated_leaves = [onb.toCoords(curve.frob(point, k)[0])
                      for point in raw_points]
    rotated_mids = [onb.toCoords(curve.frob(point, k)[0])
                    for point in mids]
    rotated_target = onb.toCoords(curve.frob(
        tuple(witness["raw_target_point"]), k)[0])
    assert meta["raw_target_x_coordinates"][141] == rotated_target
    groups = (list(zip(meta["leaf_variables"], rotated_leaves)) +
              list(zip(meta["pair_mid_variables"], rotated_mids)) +
              [(meta["target_selector_variables"], 141)])
    assert len(groups) == 7
    pins = []
    for bits, value in groups:
        assert 0 <= value < (1 << len(bits))
        pins.extend(bit if ((value >> j) & 1) else -bit
                    for j, bit in enumerate(bits))
    assert len(pins) == 327 == len({abs(lit) for lit in pins})
    return pins


def extra_pinned_cnf(base: bytes, variables: int, clauses: int,
                     pins: list[int]) -> bytes:
    header, sep, body = base.partition(b"\n")
    assert sep and header == f"p cnf {variables} {clauses}".encode()
    assert body.count(b"\n") == clauses
    return (f"p cnf {variables} {clauses + len(pins)}\n".encode() + body +
            b"".join(f"{lit} 0\n".encode() for lit in pins))


def verify_model(path: Path, raw: bytes, base: bytes, full: bytes,
                 formula, meta: dict, variables: int, clauses: int,
                 original_q: tuple, k: int, selected: int,
                 pins: list[int]) -> dict:
    model = q1493.model_from_file(path)
    q1493.check_cnf(full, model, variables, clauses + 1 + len(pins))
    assert all(model[abs(lit)] == (lit > 0) for lit in pins)
    relation = q1493.replay_model(path, raw, base, formula, meta,
                                  variables, clauses, original_q, k,
                                  selected)
    assert relation["status"] == "verified_four_point_relation"
    assert relation["selected_raw_target_index"] == 141
    assert relation["transported_original_target"] == list(original_q)
    return relation


def run() -> None:
    design, _, witness, parent_design = load_and_check()
    profile = parent_design["profiles"][0]
    k = design["rotation"]
    (raw, base, targets, formula, meta, variables, clauses,
     original_q, rotated_q, selected) = q1493.rotated_input(53, k, profile)
    pins = rotated_witness_pins(meta, witness, k)
    full = extra_pinned_cnf(base, variables, clauses + 1, pins)
    assert not OUT.exists(), "refusing to overwrite attempted control"
    OUT.mkdir(parents=True)
    cnf_path = OUT / "system.cnf"
    target_path = OUT / "targets.txt"
    model_path = OUT / "solver.model.txt"
    stdout_path = OUT / "solver.stdout.txt"
    stderr_path = OUT / "solver.stderr.txt"
    cnf_path.write_bytes(full)
    target_path.write_bytes(targets)
    command = [str(INPUT_PATHS["q1480_native_solver"]),
               str(INPUT_PATHS["n53_field"]), str(cnf_path),
               str(INPUT_PATHS["q1482_n53_variables"]),
               str(model_path), str(design["conflict_cap"]),
               str(design["native_wall_cap_seconds"]),
               str(target_path), str(design["pair_candidate_cap"]),
               design["decision_policy"]]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    began = time.perf_counter_ns()
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
    native_ns = time.perf_counter_ns() - began
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    stdout_path.write_text(stdout)
    stderr_path.write_text(stderr)
    cnf_path.unlink()
    target_path.unlink()
    try:
        report = json.loads(stdout) if stdout.strip() else None
    except json.JSONDecodeError:
        report = None
    relation, verification_error = None, None
    if native_status == "sat" and model_path.exists():
        try:
            relation = verify_model(model_path, raw, base, full, formula,
                                    meta, variables, clauses, original_q,
                                    k, selected, pins)
        except Exception as error:
            verification_error = repr(error)
    status = ("PASS" if relation is not None else
              "MODEL_REJECTED" if verification_error else native_status)
    receipt = {
        "kind": "q1493_rotated_known_witness_cnf_control",
        "proposal_id": "Q1493", "control_id": "Q1493C1",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "status": status, "native_status": native_status,
        "native_exit_code": exit_code, "native_report": report,
        "curve_id": design["curve_id"], "field_degree_n": 53,
        "factor_base_actual_B": design["factor_base_actual_B"],
        "factor_base_folded_columns_K": design[
            "factor_base_folded_columns_K"],
        "factor_base_enumerated_set_sha256": design[
            "factor_base_enumerated_set_sha256"],
        "rotation": k, "target_preimage_index": 141,
        "original_target": list(original_q),
        "rotated_target": list(rotated_q),
        "original_cnf_sha256": hashlib.sha256(raw).hexdigest(),
        "first_window_cnf_sha256": hashlib.sha256(base).hexdigest(),
        "full_pinned_cnf_sha256": hashlib.sha256(full).hexdigest(),
        "pin_count": len(pins),
        "solver_process_wall_ns_exploratory": native_ns,
        "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
        "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
        "peak_child_rss_raw": after.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "solver_stdout_sha256": sha(stdout_path),
        "solver_stderr_sha256": sha(stderr_path),
        "solver_model_sha256": sha(model_path) if model_path.exists()
                               else None,
        "independent_relation": relation,
        "verification_error": verification_error,
        "known_witness_control_only": True,
        "successful_unpinned_solver_cost": None,
        "natural_relation_yield_estimate": None,
        "complete_n131_log2_work": None,
        "challenge_run_admitted": False,
        "design_sha256": sha(DESIGN),
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
    }
    (OUT / "receipt.json").write_text(json.dumps(
        receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status,
                      "conflicts": (report or {}).get("conflicts"),
                      "propagations": (report or {}).get("propagations")},
                     sort_keys=True))


def check() -> None:
    design, _, witness, parent_design = load_and_check()
    profile = parent_design["profiles"][0]
    k = design["rotation"]
    (raw, base, _, formula, meta, variables, clauses,
     original_q, _, selected) = q1493.rotated_input(53, k, profile)
    pins = rotated_witness_pins(meta, witness, k)
    full = extra_pinned_cnf(base, variables, clauses + 1, pins)
    receipt = json.loads((OUT / "receipt.json").read_text())
    assert receipt["source_sha256"] == sha(Path(__file__))
    assert receipt["protocol_sha256"] == sha(PROTOCOL)
    assert receipt["full_pinned_cnf_sha256"] == hashlib.sha256(full).hexdigest()
    assert receipt["pin_count"] == len(pins)
    assert receipt["solver_stdout_sha256"] == sha(OUT /
                                                  "solver.stdout.txt")
    assert receipt["solver_stderr_sha256"] == sha(OUT /
                                                  "solver.stderr.txt")
    if receipt["status"] == "PASS":
        model_path = OUT / "solver.model.txt"
        assert receipt["solver_model_sha256"] == sha(model_path)
        relation = verify_model(model_path, raw, base, full, formula,
                                meta, variables, clauses, original_q, k,
                                selected, pins)
        assert relation == receipt["independent_relation"]
    else:
        assert receipt["independent_relation"] is None
    print(f"Q1493 rotated-CNF witness control: {receipt['status']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    check() if args.check else run()


if __name__ == "__main__":
    main()
