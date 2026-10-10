#!/usr/bin/env sage -python
"""Bounded no-Gauss solver replay of the frozen W16 native-XOR formula."""

import argparse
import gzip
import hashlib
import json
import subprocess
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_w16_cached_fivepair_20261010"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
TEMP = Path("/private/tmp/n131_w16_nogauss_gate_20261010")
FLAGS = ["--threads=1", "--xor=0", "--printsol=1", "--random=20261010",
         "--maxconfl=20000000", "--maxtime=106", "--maxnummatrices=0"]
SAFE_STOP_SECONDS = 115
RSS_CAP = 4 * 1024**3


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def paths():
    return {"runner": HERE / "run.py",
            "formula_gzip": BASE / "control.xcnf.gz",
            "control_result": BASE / "control_result.json",
            "prior_query_result": BASE / "query_result.json",
            "prior_query_protocol": BASE / "query_protocol.json",
            "runtime": HERE / "sage_runtime_info.json",
            "solver": SOLVER}


def freeze():
    control = json.loads((BASE / "control_result.json").read_text())
    previous = json.loads((BASE / "query_result.json").read_text())
    assert control["status"] == "PASS_CACHED_W16_FULL_XCNF_AND_GROUP_CONTROL"
    assert previous["status"] == "CENSORED_TIME"
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    row = {"status": "FROZEN_BEFORE_W16_NO_GAUSS_GATE",
           "candidate_id": None, "curve_id": "EC1N131Ckb1heb5f1998f20b",
           "input_law": "same constructed signed-prefix W16 residual XCNF as cached control",
           "formula_sha256": control["formula"]["sha256"],
           "formula_profile": {key: control["formula"][key] for key in
                               ("variables", "cnf_clauses", "native_xor_rows")},
           "solver_flags": FLAGS, "workers": 1,
           "solver_safe_stop_seconds": SAFE_STOP_SECONDS,
           "parent_cap_seconds": 120, "rss_cap_bytes": RSS_CAP,
           "source_sha256": {name: sha(path) for name, path in paths().items()}}
    with (HERE / "protocol.json").open("x") as stream:
        json.dump(row, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": row["status"]}))


def execute():
    frozen = json.loads((HERE / "protocol.json").read_text())
    assert frozen["status"] == "FROZEN_BEFORE_W16_NO_GAUSS_GATE"
    assert frozen["source_sha256"] == {name: sha(path) for name, path in paths().items()}
    assert frozen["solver_flags"] == FLAGS
    assert not TEMP.exists()
    TEMP.mkdir()
    formula = TEMP / "frozen.xcnf"
    setup_started = time.monotonic_ns()
    with gzip.open(BASE / "control.xcnf.gz", "rb") as source, formula.open("xb") as dest:
        for block in iter(lambda: source.read(1 << 20), b""):
            dest.write(block)
    assert sha(formula) == frozen["formula_sha256"]
    setup_ns = time.monotonic_ns()-setup_started
    parent = psutil.Process()
    peak_rss = parent.memory_info().rss
    stdout_path = HERE / "solver.stdout.txt"
    stderr_path = HERE / "solver.stderr.txt"
    command = [str(SOLVER), *FLAGS, str(formula)]
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                 start_new_session=True)
        started = time.monotonic_ns()
        process = psutil.Process(child.pid)
        sampled_cpu = 0.0
        stop_reason = None
        while child.poll() is None:
            try:
                peak_rss = max(peak_rss, parent.memory_info().rss + process.memory_info().rss)
                cpu = process.cpu_times()
                sampled_cpu = max(sampled_cpu, cpu.user + cpu.system)
            except psutil.NoSuchProcess:
                pass
            if peak_rss >= RSS_CAP:
                stop_reason = "RSS_CAP"
            elif time.monotonic_ns()-started >= SAFE_STOP_SECONDS*10**9:
                stop_reason = "PARENT_SAFE_STOP"
            if stop_reason:
                child.terminate()
                break
            time.sleep(.05)
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
            stop_reason = (stop_reason or "DRAIN_TIMEOUT") + "_KILLED"
    solver_ns = time.monotonic_ns()-started
    output = stdout_path.read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in output.splitlines())
    restart_lines = sum(line.startswith("c rst ") for line in output.splitlines())
    if statuses == ["s SATISFIABLE"] and model_lines:
        status = "SAT_PENDING_INDEPENDENT_MODEL_AND_GROUP_CHECK"
    elif stop_reason == "RSS_CAP":
        status = "OOM"
    elif stop_reason == "PARENT_SAFE_STOP" or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "PRODUCER_FAILURE_UNSAT_CONSTRUCTED_CONTROL"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    if solver_ns > frozen["parent_cap_seconds"]*10**9:
        status = "CENSORED_TIME_OVERRUN"
    row = {"status": status, "candidate_id": None,
           "formula_sha256": frozen["formula_sha256"],
           "solver_command": command, "solver_exit_code": child.returncode,
           "solver_status_lines": statuses, "model_lines": model_lines,
           "restart_lines": restart_lines, "stop_reason": stop_reason,
           "phase_ns": {"formula_decompress_and_hash": setup_ns,
                        "solver_subprocess": solver_ns},
           "sampled_peak_combined_rss_bytes": peak_rss,
           "sampled_solver_cpu_seconds": sampled_cpu,
           "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                             "stdout": sha(stdout_path),
                             "stderr": sha(stderr_path)}}
    with (HERE / "result.json").open("x") as stream:
        json.dump(row, stream, sort_keys=True, indent=2)
        stream.write("\n")
    formula.unlink()
    TEMP.rmdir()
    print(json.dumps({"status": status, "solver_seconds": solver_ns/1e9,
                      "restart_lines": restart_lines,
                      "peak_rss_bytes": peak_rss}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "run"))
    {"freeze": freeze, "run": execute}[parser.parse_args().mode]()
