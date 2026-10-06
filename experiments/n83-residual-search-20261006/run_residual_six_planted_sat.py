#!/usr/bin/env python3
"""Solve the six hidden factors after publishing a planted first pair."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import resource
import sys
import time

import psutil

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "n83-costed-candidate-screen-20261005"
sys.path.insert(0, str(PRIOR))
from run_shifted_sat_branch import build, parse_model, replay, verify_model  # noqa: E402
from run_long_unpinned_sat import run_solver  # noqa: E402

PROTOCOL = HERE / "residual_six_protocol.json"
FIXTURE = HERE / "runs/planted_pair01_fixture_v1/public_input.json"
OLD_PUBLIC = HERE.parent / "hamming-ic-e2e-20260929/runs/n83_w34_sat_fixture_v1/public_input.json"
CMS = Path("/opt/homebrew/bin/cryptominisat5")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main(out: Path) -> None:
    out = out.resolve()
    if out.exists():
        raise FileExistsError("residual-six SAT output is immutable")
    protocol = json.loads(PROTOCOL.read_text())
    fixture = json.loads(FIXTURE.read_text())
    old = json.loads(OLD_PUBLIC.read_text())
    geometry_path = PRIOR / "runs/shifted_m8_d11_v1/geometry.json"
    geometry = json.loads(geometry_path.read_text())
    assert fixture["candidate_id"] is None
    assert fixture["curve_id"] == protocol["curve_id"] == geometry["curve_id"]
    assert fixture["protocol_sha256"] == sha(PROTOCOL)
    assert fixture["remaining_slot_indices"] == protocol["remaining_slot_indices"]
    assert fixture["source_public_fixture_sha256"] == \
        protocol["source_public_fixture_sha256"]
    assert sha(CMS) == protocol["solver_binary_sha256"]
    assert geometry["arity"] == 8 and geometry["dimension"] == 11
    six_geometry = {
        "arity": 6, "dimension": geometry["dimension"],
        "slot_normal_basis_indices": [geometry["slot_normal_basis_indices"][i]
                                      for i in protocol["remaining_slot_indices"]],
    }
    conjugates = [int(value) for value in old["normal_conjugates_polynomial_bits_decimal"]]
    assert len(conjugates) == 83
    target_xy = fixture["raw_residual_target"]
    target_q = fixture["projected_residual_target_Q"]
    target_x = int(target_xy[0])
    out.mkdir(parents=True)
    save(out / "started.json", {
        "kind": "n83_shifted_m8_residual_six_sat_start",
        "candidate_id": None, "curve_id": protocol["curve_id"],
        "public_fixture_sha256": sha(FIXTURE),
        "geometry_sha256": sha(geometry_path),
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": {
            "runner": sha(Path(__file__)),
            "solver_wrapper": sha(HERE / "run_long_unpinned_sat.py"),
            "circuit_builder": sha(PRIOR / "run_shifted_sat_branch.py"),
        },
        "solver_binary_sha256": sha(CMS),
        "target_R_raw": target_xy,
        "target_Q_projected": target_q,
        "architecture": platform.machine(), "os": platform.platform(),
    })
    started_ns = time.perf_counter_ns()
    report = {
        "schema_version": 1,
        "kind": "n83_shifted_m8_pair_prefix_residual_six_sat_attempt",
        "status": "INCOMPLETE", "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "remaining_slot_indices": protocol["remaining_slot_indices"],
        "target_kind": "planted_pair_prefix_control",
        "branch_target_x_decimal": str(target_x),
        "target_Q": target_q,
        "claim_boundary": protocol["claim_boundary"],
    }
    try:
        build_started = time.perf_counter_ns()
        circuit, rows = build(six_geometry, conjugates, target_x, None, None)
        report["circuit_build_wall_ns"] = time.perf_counter_ns() - build_started
        report["circuit"] = {
            "variables": circuit.next_var - 1,
            "and_gates": circuit.and_count,
            "cnf_clauses": len(circuit.clauses),
            "xor_rows": len(circuit.xors),
        }
        xcnf = out / "branch.xcnf"
        write_started = time.perf_counter_ns()
        circuit.write(xcnf)
        report["xcnf_write_wall_ns"] = time.perf_counter_ns() - write_started
        report["xcnf_bytes"] = xcnf.stat().st_size
        report["xcnf_sha256"] = sha(xcnf)
        parent_rss = psutil.Process().memory_info().rss
        report["parent_rss_after_encoding_bytes"] = parent_rss
        if parent_rss >= protocol["max_process_tree_rss_bytes"]:
            report["status"] = "ENCODING_RSS_GUARD"
        elif (time.perf_counter_ns() - started_ns) / 1e9 >= protocol["external_wall_seconds"]:
            report["status"] = "ENCODING_WALL_GUARD"
        else:
            report["solver"] = run_solver(xcnf, out, protocol, started_ns)
            solver_text = (out / "solver.stdout.txt").read_text(errors="replace")
            model = parse_model(solver_text)
            if model is None:
                report["status"] = ("UNSAT" if "s UNSATISFIABLE" in solver_text else
                                    "BOUNDED_UNKNOWN" if report["solver"]["guard"] else
                                    "SOLVER_UNKNOWN")
            elif not verify_model(circuit, model):
                report["status"] = "MODEL_INVALID"
            else:
                masks = [sum((1 << bit) for bit, variable in enumerate(mask_row)
                             if model[variable]) for mask_row in rows]
                x_codes = [0] * 6
                for slot, mask in enumerate(masks):
                    for bit, basis_index in enumerate(six_geometry["slot_normal_basis_indices"][slot]):
                        if mask & (1 << bit):
                            x_codes[slot] ^= conjugates[basis_index]
                report["model"] = {
                    "mask_decimal": [str(mask) for mask in masks],
                    "factor_x_decimal": [str(value) for value in x_codes],
                    "cnf_xor_verified": True,
                }
                check_started = time.perf_counter_ns()
                report["group_check"] = replay(
                    x_codes, target_q, target_xy,
                    geometry_path.parent / "representatives.json.gz")
                report["group_check_wall_ns"] = time.perf_counter_ns() - check_started
                report["status"] = ("SAT_GROUP_VERIFIED_PENDING_SAGE" if
                                    report["group_check"]["verified"] else
                                    "SAT_UNVERIFIED_GROUP")
        report["self_peak_rss_highwater"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report["self_peak_rss_unit"] = "bytes" if platform.system() == "Darwin" else "kilobytes"
    except Exception as error:
        report["status"] = "ERROR"
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["attempt_wall_ns"] = time.perf_counter_ns() - started_ns
        report["protocol_sha256"] = sha(PROTOCOL)
        report["public_fixture_sha256"] = sha(FIXTURE)
        report["started_sha256"] = sha(out / "started.json")
        report["source_sha256"] = sha(Path(__file__))
        report["online_target_wall_ns"] = None
        report["rho_online_wall_ns"] = None
        report["online_speedup"] = None
        save(out / "receipt.json", report)
        print(json.dumps({"status": report["status"],
                          "attempt_wall_seconds": report["attempt_wall_ns"] / 1e9,
                          "guard": report.get("solver", {}).get("guard")},
                         sort_keys=True), flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: run_residual_six_planted_sat.py OUTPUT_DIRECTORY")
    main(Path(sys.argv[1]))
