#!/usr/bin/env python3
"""Bounded native-ANF solver panel on exact Q1519 S3 formulas."""
from __future__ import annotations

import hashlib
import gzip
import importlib.util
import json
import os
import re
import resource
import signal
import subprocess
import time
from pathlib import Path

import convert

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "q20261012_fixed_pair_s3_handoff"
SOLVER = Path("/Volumes/SSD990/llm/tmp/q1525-dpll-anf/simp/glucose")
SPEC = importlib.util.spec_from_file_location("q1519_handoff", PARENT / "run.py")
assert SPEC and SPEC.loader
q1519 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(q1519)


def read(path: Path):
    return json.loads(path.read_text())


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def ensure_formula(label: str) -> Path:
    manifest = read(HERE / "archive_manifest.json")["current"][label]
    archived = HERE / "formulas" / f"{label}.anf.gz"
    assert convert.sha(archived) == manifest["gzip_sha256"]
    data = gzip.decompress(archived.read_bytes())
    assert hashlib.sha256(data).hexdigest() == manifest["uncompressed_sha256"]
    path = HERE / "formulas" / f"{label}.anf"
    if path.exists():
        assert path.read_bytes() == data
    else:
        path.write_bytes(data)
    return path


def cpu_limit() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (30, 35))


def verify_sat(label: str, stdout: str) -> dict:
    meta_name = convert.INPUTS[label].replace(".xcnf", ".json")
    meta = read(PARENT / meta_name)
    formula, raw, leaves, onb = q1519.build(meta["n"], meta["complement_x_coords"])
    for bits, value in zip(raw, meta["pin_raw"]):
        q1519.pin_bits(formula, bits, value)
    for bits, value in zip(leaves, meta["pin_projected"]):
        q1519.pin_bits(formula, bits, value)
    assert formula.variables == meta["variables"]
    # DPLL_ANF prints its complete search assignment as `s <bits>` before
    # SimpSolver's final `v` model. On this source revision the latter can
    # mis-reconstruct variables eliminated by preprocessing; replay the former.
    bitstrings = [line[2:] for line in stdout.splitlines()
                  if line.startswith("s ") and set(line[2:]) <= {"0", "1"}]
    assert len(bitstrings) == 1 and len(bitstrings[0]) == formula.variables
    assignment = {i + 1: bit == "1" for i, bit in enumerate(bitstrings[0])}
    check = q1519.verify(formula, raw, leaves, onb, meta["complement_x_coords"], assignment)
    return {"model_source": "core_complete_bitstring",
            "model_assigned_variables": len(assignment), **check}


def main() -> None:
    p = read(HERE / "protocol.json")
    assert p["solver_source_commit"] == "26e3b541f3a917ae4015caae1023642bd6310b79"
    assert convert.sha(SOLVER) == p["solver_binary_sha256"]
    assert convert.sha(HERE / "convert.py") == p["converter_sha256"]
    for label in p["panel_order"]:
        formula = ensure_formula(label)
        frozen = p["inputs"][label]
        assert convert.sha(formula) == frozen["anf_sha256"]
        assert convert.sha(PARENT / convert.INPUTS[label]) == frozen["xcnf_sha256"]
        folder = HERE / "runs" / label
        folder.mkdir(parents=True, exist_ok=False)
        command = [str(SOLVER), "-useWatchedLiterals", "-useWatchedMonomials",
                   "-checkModel", "-model", "-cpu-lim=30", str(formula)]
        out, err = folder / "stdout.txt", folder / "stderr.txt"
        start = time.monotonic()
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
                if terminated is None and now - start >= 90:
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
        matches = re.findall(r"^c conflicts\s*:\s*([0-9]+)", stdout, re.I | re.M)
        receipt = {"label": label, "status": status,
                   "candidate_id": None, "isogeny": "none",
                   "command": command, "return_code": child.returncode,
                   "termination_reason": reason,
                   "wall_seconds_exploratory": time.monotonic() - start,
                   "child_user_cpu_seconds": usage.ru_utime,
                   "child_system_cpu_seconds": usage.ru_stime,
                   "child_peak_rss_bytes_darwin": usage.ru_maxrss,
                   "reported_conflicts_last": int(matches[-1]) if matches else None,
                   "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
                   "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(),
                   "verification": verified}
        save(folder / "receipt.json", receipt)
        print(label, status, round(receipt["child_user_cpu_seconds"], 3),
              receipt["reported_conflicts_last"], flush=True)


if __name__ == "__main__":
    main()
