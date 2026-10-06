#!/usr/bin/env python3
"""Bounded wide-Gaussian solver on frozen pinned and public N83 fibers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import psutil
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
SLOPE = HERE.parent / "n83-slope-witness-pdp-20261006"
INDEXED = HERE.parent / "n83-indexed-factor-pdp-20261006"
SOURCE = HERE.parent / "hamming-ic-e2e-20260929"
sys.path.insert(0, str(SLOPE))
sys.path.insert(0, str(INDEXED))
from indexed_factor import factor, pin_positions  # noqa: E402
from run_slope_branch import (PRIVATE, PUBLIC, REPS, SlopeWitnessCircuit,
                              parse_model, replay, verify_model)  # noqa: E402

PROTOCOL = HERE / "protocol_queries.json"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sampled_tree(child: psutil.Process) -> tuple[int, float]:
    members = [psutil.Process(os.getpid())]
    try:
        members += [child, *child.children(recursive=True)]
    except psutil.NoSuchProcess:
        pass
    rss, cpu = 0, 0.0
    for process in members:
        try:
            if process.is_running():
                rss += process.memory_info().rss
                clocks = process.cpu_times()
                cpu += clocks.user + clocks.system
        except psutil.NoSuchProcess:
            pass
    return rss, cpu


def check_sat_model(model: dict[int, bool], out: Path, public: dict,
                    case_record: dict, private: dict | None) -> dict:
    builder = SlopeWitnessCircuit(83, [0, 2, 4, 7])
    circuit = builder.circuit
    conjugates = [int(v) for v in public["normal_conjugates_polynomial_bits_decimal"]]
    encoded = [factor(circuit, conjugates) for _ in range(5)]
    mode = case_record["mode"]
    kind = "ordinary" if mode == "ordinary" else "planted"
    fiber = public[kind]["raw_target_fiber"][case_record["fiber_index"]]
    witness = builder.require_sum([item["x"] for item in encoded],
                                  int(fiber["x"]), int(fiber["y"]))
    if mode == "pinned_planted":
        assert private is not None
        for item, selected in zip(encoded, private["selected"]):
            pin_positions(circuit, item, selected["mask"])
    rebuilt = out / "rebuilt.xcnf"
    circuit.write(rebuilt)
    if sha(rebuilt) != case_record["input_xcnf_sha256"]:
        return {"verified": False, "reason": "source_circuit_mismatch"}
    if not verify_model(circuit, model):
        return {"verified": False, "reason": "cnf_xor_model_invalid"}
    return replay(model, encoded, witness, conjugates, public, kind, fiber)


def main(case: str, out: Path) -> int:
    out = out.resolve()
    if out.exists():
        raise FileExistsError("solver-policy output is immutable")
    out.mkdir(parents=True)
    protocol = json.loads(PROTOCOL.read_text())
    assert case in protocol["cases"]
    case_record = protocol["cases"][case]
    xcnf = SLOPE / "runs" / case_record["parent_run"] / "branch.xcnf"
    parent_receipt = xcnf.parent / "receipt.json"
    assert sha(xcnf) == case_record["input_xcnf_sha256"]
    assert sha(parent_receipt) == case_record["parent_receipt_sha256"]
    assert sha(SOLVER) == protocol["solver_binary_sha256"]
    assert sha(SLOPE / "slope_witness_circuit.py") == \
        protocol["source_slope_circuit_sha256"]
    assert sha(INDEXED / "indexed_factor.py") == \
        protocol["source_indexed_factor_sha256"]
    assert sha(PUBLIC) == protocol["public_fixture_sha256"]
    assert sha(REPS) == protocol["representatives_sha256"]
    private = None
    if case_record["mode"] == "pinned_planted":
        assert sha(PRIVATE) == protocol["private_fixture_sha256_local_only"]
        private = json.loads(PRIVATE.read_text())
    with (out / "sage_runtime_info.json").open("wb") as runtime, \
         (out / "sage_runtime_info.stderr.txt").open("wb") as runtime_error:
        preflight = subprocess.run([str(SAGE), "--runtime-info"],
                                  stdout=runtime, stderr=runtime_error,
                                  check=False)
    if preflight.returncode:
        save(out / "preflight_failure.json", {
            "status": "SAGE_RUNTIME_PREFLIGHT_FAILURE",
            "exit_code": preflight.returncode,
        })
        return 1
    public = json.loads(PUBLIC.read_text())
    assert public["curve_id"] == protocol["curve_id"]
    mode = case_record["mode"]
    kind = "ordinary" if mode == "ordinary" else "planted"
    fiber_index = case_record["fiber_index"]
    fiber = public[kind]["raw_target_fiber"][fiber_index]
    if private is not None:
        assert [fiber[key] for key in ("x", "y")] == private["raw_sum"]
    argv = [str(SOLVER), "--threads=1", "--maxtime=120",
            "--maxconfl=1000000", "--printsol=1",
            *protocol["solver_options"], str(xcnf)]
    save(out / "started.json", {
        "kind": "n83_wide_gauss_query_start",
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "case": case, "mode": mode, "fiber_index": fiber_index,
        "target_kind": kind, "target_Q": public[kind]["target_Q"],
        "argv": argv,
        "input_xcnf_sha256": sha(xcnf),
        "parent_receipt_sha256": sha(parent_receipt),
        "private_fixture_sha256_local_only": sha(PRIVATE) if private is not None else None,
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": sha(Path(__file__)),
        "sage_runtime_info_sha256": sha(out / "sage_runtime_info.json"),
        "architecture": platform.machine(), "os": platform.platform(),
    })
    started = time.perf_counter_ns()
    peak_rss, sampled_cpu = 0, 0.0
    guard = None
    guard_error = None
    with (out / "solver.stdout.txt").open("wb") as stdout, \
         (out / "solver.stderr.txt").open("wb") as stderr:
        child = subprocess.Popen(argv, stdout=stdout, stderr=stderr,
                                 start_new_session=True)
        root = psutil.Process(child.pid)
        while child.poll() is None:
            try:
                rss, cpu = sampled_tree(root)
            except (psutil.AccessDenied, PermissionError) as error:
                guard = "process_inspection_error"
                guard_error = f"{type(error).__name__}: {error}"
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            peak_rss = max(peak_rss, rss)
            sampled_cpu = max(sampled_cpu, cpu)
            if peak_rss >= protocol["max_process_tree_rss_bytes"]:
                guard = "process_tree_rss_guard"
            elif (time.perf_counter_ns() - started) / 1e9 >= \
                    protocol["external_wall_seconds"]:
                guard = "external_wall_guard"
            if guard:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            time.sleep(0.05)
        exit_code = child.wait()
    solver_wall_ns = time.perf_counter_ns() - started
    stdout_text = (out / "solver.stdout.txt").read_text(errors="replace")
    model = parse_model(stdout_text) if guard is None else None
    result = {
        "schema_version": 1,
        "kind": "n83_wide_gauss_query",
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "case": case, "mode": mode, "fiber_index": fiber_index,
        "target_kind": kind, "target_Q": public[kind]["target_Q"],
        "status": "RESOURCE_GUARD" if guard else "INCOMPLETE",
        "solver_exit_code": exit_code,
        "solver_wall_ns": solver_wall_ns,
        "sampled_process_tree_cpu_seconds": sampled_cpu,
        "sampled_process_tree_peak_rss_bytes": peak_rss,
        "guard": guard,
        "guard_error": guard_error,
        "solver_stdout_sha256": sha(out / "solver.stdout.txt"),
        "solver_stderr_sha256": sha(out / "solver.stderr.txt"),
        "started_sha256": sha(out / "started.json"),
        "protocol_sha256": sha(PROTOCOL),
        "claim_boundary": protocol["claim_boundary"],
        "online_target_wall_ns": None,
        "rho_online_wall_ns": None,
        "online_speedup": None,
    }
    if guard is None:
        if model is None:
            result["status"] = ("UNSAT" if "s UNSATISFIABLE" in stdout_text
                                else "BOUNDED_UNKNOWN")
        else:
            checked = check_sat_model(model, out, public, case_record, private)
            if checked["verified"]:
                save(out / "private_model.json", checked)
                result["private_model_sha256_local_only"] = sha(out / "private_model.json")
                result["status"] = "SAT_GROUP_VERIFIED_PENDING_SAGE"
            else:
                result["status"] = "SAT_UNVERIFIED_GROUP"
                result["group_check_error"] = checked["reason"]
    result["verification_wall_ns"] = time.perf_counter_ns() - started - solver_wall_ns
    result["total_wall_ns"] = solver_wall_ns + result["verification_wall_ns"]
    save(out / "receipt.json", result)
    print(json.dumps({"status": result["status"],
                      "solver_wall_seconds": solver_wall_ns / 1e9,
                      "peak_mib": peak_rss / 2**20}, sort_keys=True), flush=True)
    return 0 if guard is None else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=("pinned_planted_f0",
                                         "unpinned_planted_f0",
                                         "ordinary_f0", "ordinary_f1",
                                         "ordinary_f2", "ordinary_f3"))
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    raise SystemExit(main(args.case, args.out))
