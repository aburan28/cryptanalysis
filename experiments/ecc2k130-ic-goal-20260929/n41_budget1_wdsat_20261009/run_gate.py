#!/usr/bin/env python3
"""Freeze and run a bounded WDSat stage on the N41 fill-limited XCNF."""

import argparse
import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
ROOT = GOAL.parents[1]
BASE = GOAL / "fill_controlled_projection_20261009/n41_budget1"
FORMULA = BASE / "projected.xcnf"
CONTROL = BASE / "projected_control_model.stdout.txt"
VERIFIER = GOAL / "n131_phi_torsion_frobenius_domains_20261005/m16_prefix_audit_20261006/verify_xcnf_model.py"
SOLVER = HERE / "wdsat/wdsat_solver"
PINNED = HERE / "fully_fixed_control.xcnf"
PROTOCOL = HERE / "protocol.json"
RUNTIME = HERE / "sage_runtime_info.json"
MEMORY_CAP = 4 * 1024**3


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def verifier():
    spec = importlib.util.spec_from_file_location("independent_xcnf_verifier", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare():
    if PROTOCOL.exists() or PINNED.exists():
        raise FileExistsError("frozen inputs already exist")
    if verifier().verify(FORMULA, CONTROL)["status"] != "PASS":
        raise ValueError("projected control model failed independent verifier")
    values = verifier().model_from_stdout(CONTROL, 40313)
    with FORMULA.open("rb") as source, PINNED.open("xb") as output:
        if source.readline() != b"p cnf 40313 174617\n":
            raise ValueError("unexpected public formula header")
        output.write(b"p cnf 40313 214930\n")
        for index in range(1, 40314):
            output.write(f"{index if values[index] else -index} 0\n".encode())
        for block in iter(lambda: source.read(1 << 20), b""):
            output.write(block)
    if verifier().verify(PINNED, CONTROL)["status"] != "PASS":
        raise ValueError("pinned control is not satisfied by known model")
    source = HERE / "wdsat/src"
    sources = {path.name: sha(path) for path in sorted(source.iterdir()) if path.is_file()}
    save(PROTOCOL, {
        "status": "FROZEN", "proposal_id": "Q20261009N41WDSAT",
        "candidate_id": None, "run_id": None,
        "curve_id": "EC1N41Ckb1hf5a3eea408f4", "workload_id": "2fa2f1e7c5fc",
        "target_count": 1, "worker_count": 1,
        "formula_sha256": sha(FORMULA), "pinned_sha256": sha(PINNED),
        "control_model_sha256": sha(CONTROL),
        "solver_sha256": sha(SOLVER), "solver_source_sha256": sources,
        "runner_sha256": sha(Path(__file__)), "verifier_sha256": sha(VERIFIER),
        "compiler": subprocess.check_output(["gcc", "--version"], text=True).splitlines()[0],
        "build_command": "make -C wdsat/src clean all",
        "solver_mode": "plain CNF/XOR-set propagation; no Gaussian elimination",
        "capacities": {"variables": 41000, "cnf_clauses": 215000,
                       "xor_rows": 4100, "cnf_and_xor_width": 304,
                       "literal_buffer": 1200000},
        "wall_cap_seconds": {"pinned": 60, "ordinary": 240},
        "memory_cap_bytes": MEMORY_CAP,
        "timing_boundary": "solver process launch through terminal status; formula build and independent model verification excluded",
        "acceptance": "An ordinary model must satisfy the projected and original XCNF and independent checked-Sage group replay before relation credit.",
    })
    print(json.dumps({"status": "FROZEN", "formula_sha256": sha(FORMULA),
                      "pinned_sha256": sha(PINNED)}))


def run(mode):
    protocol = json.loads(PROTOCOL.read_text())
    if protocol["status"] != "FROZEN":
        raise ValueError("protocol is not frozen")
    for path, key in ((FORMULA, "formula_sha256"), (PINNED, "pinned_sha256"),
                      (CONTROL, "control_model_sha256"), (SOLVER, "solver_sha256"),
                      (Path(__file__), "runner_sha256"), (VERIFIER, "verifier_sha256")):
        if sha(path) != protocol[key]:
            raise ValueError("frozen hash mismatch: " + key)
    for name, expected in protocol["solver_source_sha256"].items():
        if sha(HERE / "wdsat/src" / name) != expected:
            raise ValueError("solver source hash mismatch: " + name)
    runtime = json.loads(RUNTIME.read_text())
    if runtime["status"] != "verified":
        raise ValueError("checked Sage runtime receipt failed")
    if mode == "ordinary" and json.loads((HERE / "pinned/receipt.json").read_text())["status"] != "PINNED_MODEL_PASS":
        raise ValueError("pinned control did not pass")
    run_dir = HERE / mode
    run_dir.mkdir(exist_ok=False)
    input_path = PINNED if mode == "pinned" else FORMULA
    command = [str(SOLVER), "-i", str(input_path), "-n", "41", "-m", "7", "-l", "41"]
    wall_cap = protocol["wall_cap_seconds"][mode]
    stdout = run_dir / "solver.stdout.txt"
    stderr = run_dir / "solver.stderr.txt"
    started = time.monotonic()
    started_ns = time.time_ns()
    peak_group = 0
    stop_reason = None
    with stdout.open("wb") as out, stderr.open("wb") as err:
        child = subprocess.Popen(command, cwd=ROOT, stdout=out, stderr=err,
                                 start_new_session=True)
        parent = psutil.Process()
        while child.poll() is None:
            try:
                rss = psutil.Process(child.pid).memory_info().rss
            except psutil.NoSuchProcess:
                rss = 0
            peak_group = max(peak_group, rss + parent.memory_info().rss)
            if peak_group >= MEMORY_CAP:
                stop_reason = "MEMORY_GUARD"
            elif time.monotonic() - started >= wall_cap:
                stop_reason = "WALL_CAP"
            if stop_reason:
                os.killpg(child.pid, signal.SIGINT)
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
                break
            time.sleep(.1)
        child.wait()
    wall = time.monotonic() - started
    models = [line.strip() for line in stdout.read_text(errors="replace").splitlines()
              if len(line.strip()) == 40313 and set(line.strip()) <= {"0", "1"}]
    model_check = None
    if models:
        model_path = run_dir / "solver_model.stdout.txt"
        with model_path.open("w") as stream:
            stream.write("s SATISFIABLE\n")
            for index, bit in enumerate(models[0], 1):
                stream.write(f"v {index if bit == '1' else -index} 0\n")
        model_check = verifier().verify(input_path, model_path)
        if mode == "pinned" and models[0] != "".join(str(int(value)) for value in verifier().model_from_stdout(CONTROL, 40313)[1:]):
            raise ValueError("pinned model differs from known assignment")
    if model_check and mode == "pinned":
        status = "PINNED_MODEL_PASS"
    elif model_check:
        status = "ORDINARY_XCNF_MODEL_REQUIRES_GROUP_REPLAY"
    elif stop_reason == "WALL_CAP":
        status = "CENSORED_TIME"
    elif stop_reason == "MEMORY_GUARD":
        status = "OOM"
    else:
        status = "INDETERMINATE"
    save(run_dir / "receipt.json", {
        "status": status, "mode": mode, "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
        "target_count": 1, "input_sha256": sha(input_path),
        "protocol_sha256": sha(PROTOCOL), "runtime_info_sha256": sha(RUNTIME),
        "command": command, "wall_cap_seconds": wall_cap,
        "solver_wall_seconds": wall, "started_unix_ns": started_ns,
        "memory_cap_bytes": MEMORY_CAP, "sampled_peak_group_rss_bytes": peak_group,
        "stop_reason": stop_reason, "exit_code": child.returncode,
        "model_count": len(models), "xcnf_model_check": model_check,
        "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr),
        "solver_sha256": sha(SOLVER),
    })
    print(json.dumps({"status": status, "solver_wall_seconds": wall,
                      "sampled_peak_group_rss_bytes": peak_group,
                      "model_count": len(models)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "pinned", "ordinary"])
    mode = parser.parse_args().mode
    prepare() if mode == "prepare" else run(mode)
