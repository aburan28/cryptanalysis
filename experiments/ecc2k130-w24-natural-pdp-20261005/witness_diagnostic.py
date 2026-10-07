#!/usr/bin/env python3
"""Pin predeclared planted inverse/intermediate witnesses in the v1 XCNF."""

import argparse
import json
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

import arithmetic as a
import run
from xor_circuit import Circuit


HERE = Path(__file__).resolve().parent
SOURCES = ("arithmetic.py", "xor_circuit.py", "run.py",
           "witness_diagnostic.py")


def witness_values(masks, raw_points, basis, fibers, fiber_index):
    inverses = [a.inv(a.source_w(mask, basis)) for mask in masks]
    partial = raw_points[0]
    intermediates = []
    for point in raw_points[1:5]:
        partial = a.add(partial, point)
        assert partial is not None and partial[0] != 1
        intermediates.append(a.inv(partial[0] ^ 1))
    us = [a.halftrace(a.source_w(mask, basis)) for mask in masks]
    chain = [us[0]] + intermediates + [a.inv(fibers[fiber_index][0] ^ 1)]
    for slot in range(1, 6):
        assert a.s3_cleared(chain[slot-1], us[slot], chain[slot]) == 0
    return inverses, intermediates


def pin_element(circuit, wires, value):
    for bit, wire in enumerate(wires):
        circuit.pin(wire, (value >> bit) & 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pin", choices=("both", "inverse", "intermediate"),
                        required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if not __debug__:
        parser.error("assertions must remain enabled")
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out / "receipt.json").exists() or (out / "system.xcnf").exists():
        parser.error("run directory already contains an attempt")
    if not (out / "runtime-info.json").is_file():
        parser.error("save checked ./sage --runtime-info before the run")
    protocol = json.loads((HERE / "DIAGNOSTIC_CONFIG.json").read_text())
    previous = HERE / "runs/v1-planted/receipt.json"
    assert run.digest(previous) == protocol["parent_planted_receipt_sha256"]
    parent = json.loads(previous.read_text())
    assert parent["xcnf_sha256"] == protocol["parent_planted_xcnf_sha256"]
    assert parent["status"] == "unresolved"
    config, base, _workload = run.load_pinned()
    started = time.perf_counter()
    basis = a.source_basis()
    half_basis = tuple(a.halftrace(value) for value in basis)
    q, fibers, masks, raw_points, fiber_index = run.control_input(base, basis)
    assert masks == parent["planted_masks"]
    assert list(q) == parent["public_q"]
    assert fiber_index == parent["planted_fiber_index"]
    inverses, intermediates = witness_values(masks, raw_points, basis,
                                               fibers, fiber_index)
    query_seconds = time.perf_counter()-started

    circuit = Circuit(a.N, a.LOW_TERMS,
                      memory_limit_bytes=protocol["peak_rss_limit_bytes"])
    build_start = time.perf_counter()
    meta = run.build_formula(circuit, basis, half_basis,
                             run.field_trace_positions(), fibers,
                             masks, fiber_index)
    baseline = out / "baseline.xcnf"
    circuit.write(baseline)
    assert run.digest(baseline) == protocol["parent_planted_xcnf_sha256"]
    baseline.unlink()
    original_clauses = len(circuit.clauses)
    if args.pin in ("both", "inverse"):
        for row, value in zip(meta["inverse_rows"], inverses):
            pin_element(circuit, row, value)
    if args.pin in ("both", "intermediate"):
        for row, value in zip(meta["intermediates"], intermediates):
            pin_element(circuit, row, value)
    added_clauses = len(circuit.clauses)-original_clauses
    xcnf = out / "system.xcnf"
    circuit.write(xcnf)
    build_seconds = time.perf_counter()-build_start

    wall = protocol["solver_wall_limit_seconds"]
    conflicts = protocol["solver_conflict_limit"]
    command = [str(run.CMS), f"--maxtime={wall}",
               f"--maxconfl={conflicts}", "--threads=1", "--random=0",
               "--maxsol=1", "--printsol=1", str(xcnf)]
    solve_start = time.perf_counter()
    stop_reason = None
    observed_peak = 0
    with (out / "solver.stdout.txt").open("x") as stdout, \
         (out / "solver.stderr.txt").open("x") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        try:
            while process.poll() is None:
                if time.perf_counter()-solve_start >= wall:
                    stop_reason = "timeout"
                    process.kill()
                    break
                try:
                    rss = run.process_rss_bytes(process.pid)
                except (RuntimeError, subprocess.TimeoutExpired):
                    stop_reason = "memory_monitor_failure"
                    process.kill()
                    break
                if rss is not None:
                    observed_peak = max(observed_peak, rss)
                    if rss > protocol["peak_rss_limit_bytes"]:
                        stop_reason = "solver_memory_limit"
                        process.kill()
                        break
                time.sleep(0.5)
        finally:
            exit_code = process.wait()
    solver_seconds = time.perf_counter()-solve_start
    solver_status, assignment = run.read_solver_output(out / "solver.stdout.txt")
    model = None
    diagnostic = None
    if stop_reason is not None:
        status = stop_reason
    elif solver_status == "SATISFIABLE":
        decoded_masks, selector, decoded_intermediates = run.decode_model(
            assignment, meta)
        model = {"masks": decoded_masks, "fiber_index": selector,
                 "intermediate_us": decoded_intermediates,
                 "assigned_variables": len(assignment)}
        diagnostic = run.diagnostic_replay(decoded_masks, selector,
                                           decoded_intermediates,
                                           q, fibers, basis)
        status = ("candidate_group_relation" if diagnostic["valid"]
                  else "sat_invalid")
    elif solver_status == "UNSATISFIABLE":
        status = "unsat"
    else:
        status = "unresolved"
    self_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    child_peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    if sys.platform != "darwin":
        self_peak *= 1024
        child_peak *= 1024
    report = {
        "schema": "ecc2k130-w24-natural-pdp-planted-witness-run-v1",
        "candidate_id": None, "diagnostic_only": True,
        "mode": "planted", "pin_variant": args.pin,
        "status": status, "solver_status": solver_status,
        "solver_exit_code": exit_code, "solver_command": command,
        "query_seconds": query_seconds, "build_seconds": build_seconds,
        "solver_seconds": solver_seconds,
        "variables": circuit.next_var-1,
        "and_gates": circuit.and_count,
        "cnf_clauses": len(circuit.clauses),
        "xor_rows": len(circuit.xors),
        "added_unit_clauses": added_clauses,
        "xcnf_bytes": xcnf.stat().st_size,
        "xcnf_sha256": run.digest(xcnf),
        "solver_stdout_sha256": run.digest(out / "solver.stdout.txt"),
        "solver_stderr_sha256": run.digest(out / "solver.stderr.txt"),
        "sage_runtime_info_sha256": run.digest(out / "runtime-info.json"),
        "config_sha256": run.digest(HERE / "CONFIG.json"),
        "diagnostic_config_sha256": run.digest(HERE / "DIAGNOSTIC_CONFIG.json"),
        "parent_planted_xcnf_sha256": protocol["parent_planted_xcnf_sha256"],
        "source_sha256": {name: run.digest(HERE / name) for name in SOURCES},
        "solver_binary_sha256": run.digest(run.CMS),
        "public_q": list(q),
        "raw_fibers": [list(point) for point in fibers],
        "planted_masks": masks,
        "planted_raw_points": [list(point) for point in raw_points],
        "planted_fiber_index": fiber_index,
        "model": model,
        "diagnostic_group_replay": diagnostic,
        "independent_group_replay": None,
        "self_peak_rss_bytes": self_peak,
        "child_peak_rss_bytes": child_peak,
        "solver_peak_rss_bytes": observed_peak,
        "host": {"system": platform.system(), "machine": platform.machine(),
                 "python": sys.version.split()[0], "cpu_isolation": "unverified"},
        "natural_target_attempts": 0,
        "verified_logarithm": None,
        "online_wall_time": None,
        "rho_ratio": None,
    }
    run.save(out / "receipt.json", report)
    print(json.dumps({key: report[key] for key in
                      ("pin_variant", "status", "solver_status",
                       "solver_seconds", "added_unit_clauses")},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
