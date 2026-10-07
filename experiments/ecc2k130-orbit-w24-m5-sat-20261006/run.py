#!/usr/bin/env python3
"""Frozen orbit-closed W24/m5 native-XOR SAT unknown-witness gate."""

from __future__ import annotations

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
EXPERIMENTS = HERE.parent
SEED = EXPERIMENTS / "ecc2k130-orbit-closed-w24-seed-20261006"
NORMAL = EXPERIMENTS / "ecc2k130-w24-normal-barrel-20261006"
WORKLOAD = EXPERIMENTS / "ecc2k130-263-equal-w24-workload-20261005"
CONFIG = HERE / "CONFIG.json"
SOURCE_FILES = ("arithmetic.py", "xor_circuit.py", "run.py")
LAYERS = (1, 2, 4, 8, 16, 32, 64, 128)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        h = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def rss_bytes(who: int = resource.RUSAGE_SELF) -> int:
    value = resource.getrusage(who).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def load_inputs():
    config = json.loads(CONFIG.read_text())
    assert config["candidate_id"] is None
    assert config["field_degree"] == a.N == 131
    assert int(config["subgroup_order"]) == a.R
    assert config["summands"] == 5
    assert config["frobenius_exponent_max"] == 130
    assert digest(HERE / "arithmetic.py") == config["parent_sat_arithmetic_sha256"]
    assert digest(HERE / "xor_circuit.py") == config["parent_sat_xor_circuit_sha256"]
    seed_path = SEED / "runs/R1/result.json"
    normal_path = NORMAL / "runs/R2/result.json"
    workload_path = WORKLOAD / "primary_workload.json"
    assert digest(seed_path) == config["parent_seed_result_sha256"]
    assert digest(normal_path) == config["parent_normal_result_sha256"]
    assert digest(workload_path) == config["ordinary_primary_workload_sha256"]
    cms = Path(config["solver_binary"])
    assert digest(cms) == config["solver_binary_sha256"]
    seed = json.loads(seed_path.read_text())
    normal = json.loads(normal_path.read_text())
    workload = json.loads(workload_path.read_text())
    assert normal["candidate_id"] is None and seed["candidate_id"] is None
    assert normal["normal_element_search_counter"] == 0
    assert len(normal["polynomial_to_normal_columns"]) == a.N
    assert len(normal["normal_to_polynomial_columns"]) == a.N
    assert seed["counts"]["group_controls"] == 8
    assert workload["workload_id"] == config["ordinary_workload_id"]
    assert workload["target_count"] == 1
    return config, seed, normal, workload


def frobenius(word: int, exponent: int) -> int:
    assert 0 <= exponent < a.N
    for _ in range(exponent):
        word = a.square(word)
    return word


def raw_point(mask: int, exponent: int, basis: tuple[int, ...]):
    if not 0 < mask < (1 << 24) or not 0 <= exponent <= 130:
        raise ValueError("mask or exponent outside full orbit policy")
    word = frobenius(a.coordinate(basis, mask), exponent)
    if word == 0 or a.trace(a.inv(word)) != 0:
        raise ValueError("seed is not a rational usable W24 point")
    u = a.halftrace(word)
    if u in (0, 1):
        raise ValueError("exceptional W24 quotient coordinate")
    x = 1 ^ a.inv(u)
    lifts = a.points_with_x(x)
    if len(lifts) != 2:
        raise ValueError("W24 quotient has no two curve lifts")
    return min(lifts, key=lambda point: point[1]), word, u


def planted_input(seed, config, basis):
    controls, points, words, us = [], [], [], []
    for index in config["planted_group_control_indices"]:
        row = seed["group"][index]
        assert row["control_index"] == index
        point, word, u = raw_point(row["mask"], row["exponent"], basis)
        assert str(word) == row["orbit_x"]
        projected = a.scalar_mul(4, point)
        archived = tuple(int(value) for value in row["frobenius_q"])
        assert projected in (archived, a.negate(archived))
        controls.append({"index": index, "mask": row["mask"],
                         "exponent": row["exponent"], "word": str(word),
                         "raw_point": list(point)})
        points.append(point)
        words.append(word)
        us.append(u)
    prefix = points[0]
    for slot, point in enumerate(points[1:], 1):
        next_prefix = a.add(prefix, point)
        if prefix is None or next_prefix is None or prefix[0] == 1 or next_prefix[0] == 1:
            raise ValueError(f"exceptional planted S3 chain at link {slot}")
        current_u = a.inv(prefix[0] ^ 1)
        next_u = a.inv(next_prefix[0] ^ 1)
        if a.s3_cleared(current_u, us[slot], next_u) != 0:
            raise ArithmeticError(f"planted S3 residual at link {slot}")
        prefix = next_prefix
    q = a.scalar_mul(4, prefix)
    if q is None or a.scalar_mul(a.R, q) is not None:
        raise ArithmeticError("planted target is not a nonidentity subgroup point")
    fibers = a.target_fibers(q)
    if prefix not in fibers:
        raise ArithmeticError("planted raw sum is absent from the four [4] fibers")
    return q, fibers, controls, fibers.index(prefix)


def normal_seed_columns(basis, normal):
    polynomial_to_normal = [int(word) for word in normal["polynomial_to_normal_columns"]]
    normal_to_polynomial = [int(word) for word in normal["normal_to_polynomial_columns"]]

    def convert(word):
        result = 0
        for bit in range(a.N):
            if (word >> bit) & 1:
                result ^= polynomial_to_normal[bit]
        return result

    half_basis = tuple(a.halftrace(word) for word in basis)
    columns = tuple(convert(word) for word in half_basis)
    for word, code in zip(half_basis, columns):
        reconstructed = 0
        for bit, column in enumerate(normal_to_polynomial):
            if (code >> bit) & 1:
                reconstructed ^= column
        assert reconstructed == word
    return columns, normal_to_polynomial


def barrel_wires(circuit: Circuit, normal_wires: list[int], exponent_wires: list[int]):
    wires = normal_wires
    for selector, shift in zip(exponent_wires, LAYERS):
        next_wires = []
        for position in range(a.N):
            left = wires[position]
            right = wires[(position - shift) % a.N]
            difference = circuit.xor((left, right))
            next_wires.append(circuit.xor((left, circuit.and_(selector, difference))))
        wires = next_wires
    return wires


def build_formula(circuit, seed_columns, normal_to_polynomial, fibers):
    target_us = []
    for point in fibers:
        if point is None or point[0] == 1:
            raise ValueError("exceptional target [4] fiber")
        target_us.append(a.inv(point[0] ^ 1))
    s0, s1 = circuit.variable(), circuit.variable()
    s01 = circuit.and_(s0, s1)
    u0, u1, u2, u3 = target_us
    target_u = circuit.linear_element(
        (s0, s1, s01), (u0 ^ u1, u0 ^ u2, u0 ^ u1 ^ u2 ^ u3), u0)
    target_w = circuit.add(circuit.square(target_u), target_u)
    trace_positions = [bit for bit in range(a.N) if a.trace(1 << bit)]

    masks, exponents, intermediates = [], [], []
    leaf_us, leaf_ws = [], []
    for _ in range(5):
        mask_row = [circuit.variable() for _ in range(24)]
        exponent_row = [circuit.variable() for _ in range(8)]
        circuit.forbid_above(exponent_row, 130)
        seed_u_normal = circuit.linear_element(mask_row, seed_columns)
        orbit_u_normal = barrel_wires(circuit, seed_u_normal, exponent_row)
        orbit_u = circuit.linear_element(orbit_u_normal, normal_to_polynomial)
        orbit_w = circuit.add(circuit.square(orbit_u), orbit_u)
        inverse = [circuit.variable() for _ in range(a.N)]
        circuit.require_zero(circuit.add(circuit.mul(orbit_w, inverse),
                                         circuit.constant(1)))
        circuit.require_zero([circuit.xor(inverse[bit]
                                          for bit in trace_positions)])
        masks.append(mask_row)
        exponents.append(exponent_row)
        leaf_us.append(orbit_u)
        leaf_ws.append(orbit_w)

    intermediates = [[circuit.variable() for _ in range(a.N)] for _ in range(3)]
    for intermediate in intermediates:
        circuit.require_nonzero(intermediate)
    current_u, current_w = leaf_us[0], leaf_ws[0]
    for slot in range(1, 5):
        next_u = intermediates[slot - 1] if slot < 4 else target_u
        next_w = (circuit.add(circuit.square(next_u), next_u)
                  if slot < 4 else target_w)
        lhs = circuit.mul(circuit.mul(current_w, leaf_ws[slot]), next_w)
        rhs = circuit.square(circuit.add_many((current_u, leaf_us[slot], next_u)))
        circuit.require_zero(circuit.add(lhs, rhs))
        current_u, current_w = next_u, next_w
    return {"masks": masks, "exponents": exponents,
            "selectors": (s0, s1), "intermediates": intermediates,
            "target_us": target_us}


def solver_output(path):
    status, assignment = None, {}
    for line in path.read_text(errors="replace").splitlines():
        if line.startswith("s "):
            status = line[2:].strip()
        elif line.startswith("v "):
            for word in line[2:].split():
                value = int(word)
                if value:
                    assignment[abs(value)] = value > 0
    return status, assignment


def decode_model(model, meta):
    required = [wire for row in meta["masks"] + meta["exponents"] +
                meta["intermediates"] for wire in row]
    required += list(meta["selectors"])
    if any(wire not in model for wire in required):
        raise ValueError("SAT output omitted a primary or intermediate bit")
    return {
        "masks": [sum(int(model[wire]) << bit for bit, wire in enumerate(row))
                  for row in meta["masks"]],
        "exponents": [sum(int(model[wire]) << bit for bit, wire in enumerate(row))
                      for row in meta["exponents"]],
        "fiber_index": sum(int(model[wire]) << bit
                           for bit, wire in enumerate(meta["selectors"])),
        "intermediate_us": [sum(int(model[wire]) << bit
                                for bit, wire in enumerate(row))
                            for row in meta["intermediates"]],
        "assigned_variables": len(model),
    }


def diagnostic_replay(model, q, fibers, basis):
    try:
        points, us, words = [], [], []
        for mask, exponent in zip(model["masks"], model["exponents"]):
            point, word, u = raw_point(mask, exponent, basis)
            lifts = a.points_with_x(point[0])
            if len(lifts) != 2:
                raise ValueError("missing signed curve lift")
            points.append(lifts)
            words.append(str(word))
            us.append(u)
        selector = model["fiber_index"]
        if not 0 <= selector < len(fibers):
            raise ValueError("target fiber selector outside range")
        selected = fibers[selector]
        if selected is None or selected[0] == 1:
            raise ValueError("exceptional selected target fiber")
        chain = [us[0]] + model["intermediate_us"] + [a.inv(selected[0] ^ 1)]
        for slot in range(1, 5):
            if chain[slot] == 0 or a.s3_cleared(chain[slot-1], us[slot], chain[slot]) != 0:
                raise ValueError(f"S3 residual at link {slot}")
        for chosen in itertools.product(*points):
            raw_sum = a.group_sum(chosen)
            if raw_sum == selected and a.scalar_mul(4, raw_sum) == q:
                return {"valid": True, "raw_points": [list(p) for p in chosen],
                        "raw_sum": list(raw_sum), "orbit_words": words}
        raise ValueError("no signed raw-point sum matches selected [4] fiber")
    except (ValueError, ZeroDivisionError, AssertionError) as exc:
        return {"valid": False, "reason": str(exc)}


def process_rss_bytes(pid):
    reading = subprocess.run(["/bin/ps", "-o", "rss=", "-p", str(pid)],
                             capture_output=True, text=True, timeout=5)
    if reading.returncode != 0:
        raise RuntimeError("solver RSS monitor failed: " + reading.stderr.strip())
    words = reading.stdout.split()
    return int(words[0]) * 1024 if words else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("planted", "ordinary"), required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--profile-only", action="store_true")
    parser.add_argument("--planted-verification", type=Path)
    args = parser.parse_args()
    if not __debug__:
        parser.error("assertions must be enabled")
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out / "receipt.json").exists() or (out / "system.xcnf").exists():
        parser.error("run directory already contains an attempt")
    if not (out / "runtime-info.json").is_file():
        parser.error("save checked ./sage --runtime-info before this attempt")
    config, seed, normal, workload = load_inputs()
    if args.mode == "ordinary":
        if args.planted_verification is None:
            parser.error("ordinary gate requires independent planted verification")
        planted = json.loads(args.planted_verification.read_text())
        if planted.get("status") != "PASS_UNKNOWN_WITNESS_GROUP_REPLAY":
            parser.error("independent planted replay did not pass")
    started = time.perf_counter()
    source = {name: digest(HERE / name) for name in SOURCE_FILES}
    try:
        basis = a.source_basis()
        columns, output_columns = normal_seed_columns(basis, normal)
        if args.mode == "planted":
            q, fibers, controls, planted_fiber = planted_input(seed, config, basis)
        else:
            q = tuple(workload["targets"][0]["source"])
            assert a.on_curve(q) and a.scalar_mul(a.R, q) is None
            fibers = a.target_fibers(q)
            controls, planted_fiber = None, None
    except Exception as exc:
        receipt = {"schema": "ecc2k130-orbit-w24-m5-sat-run-v1",
                   "status": "input_preflight_failure", "mode": args.mode,
                   "error_type": type(exc).__name__, "error": str(exc),
                   "query_seconds": time.perf_counter() - started,
                   "config_sha256": digest(CONFIG), "source_sha256": source,
                   "candidate_id": None, "target_online_ms": None}
        save(out / "receipt.json", receipt)
        print(json.dumps(receipt, sort_keys=True), flush=True)
        return
    query_seconds = time.perf_counter() - started
    circuit = Circuit(a.N, a.LOW_TERMS,
                      memory_limit_bytes=config["peak_rss_limit_bytes"])
    build_started = time.perf_counter()
    def build_alarm(_signum, _frame):
        raise TimeoutError("frozen formula-build wall limit")

    signal.signal(signal.SIGALRM, build_alarm)
    signal.alarm(config["build_wall_limit_seconds"])
    try:
        meta = build_formula(circuit, columns, output_columns, fibers)
        circuit.write(out / "system.xcnf")
    except Exception as exc:
        receipt = {"schema": "ecc2k130-orbit-w24-m5-sat-run-v1",
                   "status": ("build_timeout" if isinstance(exc, TimeoutError) else
                              "build_memory_limit" if isinstance(exc, MemoryError) else
                              "build_error"),
                   "error_type": type(exc).__name__, "error": str(exc),
                   "mode": args.mode, "config_sha256": digest(CONFIG),
                   "source_sha256": source, "candidate_id": None,
                   "target_online_ms": None,
                   "query_seconds": query_seconds,
                   "build_seconds": time.perf_counter() - build_started}
        save(out / "receipt.json", receipt)
        print(json.dumps(receipt, sort_keys=True), flush=True)
        return
    finally:
        signal.alarm(0)
    build_seconds = time.perf_counter() - build_started
    xcnf = out / "system.xcnf"
    report = {
        "schema": "ecc2k130-orbit-w24-m5-sat-run-v1",
        "candidate_id": None,
        "mode": args.mode,
        "profile_only": args.profile_only,
        "config_sha256": digest(CONFIG),
        "source_sha256": source,
        "parent_seed_result_sha256": config["parent_seed_result_sha256"],
        "parent_normal_result_sha256": config["parent_normal_result_sha256"],
        "ordinary_workload_id": config["ordinary_workload_id"] if args.mode == "ordinary" else None,
        "public_q": list(q),
        "raw_fibers": [list(point) for point in fibers],
        "planted_controls": controls,
        "planted_fiber_index": planted_fiber,
        "seed_to_normal_u_columns": [str(value) for value in columns],
        "factor_base_B": config["orbit_closed_geometric_points_B"],
        "folded_columns": config["orbit_closed_sign_frobenius_columns"],
        "query_seconds": query_seconds,
        "build_seconds": build_seconds,
        "variables": circuit.next_var - 1,
        "and_gates": circuit.and_count,
        "cnf_clauses": len(circuit.clauses),
        "xor_rows": len(circuit.xors),
        "xcnf_bytes": xcnf.stat().st_size,
        "xcnf_sha256": digest(xcnf),
        "sage_runtime_info_sha256": digest(out / "runtime-info.json"),
        "solver_binary_sha256": digest(Path(config["solver_binary"])),
        "solver_command": None, "solver_seconds": None,
        "solver_exit_code": None, "solver_status": None,
        "solver_peak_rss_bytes": None, "model": None,
        "diagnostic_group_replay": None,
        "status": "profile_only" if args.profile_only else "unresolved",
        "host": {"system": platform.system(), "machine": platform.machine(),
                 "python": sys.version.split()[0], "cpu_isolation": "unverified"},
        "natural_pdp_yield": None,
        "verified_novel_rank": None,
        "target_online_ms": None,
        "rho_ratio": None,
    }
    if not args.profile_only:
        wall = (config["planted_wall_limit_seconds"] if args.mode == "planted"
                else config["ordinary_wall_limit_seconds"])
        conflicts = (config["planted_conflict_limit"] if args.mode == "planted"
                     else config["ordinary_conflict_limit"])
        command = [config["solver_binary"], f"--maxtime={wall}",
                   f"--maxconfl={conflicts}", f"--threads={config['solver_threads']}",
                   f"--random={config['solver_seed']}", "--maxsol=1", "--printsol=1",
                   str(xcnf)]
        report["solver_command"] = command
        solve_started = time.perf_counter()
        stop_reason, observed_peak, monitor_error = None, 0, None
        with (out / "solver.stdout.txt").open("x") as stdout, \
             (out / "solver.stderr.txt").open("x") as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
            try:
                while process.poll() is None:
                    if time.perf_counter() - solve_started >= wall:
                        stop_reason = "timeout"
                        process.kill()
                        break
                    try:
                        rss = process_rss_bytes(process.pid)
                    except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
                        stop_reason = "memory_monitor_failure"
                        monitor_error = f"{type(exc).__name__}: {exc}"
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
        report["solver_seconds"] = time.perf_counter() - solve_started
        report["solver_peak_rss_bytes"] = observed_peak
        report["monitor_error"] = monitor_error
        report["solver_stdout_sha256"] = digest(out / "solver.stdout.txt")
        report["solver_stderr_sha256"] = digest(out / "solver.stderr.txt")
        status, assignment = solver_output(out / "solver.stdout.txt")
        report["solver_status"] = status
        if stop_reason is not None:
            report["status"] = stop_reason
        elif status == "SATISFIABLE":
            try:
                model = decode_model(assignment, meta)
                replay = diagnostic_replay(model, q, fibers, basis)
                report["model"] = model
                report["diagnostic_group_replay"] = replay
                report["status"] = "candidate_group_relation" if replay["valid"] else "sat_invalid"
            except (ValueError, AssertionError) as exc:
                report["status"] = "sat_invalid"
                report["model_error"] = str(exc)
        elif status == "UNSATISFIABLE":
            report["status"] = "unsat"
    report["self_peak_rss_bytes"] = rss_bytes()
    report["child_peak_rss_bytes"] = rss_bytes(resource.RUSAGE_CHILDREN)
    save(out / "receipt.json", report)
    print(json.dumps({key: report[key] for key in
                      ("mode", "status", "variables", "and_gates", "xor_rows",
                       "cnf_clauses", "xcnf_bytes", "build_seconds",
                       "solver_seconds", "solver_status")}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
