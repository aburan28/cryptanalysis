#!/usr/bin/env python3
"""Run the preregistered functional-inverse/S3-root W24 six-sum SAT gate."""

import argparse
import importlib.util
import json
import platform
import resource
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PDP_PARENT = HERE.parent / "ecc2k130-w24-natural-pdp-20261005"
BASE_PARENT = HERE.parent / "ecc2k130-263-equal-w24-workload-20261005"
sys.path.insert(0, str(PDP_PARENT))

import arithmetic as a  # noqa: E402
import functional as f  # noqa: E402
from xor_circuit import Circuit  # noqa: E402

parent_spec = importlib.util.spec_from_file_location(
    "parent_w24_sat_run", PDP_PARENT / "run.py")
assert parent_spec is not None and parent_spec.loader is not None
parent_run = importlib.util.module_from_spec(parent_spec)
parent_spec.loader.exec_module(parent_run)
CMS = parent_run.CMS
SOURCE_FILES = ("run.py", "functional.py", "selftest.py", "replay_sage.py")


def load_pinned():
    config = json.loads((HERE / "CONFIG.json").read_text())
    pinned = ((PDP_PARENT / "CONFIG.json", "parent_pdp_config_sha256"),
              (PDP_PARENT / "run.py", "parent_run_sha256"),
              (PDP_PARENT / "arithmetic.py", "parent_arithmetic_sha256"),
              (PDP_PARENT / "xor_circuit.py", "parent_xor_circuit_sha256"),
              (BASE_PARENT / "base_selection.json",
               "parent_base_selection_sha256"),
              (BASE_PARENT / "primary_workload.json",
               "parent_primary_workload_sha256"),
              (CMS, "solver_binary_sha256"))
    for path, key in pinned:
        assert parent_run.digest(path) == config[key], (path, key)
    _, base, workload = parent_run.load_pinned()
    assert config["curve_id"] == workload["source_curve_id"]
    assert config["primary_workload_id"] == workload["workload_id"]
    assert config["source_last_selected_mask"] == a.LAST_MASK
    assert config["source_usable_points_B"] == base["source"][
        "selected_usable_points_B"]
    assert config["summands"] == 6
    return config, base, workload


def build_formula(circuit, basis, half_basis, trace_positions, fibers,
                  pinned_masks=None, pinned_fiber=None):
    target_us = []
    for point in fibers:
        if point is None or point[0] == 1:
            raise ValueError("frozen target fiber has exceptional x")
        target_us.append(a.inv(point[0] ^ 1))
    s0, s1 = circuit.variable(), circuit.variable()
    s01 = circuit.and_(s0, s1)
    u0, u1, u2, u3 = target_us
    target_u = circuit.linear_element(
        (s0, s1, s01), (u0 ^ u1, u0 ^ u2, u0 ^ u1 ^ u2 ^ u3), u0)
    target_w = circuit.add(circuit.square(target_u), target_u)
    if pinned_fiber is not None:
        circuit.pin(s0, bool(pinned_fiber & 1))
        circuit.pin(s1, bool(pinned_fiber & 2))

    mask_rows, leaf_us, leaf_ws = [], [], []
    for slot in range(6):
        row = [circuit.variable() for _ in range(24)]
        circuit.forbid_above(row, a.LAST_MASK)
        circuit.require_nonzero(row)
        if pinned_masks is not None:
            for bit, wire in enumerate(row):
                circuit.pin(wire, bool(pinned_masks[slot] & (1 << bit)))
        w = circuit.linear_element(row, basis)
        u = circuit.linear_element(row, half_basis)
        inverse = f.inverse_131(circuit, w)
        trace_wire = circuit.xor(inverse[i] for i in trace_positions)
        circuit.require_zero([trace_wire])
        mask_rows.append(row)
        leaf_us.append(u)
        leaf_ws.append(w)

    root_choices, intermediates, branch_indicators = [], [], []
    current_u, current_w = leaf_us[0], leaf_ws[0]
    for slot in range(1, 5):
        choice = circuit.variable()
        next_u, next_w, indicators = f.s3_root(
            circuit, current_u, current_w, leaf_us[slot], leaf_ws[slot],
            choice)
        circuit.require_nonzero(next_u)
        root_choices.append(choice)
        intermediates.append(next_u)
        branch_indicators.append(indicators)
        current_u, current_w = next_u, next_w
    # The fifth link is a relation to the selected fixed target fiber.
    lhs = circuit.mul(circuit.mul(current_w, leaf_ws[5]), target_w)
    rhs = circuit.square(circuit.add_many(
        (current_u, leaf_us[5], target_u)))
    circuit.require_zero(circuit.add(lhs, rhs))
    return {"mask_rows": mask_rows, "selectors": [s0, s1],
            "intermediates": intermediates, "root_choices": root_choices,
            "branch_indicators": branch_indicators, "target_us": target_us}


def decode_model(model, meta):
    def bit(wire):
        if wire == 0:
            return 0
        if wire == -1:
            return 1
        if wire not in model:
            raise ValueError("SAT output omits a model bit needed for replay")
        return int(model[wire])

    masks = [sum(bit(wire) << i for i, wire in enumerate(row))
             for row in meta["mask_rows"]]
    selector = sum(bit(wire) << i for i, wire in
                   enumerate(meta["selectors"]))
    intermediates = [sum(bit(wire) << i for i, wire in enumerate(row))
                     for row in meta["intermediates"]]
    return masks, selector, intermediates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("planted", "ordinary"), required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--profile-only", action="store_true")
    parser.add_argument("--control-replay", type=Path)
    args = parser.parse_args()
    if not __debug__:
        parser.error("assertions must remain enabled")
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out / "receipt.json").exists() or (out / "system.xcnf").exists():
        parser.error("run directory already contains an attempt")
    if not (out / "runtime-info.json").is_file():
        parser.error("save checked ./sage --runtime-info in the run directory first")
    config, base, workload = load_pinned()
    if args.mode == "ordinary" and not args.profile_only:
        if args.control_replay is None:
            parser.error("ordinary attempt requires independent planted replay")
        control = json.loads(args.control_replay.read_text())
        if control.get("status") != "PASS_PLANTED_GROUP_REPLAY":
            parser.error("planted replay did not pass")

    started = time.perf_counter()
    basis = a.source_basis()
    half_basis = tuple(a.halftrace(w) for w in basis)
    trace_positions = parent_run.field_trace_positions()
    if args.mode == "planted":
        q, fibers, pins, raw_points, pinned_fiber = parent_run.control_input(
            base, basis)
    else:
        q, fibers = parent_run.ordinary_input(workload)
        pins = raw_points = pinned_fiber = None
    query_seconds = time.perf_counter() - started
    circuit = Circuit(a.N, a.LOW_TERMS,
                      memory_limit_bytes=config["peak_rss_limit_bytes"])
    build_start = time.perf_counter()

    def alarm_handler(_signum, _frame):
        raise TimeoutError("formula build exceeded frozen wall limit")

    signal.signal(signal.SIGALRM, alarm_handler)
    signal.alarm(config["build_wall_limit_seconds"])
    try:
        meta = build_formula(circuit, basis, half_basis, trace_positions,
                             fibers, pins, pinned_fiber)
        circuit.write(out / "system.xcnf")
    except Exception as exc:
        failure = {
            "schema": "ecc2k130-w24-functional-s3-run-v1",
            "mode": args.mode,
            "status": ("build_timeout" if isinstance(exc, TimeoutError) else
                       "build_memory_limit" if isinstance(exc, MemoryError) else
                       "build_error"),
            "error_type": type(exc).__name__, "error": str(exc),
            "query_seconds": query_seconds,
            "build_seconds": time.perf_counter()-build_start,
            "config_sha256": parent_run.digest(HERE / "CONFIG.json"),
            "source_sha256": {name: parent_run.digest(HERE / name)
                              for name in SOURCE_FILES},
            "sage_runtime_info_sha256": parent_run.digest(out / "runtime-info.json"),
            "candidate_id": None, "verified_logarithm": None,
            "online_wall_time": None, "rho_ratio": None,
        }
        parent_run.save(out / "receipt.json", failure)
        print(json.dumps(failure, sort_keys=True), flush=True)
        return
    finally:
        signal.alarm(0)
    build_seconds = time.perf_counter() - build_start
    xcnf = out / "system.xcnf"
    report = {
        "schema": "ecc2k130-w24-functional-s3-run-v1",
        "candidate_id": None,
        "proposal_id": config["proposal_id"],
        "mode": args.mode,
        "profile_only": args.profile_only,
        "workload_id": config["primary_workload_id"] if args.mode == "ordinary" else None,
        "public_q": list(q),
        "raw_fibers": [list(point) for point in fibers],
        "planted_masks": pins,
        "planted_raw_points": [list(p) for p in raw_points] if raw_points else None,
        "planted_fiber_index": pinned_fiber,
        "source_usable_points_B": config["source_usable_points_B"],
        "source_signed_columns": config["source_signed_columns"],
        "query_seconds": query_seconds,
        "build_seconds": build_seconds,
        "variables": circuit.next_var - 1,
        "and_gates": circuit.and_count,
        "cnf_clauses": len(circuit.clauses),
        "xor_rows": len(circuit.xors),
        "xcnf_bytes": xcnf.stat().st_size,
        "xcnf_sha256": parent_run.digest(xcnf),
        "config_sha256": parent_run.digest(HERE / "CONFIG.json"),
        "parent_primary_workload_sha256": config["parent_primary_workload_sha256"],
        "sage_runtime_info_sha256": parent_run.digest(out / "runtime-info.json"),
        "source_sha256": {name: parent_run.digest(HERE / name)
                          for name in SOURCE_FILES},
        "solver_binary_sha256": parent_run.digest(CMS),
        "solver_command": None,
        "solver_seconds": None,
        "solver_exit_code": None,
        "solver_status": None,
        "solver_peak_rss_bytes": None,
        "memory_cap_method": "builder_ru_maxrss_check_4096_gates; solver_ps_rss_poll_500ms",
        "model": None,
        "diagnostic_group_replay": None,
        "independent_group_replay": None,
        "status": "profile_only" if args.profile_only else "unresolved",
        "host": {"system": platform.system(), "machine": platform.machine(),
                 "python": sys.version.split()[0], "cpu_isolation": "unverified"},
    }
    if not args.profile_only:
        wall = (config["planted_wall_limit_seconds"] if args.mode == "planted"
                else config["ordinary_wall_limit_seconds"])
        conflicts = (config["planted_conflict_limit"] if args.mode == "planted"
                     else config["ordinary_conflict_limit"])
        command = [str(CMS), f"--maxtime={wall}",
                   f"--maxconfl={conflicts}", "--threads=1", "--random=0",
                   "--maxsol=1", "--printsol=1", str(xcnf)]
        report["solver_command"] = command
        solve_start = time.perf_counter()
        stop_reason = None
        observed_peak = 0
        with (out / "solver.stdout.txt").open("x") as stdout, \
             (out / "solver.stderr.txt").open("x") as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
            try:
                while process.poll() is None:
                    if time.perf_counter() - solve_start >= wall:
                        stop_reason = "timeout"
                        process.kill()
                        break
                    try:
                        rss = parent_run.process_rss_bytes(process.pid)
                    except (RuntimeError, subprocess.TimeoutExpired,
                            OSError) as monitor_error:
                        stop_reason = "memory_monitor_failure"
                        report["memory_monitor_error_type"] = type(monitor_error).__name__
                        report["memory_monitor_error"] = str(monitor_error)
                        process.kill()
                        break
                    if rss is not None:
                        observed_peak = max(observed_peak, rss)
                        if rss > config["peak_rss_limit_bytes"]:
                            stop_reason = "solver_memory_limit"
                            process.kill()
                            break
                    time.sleep(0.5)
            finally:
                report["solver_exit_code"] = process.wait()
        report["solver_peak_rss_bytes"] = observed_peak
        report["solver_seconds"] = time.perf_counter() - solve_start
        report["solver_stdout_sha256"] = parent_run.digest(out / "solver.stdout.txt")
        report["solver_stderr_sha256"] = parent_run.digest(out / "solver.stderr.txt")
        status, assignment = parent_run.read_solver_output(out / "solver.stdout.txt")
        report["solver_status"] = status
        if stop_reason is not None:
            report["status"] = stop_reason
        elif status == "SATISFIABLE":
            masks, selector, intermediates = decode_model(assignment, meta)
            report["model"] = {"masks": masks,
                               "fiber_index": selector,
                               "intermediate_us": intermediates,
                               "root_choices": [assignment.get(wire)
                                                for wire in meta["root_choices"]],
                               "assigned_variables": len(assignment)}
            diagnostic = parent_run.diagnostic_replay(masks, selector,
                                                       intermediates, q,
                                                       fibers, basis)
            report["diagnostic_group_replay"] = diagnostic
            report["status"] = ("candidate_group_relation" if diagnostic["valid"]
                                else "sat_invalid")
        elif status == "UNSATISFIABLE":
            report["status"] = "unsat"
        else:
            report["status"] = "unresolved"
    report["self_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report["child_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    parent_run.save(out / "receipt.json", report)
    print(json.dumps({key: report[key] for key in
                      ("mode", "status", "variables", "and_gates", "xor_rows",
                       "cnf_clauses", "xcnf_bytes", "build_seconds",
                       "solver_seconds", "solver_status")}, sort_keys=True),
          flush=True)


if __name__ == "__main__":
    main()
