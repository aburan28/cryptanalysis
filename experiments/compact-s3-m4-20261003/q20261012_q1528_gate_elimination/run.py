#!/usr/bin/env python3
"""Bounded gate-eliminated ANF panel on the exact Q1525 handoff inputs."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import resource
import signal
import subprocess
import time
from pathlib import Path

import eliminate

HERE = Path(__file__).resolve().parent
SOLVER = Path("/Volumes/SSD990/llm/tmp/q1525-dpll-anf/simp/glucose")
PARENT = eliminate.q1527.PARENT
q1519 = eliminate.q1519


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text())


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def ensure_formula(label: str) -> Path:
    frozen = read(HERE / "protocol.json")["inputs"][label]
    packed = HERE / "formulas" / f"{label}.anf.gz"
    assert sha(packed) == frozen["gzip_sha256"]
    data = gzip.decompress(packed.read_bytes())
    assert hashlib.sha256(data).hexdigest() == frozen["anf_sha256"]
    plain = HERE / "formulas" / f"{label}.anf"
    if plain.exists():
        assert plain.read_bytes() == data
    else:
        plain.write_bytes(data)
    return plain


def cpu_limit() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (30, 35))


def verify_sat(label: str, stdout: str) -> dict:
    formula, meta, _ = eliminate.q1527.source_formula(label)
    _, counts, mapping, gates = eliminate.transform(formula)
    rebuilt, raw, leaves, onb = q1519.build(meta["n"], meta["complement_x_coords"])
    for bits, value in zip(raw, meta["pin_raw"]):
        q1519.pin_bits(rebuilt, bits, value)
    for bits, value in zip(leaves, meta["pin_projected"]):
        q1519.pin_bits(rebuilt, bits, value)
    bitstrings = [line[2:] for line in stdout.splitlines()
                  if line.startswith("s ") and set(line[2:]) <= {"0", "1"}]
    assert len(bitstrings) == 1 and len(bitstrings[0]) == counts["variables"]
    assignment = {old: bitstrings[0][new - 1] == "1" for old, new in mapping.items()}
    def value(lit: int) -> bool:
        return assignment[abs(lit)] == (lit > 0)
    for z, (a, b) in gates.items():
        assignment[z] = value(a) and value(b)
    assert len(assignment) == rebuilt.variables
    check = q1519.verify(rebuilt, raw, leaves, onb, meta["complement_x_coords"], assignment)
    return {"model_source": "core_complete_bitstring",
            "solver_assigned_variables": counts["variables"],
            "reconstructed_gate_variables": len(gates),
            "original_assigned_variables": len(assignment), **check}


def run_one(label: str) -> None:
    p = read(HERE / "protocol.json")
    assert label in p["panel_order"]
    assert sha(SOLVER) == p["solver_binary_sha256"]
    assert sha(HERE / "eliminate.py") == p["converter_sha256"]
    assert sha(HERE / "run.py") == p["runner_sha256"]
    frozen = p["inputs"][label]
    source = PARENT / eliminate.INPUTS[label]
    assert sha(source) == frozen["source_xcnf_sha256"]
    formula = ensure_formula(label)
    folder = HERE / "runs" / label
    folder.mkdir(parents=True, exist_ok=False)
    command = [str(SOLVER), *p["solver_options"], str(formula)]
    out, err = folder / "stdout.txt", folder / "stderr.txt"
    started = time.monotonic()
    reason = None
    with out.open("wb") as stdout, err.open("wb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                 preexec_fn=cpu_limit)
        terminated = None
        while True:
            pid, status, usage = os.wait4(child.pid, os.WNOHANG)
            if pid:
                child.returncode = os.waitstatus_to_exitcode(status)
                break
            now = time.monotonic()
            if terminated is None and now - started >= p["wall_seconds"]:
                reason = "WALL_CAP"
                child.terminate()
                terminated = now
            elif terminated is not None and now - terminated >= 5:
                child.kill()
            time.sleep(0.05)
    stdout = out.read_text(errors="replace")
    stderr = err.read_text(errors="replace")
    verified = verify_sat(label, stdout) if "s SATISFIABLE" in stdout else None
    status = ("SAT_VERIFIED" if verified else "WALL_CAP" if reason else
              "INDETERMINATE" if "s INDETERMINATE" in stdout else
              "UNSAT" if "s UNSATISFIABLE" in stdout else
              "CPU_CAP" if child.returncode in (-signal.SIGXCPU, -signal.SIGKILL) else
              "PROCESS_FAILURE")
    conflicts = re.findall(r"^c conflicts\s*:\s*([0-9]+)", stdout, re.I | re.M)
    receipt = {"label": label, "status": status, "candidate_id": None,
               "isogeny": "none", "command": command,
               "return_code": child.returncode, "termination_reason": reason,
               "wall_seconds_exploratory": time.monotonic() - started,
               "child_user_cpu_seconds": usage.ru_utime,
               "child_system_cpu_seconds": usage.ru_stime,
               "child_peak_rss_bytes_darwin": usage.ru_maxrss,
               "reported_conflicts_last": int(conflicts[-1]) if conflicts else None,
               "stdout_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
               "stderr_sha256": hashlib.sha256(err.read_bytes()).hexdigest(),
               "verification": verified}
    save(folder / "receipt.json", receipt)
    print(label, status, round(receipt["child_user_cpu_seconds"], 3),
          receipt["reported_conflicts_last"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    run_one(parser.parse_args().label)
