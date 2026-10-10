#!/usr/bin/env python3
"""Source-identical CryptoMiniSat Gaussian-width gate for W15 N131."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import time

import psutil

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "n131_w15_trace_fiber_gate_20261010"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
TEMP = Path("/private/tmp/n131_w15_gauss_width_gate_20261010.xcnf")
FORMULA = PRIOR / "trace_fiber.xcnf.gz"
BASE_FLAGS = ["--threads=1", "--xor=0", "--printsol=1", "--random=20261010",
              "--maxconfl=20000000", "--maxtime=106"]
VARIANT_FLAGS = [*BASE_FLAGS, "--maxmatrixcols=4096"]
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
            "prior_formula_gzip": FORMULA,
            "prior_protocol": PRIOR / "protocol.json",
            "prior_control": PRIOR / "control_result.json",
            "prior_query": PRIOR / "query_result.json",
            "prior_terminal_audit": PRIOR / "terminal_audit.json",
            "prior_sage_audit": PRIOR / "sage_trace_audit.json",
            "solver": SOLVER}


def freeze():
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    prior_result = json.loads((PRIOR / "query_result.json").read_text())
    prior_control = json.loads((PRIOR / "control_result.json").read_text())
    prior_audit = json.loads((PRIOR / "terminal_audit.json").read_text())
    assert prior_result["status"] == "CENSORED_TIME"
    assert prior_control["status"] == "PASS_FULL_TRACE_FIBER_XCNF_CONTROL"
    assert prior_audit["status"] == "PASS_TRACE_FIBER_TERMINAL_AUDIT"
    assert prior_result["formula"]["sha256"] == prior_control["formula"]["sha256"]
    assert prior_result["solver_command"][1:-1] == BASE_FLAGS
    help_text = subprocess.run([str(SOLVER), "--help"], check=True,
                               capture_output=True, text=True).stdout
    assert "--maxmatrixcols" in help_text
    assert "[default: 1000]" in next(line for line in help_text.splitlines()
                                     if line.strip().startswith("--maxmatrixcols"))
    record = {
        "status": "FROZEN_BEFORE_SOURCE_IDENTICAL_GAUSS_WIDTH_QUERY",
        "candidate_id": None,
        "curve_id": "EC1N131Ckb1heb5f1998f20b",
        "target_q": prior_result["target_q"],
        "input_law": "constructed exact signed-prefix W15 five-pair residual",
        "formula_sha256": prior_result["formula"]["sha256"],
        "formula_bytes": prior_result["formula"]["bytes"],
        "baseline_flags": BASE_FLAGS,
        "variant_flags": VARIANT_FLAGS,
        "default_maxmatrixcols": 1000,
        "variant_maxmatrixcols": 4096,
        "matrix_gate_from_baseline_log": "five 130 x 3929 matrices marked Too many columns",
        "workers": 1,
        "solver_stage_cap_seconds": SOLVER_CAP,
        "parent_safe_stop_seconds": PARENT_SAFE_STOP,
        "rss_cap_bytes": RSS_CAP,
        "source_sha256": {name: sha(path) for name, path in sources().items()},
    }
    save(HERE / "protocol.json", record)
    print(json.dumps({"status": record["status"],
                      "formula_sha256": record["formula_sha256"]}))


def frozen():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_SOURCE_IDENTICAL_GAUSS_WIDTH_QUERY"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    assert protocol["variant_flags"] == VARIANT_FLAGS
    return protocol


def query():
    protocol = frozen()
    assert not TEMP.exists()
    with gzip.open(FORMULA, "rb") as source, TEMP.open("xb") as sink:
        for block in iter(lambda: source.read(1 << 20), b""):
            sink.write(block)
    assert TEMP.stat().st_size == protocol["formula_bytes"]
    assert sha(TEMP) == protocol["formula_sha256"]
    stdout_path = HERE / "solver.stdout.txt"
    stderr_path = HERE / "solver.stderr.txt"
    command = [str(SOLVER), *VARIANT_FLAGS, str(TEMP)]
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
    matrix_lines = [line for line in output.splitlines() if
                    ("[matrix] Good" in line or "[matrix] UNused matrix" in line or
                     "[matrix] Using" in line or "[matrix] Too many" in line)]
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
        "matrix_log_summary": {
            "good_dense_130x3929_lines": sum("130 x 3929" in line and
                                             "[matrix] Good" in line for line in matrix_lines),
            "too_many_columns_3929_lines": sum("Too many columns in matrix: 3929" in
                                               line for line in matrix_lines),
            "using_matrix_lines": [line for line in matrix_lines if "[matrix] Using" in line],
        },
        "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                          "formula_gzip": sha(FORMULA),
                          "stdout": sha(stdout_path), "stderr": sha(stderr_path)},
    }
    save(HERE / "query_result.json", receipt)
    TEMP.unlink()
    print(json.dumps({"status": status, "solver_stage_wall_seconds": solver_seconds,
                      "peak_rss_bytes": peak_rss,
                      "matrix_log_summary": receipt["matrix_log_summary"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "query"))
    {"freeze": freeze, "query": query}[parser.parse_args().mode]()
