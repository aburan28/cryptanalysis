#!/usr/bin/env sage -python
"""Admit the W15 dense and medium XOR matrices under one bounded solver run."""

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time

import psutil

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "n131_w15_trace_fiber_gate_20261010"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
FORMULA = PRIOR / "trace_fiber.xcnf.gz"
TEMP = Path("/private/tmp/n131_w15_gauss_rows_gate_20261010.xcnf")
FLAGS = ["--threads=1", "--xor=0", "--printsol=1", "--random=20261010",
         "--maxconfl=20000000", "--maxtime=106",
         "--maxmatrixcols=10000", "--maxmatrixrows=4000"]
PARENT_SAFE_STOP = 112.5
SOLVER_CAP = 115
RSS_CAP = 4 * 1024**3


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def save(path, value):
    with Path(path).open("x") as sink:
        json.dump(value, sink, indent=2, sort_keys=True)
        sink.write("\n")


def sources():
    return {"runner": Path(__file__),
            "runtime": HERE / "sage_runtime_info.json",
            "width_runner": HERE / "run.py",
            "width_protocol": HERE / "protocol.json",
            "width_result": HERE / "query_result.json",
            "prior_formula_gzip": FORMULA,
            "prior_control": PRIOR / "control_result.json",
            "prior_sage_audit": PRIOR / "sage_trace_audit.json",
            "solver": SOLVER}


def freeze():
    width = json.loads((HERE / "query_result.json").read_text())
    prior_control = json.loads((PRIOR / "control_result.json").read_text())
    assert width["status"] == "CENSORED_TIME"
    assert width["formula_sha256"] == prior_control["formula"]["sha256"]
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    help_text = subprocess.run([str(SOLVER), "--help"], check=True,
                               capture_output=True, text=True).stdout
    rows = next(line for line in help_text.splitlines()
                if line.strip().startswith("--maxmatrixrows"))
    columns = next(line for line in help_text.splitlines()
                   if line.strip().startswith("--maxmatrixcols"))
    assert "[default: 2000]" in rows and "[default: 1000]" in columns
    protocol = {
        "status": "FROZEN_BEFORE_MEDIUM_MATRIX_ELIGIBILITY_QUERY",
        "candidate_id": None,
        "curve_id": "EC1N131Ckb1heb5f1998f20b",
        "target_q": width["target_q"],
        "input_law": "constructed exact signed-prefix W15 five-pair residual",
        "formula_sha256": width["formula_sha256"],
        "variant_flags": FLAGS,
        "default_maxmatrixcols": 1000,
        "default_maxmatrixrows": 2000,
        "variant_maxmatrixcols": 10000,
        "variant_maxmatrixrows": 4000,
        "workers": 1,
        "solver_stage_cap_seconds": SOLVER_CAP,
        "parent_safe_stop_seconds": PARENT_SAFE_STOP,
        "rss_cap_bytes": RSS_CAP,
        "source_sha256": {name: sha(path) for name, path in sources().items()},
    }
    save(HERE / "protocol_rows.json", protocol)
    print(json.dumps({"status": protocol["status"],
                      "formula_sha256": protocol["formula_sha256"]}))


def query():
    protocol = json.loads((HERE / "protocol_rows.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_MEDIUM_MATRIX_ELIGIBILITY_QUERY"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    assert not TEMP.exists()
    with gzip.open(FORMULA, "rb") as source, TEMP.open("xb") as sink:
        for block in iter(lambda: source.read(1 << 20), b""):
            sink.write(block)
    assert sha(TEMP) == protocol["formula_sha256"]
    stdout_path = HERE / "solver_rows.stdout.txt"
    stderr_path = HERE / "solver_rows.stderr.txt"
    command = [str(SOLVER), *FLAGS, str(TEMP)]
    parent = psutil.Process()
    peak_rss = parent.memory_info().rss
    started = time.monotonic()
    stop_reason = None
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                 start_new_session=True)
        process = psutil.Process(child.pid)
        while child.poll() is None:
            try:
                peak_rss = max(peak_rss, parent.memory_info().rss + process.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            if peak_rss >= RSS_CAP:
                stop_reason = "RSS_CAP"
            elif time.monotonic() - started >= PARENT_SAFE_STOP:
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
    solver_seconds = time.monotonic() - started
    output = stdout_path.read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in output.splitlines())
    matrix_lines = [line for line in output.splitlines() if "[matrix] Using" in line]
    if statuses == ["s SATISFIABLE"] and model_lines:
        status = "SAT_PENDING_XCNF_AND_SAGE_REPLAY"
    elif stop_reason == "RSS_CAP":
        status = "OOM"
    elif stop_reason == "PARENT_SAFE_STOP" or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "PRODUCER_FAILURE_UNSAT_CONSTRUCTED_CONTROL"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    receipt = {
        "status": status, "candidate_id": None,
        "target_q": protocol["target_q"],
        "formula_sha256": sha(TEMP),
        "solver_command": command,
        "solver_status_lines": statuses,
        "solver_exit_code": child.returncode,
        "model_lines": model_lines,
        "stop_reason": stop_reason,
        "solver_stage_wall_seconds": solver_seconds,
        "sampled_combined_peak_rss_bytes": peak_rss,
        "matrix_using_lines": matrix_lines,
        "source_sha256": {"protocol": sha(HERE / "protocol_rows.json"),
                          "formula_gzip": sha(FORMULA),
                          "stdout": sha(stdout_path), "stderr": sha(stderr_path)},
    }
    save(HERE / "query_rows_result.json", receipt)
    TEMP.unlink()
    print(json.dumps({"status": status,
                      "solver_stage_wall_seconds": solver_seconds,
                      "peak_rss_bytes": peak_rss,
                      "matrix_using_lines": matrix_lines}), flush=True)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2 or sys.argv[1] not in ("freeze", "query"):
        raise SystemExit("usage: run_rows.py freeze|query")
    {"freeze": freeze, "query": query}[sys.argv[1]]()
