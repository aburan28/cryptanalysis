#!/usr/bin/env python3
"""Build and run the preregistered exact source W24/m6 native-XOR SAT gate."""

import argparse
import hashlib
import itertools
import json
import platform
import resource
import signal
import subprocess
import sys
import time
from pathlib import Path

import arithmetic as a
from xor_circuit import Circuit


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "ecc2k130-263-equal-w24-workload-20261005"
CMS = Path("/opt/homebrew/bin/cryptominisat5")
FILES = ("arithmetic.py", "xor_circuit.py", "run.py")


def digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_pinned():
    config = json.loads((HERE / "CONFIG.json").read_text())
    for name, key in (("CONFIG.json", "parent_config_sha256"),
                      ("base_selection.json", "parent_base_selection_sha256"),
                      ("primary_workload.json", "parent_primary_workload_sha256")):
        assert digest(PARENT / name) == config[key], name
    assert digest(CMS) == config["solver_binary_sha256"]
    base = json.loads((PARENT / "base_selection.json").read_text())
    workload = json.loads((PARENT / "primary_workload.json").read_text())
    assert workload["workload_id"] == config["parent_workload_id"]
    assert workload["target_count"] == 1
    assert workload["source_curve_id"] == config["curve_id"]
    assert workload["subgroup_order"] == a.R
    assert base["source"]["last_selected_mask"] == config[
        "source_last_selected_mask"] == a.LAST_MASK
    assert base["source"]["selected_usable_points_B"] == config[
        "source_usable_points_B"]
    return config, base, workload


def control_input(base, basis):
    masks = base["source"]["control_masks_selection_order"][:6]
    assert len(masks) == 6 and len(set(masks)) == 6
    raw_points = [a.raw_point(mask, basis) for mask in masks]
    prefix = raw_points[0]
    for point in raw_points[1:]:
        next_prefix = a.add(prefix, point)
        if next_prefix is None or prefix[0] == 1 or next_prefix[0] == 1:
            raise ValueError("predeclared control has an exceptional S3 chain")
        assert a.s3_cleared(a.inv(prefix[0] ^ 1),
                            a.inv(point[0] ^ 1),
                            a.inv(next_prefix[0] ^ 1)) == 0
        prefix = next_prefix
    q = a.scalar_mul(4, prefix)
    assert q is not None and a.scalar_mul(a.R, q) is None
    fibers = a.target_fibers(q)
    assert prefix in fibers
    return q, fibers, masks, raw_points, fibers.index(prefix)


def ordinary_input(workload):
    q = tuple(workload["targets"][0]["source"])
    assert a.on_curve(q) and a.scalar_mul(a.R, q) is None
    return q, a.target_fibers(q)


def field_trace_positions():
    return [i for i in range(a.N) if a.trace(1 << i)]


def build_formula(circuit, basis, half_basis, trace_positions, fibers,
                  pinned_masks=None, pinned_fiber=None):
    target_us = []
    for point in fibers:
        if point is None or point[0] == 1:
            raise ValueError("predeclared target fiber has exceptional x")
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
        if pinned_masks is not None:
            for bit, wire in enumerate(row):
                circuit.pin(wire, bool(pinned_masks[slot] & (1 << bit)))
        w = circuit.linear_element(row, basis)
        u = circuit.linear_element(row, half_basis)
        inverse = [circuit.variable() for _ in range(a.N)]
        circuit.require_zero(circuit.add(circuit.mul(w, inverse),
                                         circuit.constant(1)))
        circuit.require_zero([circuit.xor(inverse[i]
                                          for i in trace_positions)])
        mask_rows.append(row)
        leaf_us.append(u)
        leaf_ws.append(w)

    intermediates = [[circuit.variable() for _ in range(a.N)]
                     for _ in range(4)]
    for intermediate in intermediates:
        circuit.require_nonzero(intermediate)
    current_u, current_w = leaf_us[0], leaf_ws[0]
    for slot in range(1, 6):
        next_u = intermediates[slot-1] if slot < 5 else target_u
        next_w = (circuit.add(circuit.square(next_u), next_u)
                  if slot < 5 else target_w)
        lhs = circuit.mul(circuit.mul(current_w, leaf_ws[slot]), next_w)
        rhs = circuit.square(circuit.add_many(
            (current_u, leaf_us[slot], next_u)))
        circuit.require_zero(circuit.add(lhs, rhs))
        current_u, current_w = next_u, next_w
    return {"mask_rows": mask_rows, "selectors": [s0, s1],
            "intermediates": intermediates, "target_us": target_us}


def read_solver_output(path):
    status = None
    assignment = {}
    with path.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            if line.startswith("s "):
                status = line.strip()[2:]
            elif line.startswith("v "):
                for word in line[2:].split():
                    value = int(word)
                    if value:
                        assignment[abs(value)] = value > 0
    return status, assignment


def decode_model(model, meta):
    necessary = [wire for row in meta["mask_rows"] for wire in row]
    necessary += meta["selectors"]
    necessary += [wire for row in meta["intermediates"] for wire in row]
    if any(wire not in model for wire in necessary):
        raise ValueError("SAT output omits a model bit needed for replay")
    masks = [sum(int(model[wire]) << bit for bit, wire in enumerate(row))
             for row in meta["mask_rows"]]
    selector = sum(int(model[wire]) << bit
                   for bit, wire in enumerate(meta["selectors"]))
    intermediate_us = [sum(int(model[wire]) << bit
                           for bit, wire in enumerate(row))
                       for row in meta["intermediates"]]
    return masks, selector, intermediate_us


def diagnostic_replay(masks, selector, intermediate_us, q, fibers, basis):
    if not all(0 < mask <= a.LAST_MASK for mask in masks):
        return {"valid": False, "reason": "mask_outside_prefix"}
    try:
        points = [a.points_with_x(a.rational_x(mask, basis))
                  for mask in masks]
    except (ValueError, ZeroDivisionError):
        return {"valid": False, "reason": "nonrational_mask"}
    if not all(len(options) == 2 for options in points):
        return {"valid": False, "reason": "missing_point_lift"}
    us = [a.halftrace(a.source_w(mask, basis)) for mask in masks]
    final_u = a.inv(fibers[selector][0] ^ 1)
    chain = [us[0]] + intermediate_us + [final_u]
    for slot in range(1, 6):
        if chain[slot] == 0 or a.s3_cleared(
                chain[slot-1], us[slot], chain[slot]) != 0:
            return {"valid": False, "reason": "s3_chain_mismatch",
                    "link": slot}
    for chosen in itertools.product(*points):
        if a.group_sum(chosen) == fibers[selector]:
            assert a.scalar_mul(4, a.group_sum(chosen)) == q
            return {"valid": True, "points": [list(p) for p in chosen],
                    "sum": list(fibers[selector])}
    return {"valid": False, "reason": "no_raw_group_lift"}


def save(path, value):
    with path.open("x", encoding="utf-8") as output:
        json.dump(value, output, sort_keys=True, indent=2)
        output.write("\n")


def process_rss_bytes(pid):
    reading = subprocess.run(["/bin/ps", "-o", "rss=", "-p", str(pid)],
                             capture_output=True, text=True, timeout=5)
    if reading.returncode != 0:
        raise RuntimeError("solver RSS monitor cannot query its child: " +
                           reading.stderr.strip())
    words = reading.stdout.split()
    return int(words[0])*1024 if words else None


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
    trace_positions = field_trace_positions()
    if args.mode == "planted":
        q, fibers, pins, raw_points, pinned_fiber = control_input(base, basis)
    else:
        q, fibers = ordinary_input(workload)
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
            "schema": "ecc2k130-w24-natural-pdp-run-v1",
            "mode": args.mode,
            "status": ("build_timeout" if isinstance(exc, TimeoutError) else
                       "build_memory_limit" if isinstance(exc, MemoryError) else
                       "build_error"),
            "error_type": type(exc).__name__, "error": str(exc),
            "query_seconds": query_seconds,
            "build_seconds": time.perf_counter()-build_start,
            "config_sha256": digest(HERE / "CONFIG.json"),
            "source_sha256": {name: digest(HERE / name) for name in FILES},
            "sage_runtime_info_sha256": digest(out / "runtime-info.json"),
            "candidate_id": None, "verified_logarithm": None,
            "online_wall_time": None, "rho_ratio": None,
        }
        save(out / "receipt.json", failure)
        print(json.dumps(failure, sort_keys=True), flush=True)
        return
    finally:
        signal.alarm(0)
    build_seconds = time.perf_counter() - build_start
    xcnf = out / "system.xcnf"
    report = {
        "schema": "ecc2k130-w24-natural-pdp-run-v1",
        "candidate_id": None,
        "proposal_id": config["proposal_id"],
        "mode": args.mode,
        "profile_only": args.profile_only,
        "workload_id": config["parent_workload_id"] if args.mode == "ordinary" else None,
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
        "xcnf_sha256": digest(xcnf),
        "config_sha256": digest(HERE / "CONFIG.json"),
        "parent_primary_workload_sha256": config["parent_primary_workload_sha256"],
        "sage_runtime_info_sha256": digest(out / "runtime-info.json"),
        "source_sha256": {name: digest(HERE / name) for name in FILES},
        "solver_binary_sha256": digest(CMS),
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
                else config["solver_wall_limit_seconds"])
        conflicts = (config["planted_conflict_limit"] if args.mode == "planted"
                     else config["solver_conflict_limit"])
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
                    if time.perf_counter() - solve_start > wall+15:
                        stop_reason = "timeout"
                        process.kill()
                        break
                    try:
                        rss = process_rss_bytes(process.pid)
                    except (RuntimeError, subprocess.TimeoutExpired):
                        stop_reason = "memory_monitor_failure"
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
        report["solver_stdout_sha256"] = digest(out / "solver.stdout.txt")
        report["solver_stderr_sha256"] = digest(out / "solver.stderr.txt")
        status, assignment = read_solver_output(out / "solver.stdout.txt")
        report["solver_status"] = status
        if stop_reason is not None:
            report["status"] = stop_reason
        elif status == "SATISFIABLE":
            masks, selector, intermediates = decode_model(assignment, meta)
            report["model"] = {"masks": masks,
                               "fiber_index": selector,
                               "intermediate_us": intermediates,
                               "assigned_variables": len(assignment)}
            diagnostic = diagnostic_replay(masks, selector, intermediates,
                                           q, fibers, basis)
            report["diagnostic_group_replay"] = diagnostic
            report["status"] = ("candidate_group_relation" if diagnostic["valid"]
                                else "sat_invalid")
        elif status == "UNSATISFIABLE":
            report["status"] = "unsat"
        else:
            report["status"] = "unresolved"
    report["self_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report["child_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    save(out / "receipt.json", report)
    print(json.dumps({key: report[key] for key in
                      ("mode", "status", "variables", "and_gates", "xor_rows",
                       "cnf_clauses", "xcnf_bytes", "build_seconds",
                       "solver_seconds", "solver_status")}, sort_keys=True),
          flush=True)


if __name__ == "__main__":
    main()
