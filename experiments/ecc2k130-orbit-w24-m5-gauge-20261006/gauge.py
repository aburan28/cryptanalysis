#!/usr/bin/env python3
"""Rebuild the exact W24/m5 XCNF, add one exponent gauge, and run bounded SAT."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import resource
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "ecc2k130-orbit-w24-m5-sat-20261006"
sys.path.insert(0, str(PARENT))
import run as parent  # noqa: E402

CONFIG = HERE / "CONFIG.json"
PARENT_RUN = PARENT / "runs/planted-r2"
PARENT_WITNESS = PARENT / "runs/witness-r2"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def save(path: Path, data: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")


def frozen_inputs() -> tuple[dict, dict, dict, dict, dict]:
    config = read(CONFIG)
    if config["candidate_id"] is not None:
        raise ValueError("stage diagnostic cannot have a candidate ID")
    paths = {
        "parent_ungauged_receipt_sha256": PARENT_RUN / "receipt.json",
        "parent_ungauged_xcnf_gzip_sha256": PARENT_RUN / "system.xcnf.gz",
        "parent_known_assignment_gzip_sha256": PARENT_WITNESS / "assignment.bin.gz",
        "parent_known_assignment_verification_sha256": PARENT_WITNESS / "verification-archived.json",
        "parent_arithmetic_sha256": PARENT / "arithmetic.py",
        "parent_xor_circuit_sha256": PARENT / "xor_circuit.py",
        "parent_run_source_sha256": PARENT / "run.py",
        "solver_binary_sha256": Path(config["solver_binary"]),
    }
    for key, path in paths.items():
        if digest(path) != config[key]:
            raise ValueError(f"frozen hash mismatch: {key}")
    strict = read(PARENT_RUN / "receipt.json")
    verification = read(PARENT_WITNESS / "verification-archived.json")
    if (strict["xcnf_sha256"] != config["parent_ungauged_xcnf_sha256"] or
            strict["solver_status"] != "INDETERMINATE" or
            strict["model"] is not None or
            verification["status"] != "PASS_KNOWN_PLANTED_XCNF_ASSIGNMENT" or
            verification["xcnf_sha256"] != strict["xcnf_sha256"] or
            strict["public_q"] != config["public_q"] or
            strict["planted_controls"][0]["exponent"] != 0):
        raise ValueError("parent outcome, witness or target changed")
    parent_config, seed, normal, workload = parent.load_inputs()
    if (parent_config["orbit_closed_geometric_points_B"] !=
            config["factor_base_geometric_B"] or
            parent_config["orbit_closed_sign_frobenius_columns"] !=
            config["factor_base_folded_columns"] or
            parent_config["ordinary_workload_id"] != config["ordinary_workload_id"]):
        raise ValueError("parent factor base or workload changed")
    return config, strict, seed, normal, workload


def prepare(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    if (out / "build.json").exists() or (out / "system.xcnf").exists():
        raise ValueError("prepare output already exists")
    runtime = out / "runtime-info.json"
    if not runtime.is_file():
        raise ValueError("save checked Sage runtime-info before prepare")
    config, strict, seed, normal, _ = frozen_inputs()
    started = time.perf_counter()

    def alarm(_signum, _frame):
        raise TimeoutError("frozen formula-build wall limit")

    signal.signal(signal.SIGALRM, alarm)
    signal.alarm(config["build_wall_seconds"])
    try:
        basis = parent.a.source_basis()
        columns, output_columns = parent.normal_seed_columns(basis, normal)
        q, fibers, controls, fiber_index = parent.planted_input(seed, config, basis)
        if list(q) != config["public_q"] or controls != strict["planted_controls"]:
            raise ValueError("planted input differs from archived target")
        circuit = parent.Circuit(parent.a.N, parent.a.LOW_TERMS,
                                 memory_limit_bytes=config["peak_rss_limit_bytes"])
        meta = parent.build_formula(circuit, columns, output_columns, fibers)
        old_counts = (circuit.next_var - 1, len(circuit.clauses), len(circuit.xors))
        if old_counts != (strict["variables"], strict["cnf_clauses"], strict["xor_rows"]):
            raise ValueError("ungauged formula shape changed")
        ungauged = out / "ungauged-check.xcnf"
        circuit.write(ungauged)
        old_hash = digest(ungauged)
        ungauged.unlink()
        if old_hash != config["parent_ungauged_xcnf_sha256"]:
            raise ValueError("ungauged XCNF bytes changed")
        wires = meta["exponents"][config["fixed_exponent_leaf_index"]]
        if (len(wires) != config["fixed_exponent_bit_count"] or
                len(set(wires)) != len(wires) or not all(w > 0 for w in wires)):
            raise ValueError("gauge wire map invalid")
        for wire in wires:
            circuit.pin(wire, False)
        gauged_counts = (circuit.next_var - 1, len(circuit.clauses), len(circuit.xors))
        if gauged_counts != (old_counts[0], old_counts[1] + 8, old_counts[2]):
            raise ValueError("gauge changed more than eight unit clauses")
        xcnf = out / "system.xcnf"
        circuit.write(xcnf)
    finally:
        signal.alarm(0)

    build = {
        "schema": "ecc2k130-orbit-w24-m5-gauge-build-v1",
        "status": "PASS_EXACT_PARENT_PLUS_EIGHT_UNIT_CLAUSES",
        "candidate_id": None,
        "config_sha256": digest(CONFIG),
        "source_sha256": digest(Path(__file__)),
        "runtime_info_sha256": digest(runtime),
        "parent_receipt_sha256": digest(PARENT_RUN / "receipt.json"),
        "parent_xcnf_sha256": old_hash,
        "xcnf_sha256": digest(xcnf),
        "xcnf_bytes": xcnf.stat().st_size,
        "variables": gauged_counts[0],
        "cnf_clauses": gauged_counts[1],
        "xor_rows": gauged_counts[2],
        "and_gates": circuit.and_count,
        "first_exponent_wires": wires,
        "meta": meta,
        "public_q": list(q),
        "planted_fiber_index": fiber_index,
        "build_seconds_exploratory": time.perf_counter() - started,
        "builder_peak_rss_bytes": parent.rss_bytes(),
    }
    save(out / "build.json", build)
    print(json.dumps({key: build[key] for key in
                      ("status", "xcnf_sha256", "variables", "cnf_clauses",
                       "xor_rows", "first_exponent_wires")}, sort_keys=True))


def solve(primary: Path, out: Path, tier: str) -> None:
    config, strict, seed, normal, _ = frozen_inputs()
    build_path = primary / "build.json"
    build = read(build_path)
    if (build["status"] != "PASS_EXACT_PARENT_PLUS_EIGHT_UNIT_CLAUSES" or
            build["config_sha256"] != digest(CONFIG) or
            build["source_sha256"] != digest(Path(__file__)) or
            build["parent_receipt_sha256"] != digest(PARENT_RUN / "receipt.json")):
        raise ValueError("gauged build provenance changed")
    xcnf = primary / "system.xcnf"
    if digest(xcnf) != build["xcnf_sha256"]:
        raise ValueError("gauged XCNF changed")
    out.mkdir(parents=True, exist_ok=True)
    if (out / "receipt.json").exists() or (out / "solver.stdout.txt").exists():
        raise ValueError("solve output already exists")
    runtime = out / "runtime-info.json"
    if not runtime.is_file():
        raise ValueError("save checked Sage runtime-info before solve")
    if tier == "secondary":
        first = read(primary / "receipt.json")
        if (first["tier"] != "primary" or first["status"] != "unresolved" or
                first["solver_status"] != "INDETERMINATE" or
                first["model"] is not None):
            raise ValueError("secondary tier requires primary indeterminate")
        limit = config["secondary_conflicts"]
        wall = config["secondary_wall_seconds"]
    else:
        if out != primary:
            raise ValueError("primary solver output must be build directory")
        limit = config["primary_conflicts"]
        wall = config["primary_wall_seconds"]
    command = [config["solver_binary"], f"--maxtime={wall}",
               f"--maxconfl={limit}", f"--threads={config['solver_threads']}",
               f"--random={config['solver_seed']}", "--maxsol=1", "--printsol=1",
               str(xcnf)]
    started = time.perf_counter()
    stop_reason, observed_peak, monitor_error = None, 0, None
    with (out / "solver.stdout.txt").open("x") as stdout, \
         (out / "solver.stderr.txt").open("x") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        try:
            while process.poll() is None:
                if time.perf_counter() - started >= wall:
                    stop_reason = "timeout"
                    process.kill()
                    break
                try:
                    rss = parent.process_rss_bytes(process.pid)
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
            exit_code = process.wait()
    solver_seconds = time.perf_counter() - started
    stdout_path = out / "solver.stdout.txt"
    solver_status, assignment = parent.solver_output(stdout_path)
    matches = re.findall(r"^c conflicts\s*:\s*(\d+)",
                         stdout_path.read_text(errors="replace"), re.MULTILINE)
    status, model, replay = "unresolved", None, None
    if stop_reason:
        status = stop_reason
    elif solver_status == "SATISFIABLE":
        try:
            model = parent.decode_model(assignment, build["meta"])
            basis = parent.a.source_basis()
            q, fibers, _, _ = parent.planted_input(seed, config, basis)
            replay = parent.diagnostic_replay(model, q, fibers, basis)
            status = "candidate_group_relation" if replay["valid"] else "sat_invalid"
        except (ValueError, AssertionError) as exc:
            status = "sat_invalid"
            replay = {"valid": False, "reason": str(exc)}
    elif solver_status == "UNSATISFIABLE":
        status = "unsat"
    report = {
        "schema": "ecc2k130-orbit-w24-m5-gauge-solve-v1",
        "status": status,
        "tier": tier,
        "candidate_id": None,
        "config_sha256": digest(CONFIG),
        "source_sha256": digest(Path(__file__)),
        "build_receipt_sha256": digest(build_path),
        "runtime_info_sha256": digest(runtime),
        "xcnf_sha256": build["xcnf_sha256"],
        "parent_ungauged_xcnf_sha256": strict["xcnf_sha256"],
        "public_q": build["public_q"],
        "variables": build["variables"],
        "cnf_clauses": build["cnf_clauses"],
        "xor_rows": build["xor_rows"],
        "solver_binary_sha256": digest(Path(config["solver_binary"])),
        "solver_command": command,
        "conflict_limit": limit,
        "wall_limit_seconds": wall,
        "solver_seconds_exploratory": solver_seconds,
        "solver_peak_rss_bytes": observed_peak,
        "monitor_error": monitor_error,
        "solver_exit_code": exit_code,
        "solver_status": solver_status,
        "solver_conflicts_reported": int(matches[-1]) if matches else None,
        "solver_stdout_sha256": digest(stdout_path),
        "solver_stderr_sha256": digest(out / "solver.stderr.txt"),
        "model": model,
        "diagnostic_group_replay": replay,
        "independently_verified_unknown_witness": False,
        "natural_pdp_yield": None,
        "verified_novel_rank": None,
        "target_online_ms": None,
        "rho_ratio": None,
        "host": {"system": platform.system(), "machine": platform.machine(),
                 "python": sys.version.split()[0], "cpu_isolation": "unverified"},
        "self_peak_rss_bytes": parent.rss_bytes(resource.RUSAGE_SELF),
        "child_peak_rss_bytes": parent.rss_bytes(resource.RUSAGE_CHILDREN),
    }
    save(out / "receipt.json", report)
    print(json.dumps({key: report[key] for key in
                      ("tier", "status", "solver_status", "solver_conflicts_reported",
                       "solver_seconds_exploratory", "solver_peak_rss_bytes")},
                     sort_keys=True), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--out-dir", type=Path, required=True)
    solve_parser = sub.add_parser("solve")
    solve_parser.add_argument("--primary-dir", type=Path, required=True)
    solve_parser.add_argument("--out-dir", type=Path, required=True)
    solve_parser.add_argument("--tier", choices=("primary", "secondary"), required=True)
    args = parser.parse_args()
    if not __debug__:
        parser.error("assertions must be enabled")
    try:
        if args.command == "prepare":
            prepare(args.out_dir.resolve())
        else:
            solve(args.primary_dir.resolve(), args.out_dir.resolve(), args.tier)
    except Exception as exc:
        out = args.out_dir.resolve()
        out.mkdir(parents=True, exist_ok=True)
        failure = out / "failure.json"
        if not failure.exists():
            save(failure, {
                "schema": "ecc2k130-orbit-w24-m5-gauge-failure-v1",
                "status": "producer_exception",
                "candidate_id": None,
                "command": args.command,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "config_sha256": digest(CONFIG),
                "source_sha256": digest(Path(__file__)),
            })
        raise


if __name__ == "__main__":
    main()
