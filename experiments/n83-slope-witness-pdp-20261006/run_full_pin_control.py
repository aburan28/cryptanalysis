#!/usr/bin/env python3
"""Planted exact-five-point positive control for the N83 slope circuit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from run_slope_branch import (HERE, PRIVATE, PROTOCOL, PUBLIC, REPS, SOLVER,
                              SlopeWitnessCircuit, parse_model, replay,
                              verify_model)
from indexed_factor import factor, pin_positions

SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main(out: Path) -> None:
    out = out.resolve()
    if out.exists():
        raise FileExistsError("positive-control output is immutable")
    out.mkdir(parents=True)
    with (out / "sage_runtime_info.json").open("wb") as f:
        subprocess.run([str(SAGE), "--runtime-info"], stdout=f, check=True)
    protocol = json.loads(PROTOCOL.read_text())
    public = json.loads(PUBLIC.read_text())
    private = json.loads(PRIVATE.read_text())
    assert sha(PUBLIC) == protocol["source_public_fixture_sha256"]
    assert sha(PRIVATE) == protocol["regenerated_private_fixture_sha256_local_only"]
    assert sha(REPS) == protocol["full_w34_representatives_sha256"]
    assert sha(SOLVER) == protocol["solver_binary_sha256"]
    assert private["public_input_sha256"] == sha(PUBLIC)
    fiber = public["planted"]["raw_target_fiber"][0]
    assert [fiber["x"], fiber["y"]] == private["raw_sum"]
    sources = {
        "control": Path(__file__),
        "branch_runner": HERE / "run_slope_branch.py",
        "slope_circuit": HERE / "slope_witness_circuit.py",
        "indexed_factor": HERE.parent / "n83-indexed-factor-pdp-20261006/indexed_factor.py",
    }
    save(out / "started.json", {
        "kind": "n83_slope_witness_fully_pinned_start",
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "protocol_sha256": sha(PROTOCOL),
        "public_fixture_sha256": sha(PUBLIC),
        "private_fixture_sha256_local_only": sha(PRIVATE),
        "source_sha256": {name: sha(path) for name, path in sources.items()},
        "solver_binary_sha256": sha(SOLVER),
        "sage_runtime_info_sha256": sha(out / "sage_runtime_info.json"),
    })
    started = time.perf_counter_ns()
    report = {
        "schema_version": 1,
        "kind": "n83_slope_witness_fully_pinned_control",
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "status": "INCOMPLETE",
        "claim_boundary": "Private masks and all five raw factor points are supplied. This is a circuit/model correctness control only; it does not estimate search cost or natural relation yield.",
    }
    try:
        began = time.perf_counter_ns()
        builder = SlopeWitnessCircuit(83, [0, 2, 4, 7])
        c = builder.circuit
        conjugates = [int(v) for v in public["normal_conjugates_polynomial_bits_decimal"]]
        encoded = [factor(c, conjugates) for _ in range(5)]
        witness = builder.require_sum([item["x"] for item in encoded],
                                      int(fiber["x"]), int(fiber["y"]))
        for item, (x_wires, y_wires), selected in zip(
                encoded, witness["factors"], private["selected"]):
            pin_positions(c, item, selected["mask"])
            assert len(x_wires) == len(y_wires) == 83
            c.require_zero(c.add(y_wires, c.constant(int(selected["raw_point"][1]))))
        report["circuit_build_wall_ns"] = time.perf_counter_ns() - began
        report["circuit"] = {
            "variables": c.next_var - 1,
            "and_gates": c.and_count,
            "cnf_clauses": len(c.clauses),
            "xor_rows": len(c.xors),
        }
        began = time.perf_counter_ns()
        xcnf = out / "control.xcnf"
        c.write(xcnf)
        report["xcnf_write_wall_ns"] = time.perf_counter_ns() - began
        report["xcnf_sha256"] = sha(xcnf)
        report["xcnf_bytes"] = xcnf.stat().st_size
        argv = [str(SOLVER), "--threads=1", "--maxtime=120",
                "--maxconfl=1000000", str(xcnf)]
        began = time.perf_counter_ns()
        with (out / "solver.stdout.txt").open("wb") as stdout, \
             (out / "solver.stderr.txt").open("wb") as stderr:
            child = subprocess.run(argv, stdout=stdout, stderr=stderr,
                                   timeout=900, check=False)
        report["solver_wall_ns"] = time.perf_counter_ns() - began
        report["solver_exit_code"] = child.returncode
        report["solver_stdout_sha256"] = sha(out / "solver.stdout.txt")
        stdout_text = (out / "solver.stdout.txt").read_text(errors="replace")
        model = parse_model(stdout_text)
        if model is None:
            report["status"] = "UNSAT" if "s UNSATISFIABLE" in stdout_text else "BOUNDED_UNKNOWN"
        elif not verify_model(c, model):
            report["status"] = "MODEL_INVALID"
        else:
            checked = replay(model, encoded, witness, conjugates,
                             public, "planted", fiber)
            if checked["verified"]:
                save(out / "private_model.json", checked)
                report["private_model_sha256_local_only"] = sha(out / "private_model.json")
                report["status"] = "SAT_GROUP_VERIFIED_PENDING_SAGE"
            else:
                report["status"] = "SAT_UNVERIFIED_GROUP"
                report["group_check_error"] = checked["reason"]
    finally:
        report["total_wall_ns"] = time.perf_counter_ns() - started
        report["started_sha256"] = sha(out / "started.json")
        report["online_target_wall_ns"] = None
        report["rho_online_wall_ns"] = None
        report["online_speedup"] = None
        save(out / "receipt.json", report)
        print(json.dumps({"status": report["status"],
                          "wall_seconds": report["total_wall_ns"] / 1e9},
                         sort_keys=True), flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: run_full_pin_control.py OUT_DIR")
    main(Path(sys.argv[1]))
