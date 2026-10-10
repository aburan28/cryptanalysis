#!/usr/bin/env sage -python
"""Bounded Gaussian-matrix gate on the frozen compact N131 public formula."""

import argparse
import gzip
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_w14_compact_columns_20261010"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
RSS_CAP = 4 * 1024**3
FLAGS = ["--threads=1", "--xor=0", "--printsol=1",
         "--random=20261010", "--maxconfl=20000000",
         "--maxmatrixrows=3500", "--maxmatrixcols=10000"]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def save(path, value):
    with Path(path).open("x") as out:
        json.dump(value, out, indent=2, sort_keys=True)
        out.write("\n")


def sources():
    return {"runner": Path(__file__),
            "compact_protocol": SOURCE / "protocol.json",
            "compact_terminal_audit": SOURCE / "terminal_audit.json",
            "compact_result": SOURCE / "public_query/result.json",
            "compact_formula_gzip": SOURCE / "public_query/system.xcnf.gz",
            "checked_sage_runtime": HERE / "sage_runtime_info.json",
            "solver": SOLVER}


def freeze():
    prior = json.loads((SOURCE / "public_query/result.json").read_text())
    terminal = json.loads((SOURCE / "terminal_audit.json").read_text())
    assert terminal["status"] == "PASS_COMPACT_N131_TERMINAL_CENSORED_AUDIT"
    assert prior["status"] == "CENSORED_TIME"
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    record = {
        "status": "FROZEN_BEFORE_N131_MODERATE_GAUSS_COMPONENT_PREFLIGHT",
        "candidate_id": None, "curve_id": prior["curve_id"],
        "target_q": prior["target_q"], "target_count": 1,
        "workers": 1, "rss_cap_bytes": RSS_CAP,
        "preflight_solver_wall_cap_seconds": 60,
        "full_solver_wall_cap_seconds": 596,
        "full_total_cap_seconds_including_prior_formula_build": 600,
        "prior_formula_build_seconds": prior["phase_seconds"]["target_formula"],
        "solver_flags": FLAGS,
        "matrix_policy": "admit up to five components at most 3500 rows and 10000 columns; larger main component remains excluded",
        "input_formula_uncompressed_sha256": prior["formula"]["sha256"],
        "input_formula_uncompressed_bytes": prior["formula"]["bytes"],
        "source_sha256": {name: sha(path) for name,path in sources().items()},
    }
    assert record["prior_formula_build_seconds"] + 596 < 600
    save(HERE / "protocol.json", record)
    print(json.dumps({"status": record["status"], "target_q": record["target_q"]}))


def protocol_checked():
    record = json.loads((HERE / "protocol.json").read_text())
    assert record["status"] == "FROZEN_BEFORE_N131_MODERATE_GAUSS_COMPONENT_PREFLIGHT"
    assert record["source_sha256"] == {name: sha(path) for name,path in sources().items()}
    return record


def decompress_input(protocol, label):
    path = Path(f"/private/tmp/n131_compact_gauss_{label}_{os.getpid()}.xcnf")
    if path.exists():
        raise FileExistsError(path)
    digest = hashlib.sha256()
    size = 0
    with gzip.open(SOURCE / "public_query/system.xcnf.gz", "rb") as inp, path.open("xb") as out:
        while block := inp.read(1 << 20):
            digest.update(block)
            size += len(block)
            out.write(block)
    assert digest.hexdigest() == protocol["input_formula_uncompressed_sha256"]
    assert size == protocol["input_formula_uncompressed_bytes"]
    return path


def used_matrices(log):
    values = []
    for line in log:
        if "[matrix] Using " in line and " matrices recovered" in line:
            values.append(int(line.split("[matrix] Using ", 1)[1].split()[0]))
    return values


def execute(label, cap_seconds):
    protocol = protocol_checked()
    folder = HERE / label
    folder.mkdir(exist_ok=False)
    formula = decompress_input(protocol, label)
    command = [str(SOLVER), *FLAGS, f"--maxtime={cap_seconds - 2}", str(formula)]
    stdout_path, stderr_path = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
    parent = psutil.Process()
    peak_rss = parent.memory_info().rss
    started = time.monotonic()
    sampled_cpu = 0.0
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                 start_new_session=True)
        process = psutil.Process(child.pid)
        stop_reason = None
        while child.poll() is None:
            try:
                peak_rss = max(peak_rss, parent.memory_info().rss
                               + process.memory_info().rss)
                cpu = process.cpu_times()
                sampled_cpu = max(sampled_cpu, cpu.user + cpu.system)
            except psutil.NoSuchProcess:
                pass
            if peak_rss >= protocol["rss_cap_bytes"]:
                stop_reason = "RSS_CAP"
            elif time.monotonic() - started >= cap_seconds:
                stop_reason = "SOLVER_WALL_CAP"
            if stop_reason:
                child.terminate()
                break
            time.sleep(.1)
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
            stop_reason = (stop_reason or "DRAIN_TIMEOUT") + "_KILLED"
    elapsed = time.monotonic() - started
    output = stdout_path.read_text(errors="replace")
    lines = output.splitlines()
    statuses = [line for line in lines if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in lines)
    matrix_counts = used_matrices(lines)
    if statuses == ["s SATISFIABLE"] and model_lines:
        status = "SAT_MODEL_PENDING_CHECK"
    elif stop_reason == "RSS_CAP":
        status = "OOM"
    elif stop_reason == "SOLVER_WALL_CAP" or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "UNSAT_FORMULA"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    result = {
        "status": status, "candidate_id": None,
        "curve_id": protocol["curve_id"], "target_q": protocol["target_q"],
        "target_count": 1, "solver_command": command,
        "solver_status_lines": statuses, "model_lines": model_lines,
        "solver_exit_code": child.returncode, "stop_reason": stop_reason,
        "solver_wall_seconds": elapsed, "solver_wall_cap_seconds": cap_seconds,
        "sampled_peak_combined_rss_bytes": peak_rss,
        "sampled_solver_cpu_seconds": sampled_cpu,
        "gaussian_matrices_used_observations": matrix_counts,
        "gaussian_matrix_admitted": any(count > 0 for count in matrix_counts),
        "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                          "input_formula_gzip": sha(SOURCE / "public_query/system.xcnf.gz"),
                          "stdout": sha(stdout_path), "stderr": sha(stderr_path)},
    }
    save(folder / "result.json", result)
    formula.unlink()
    print(json.dumps({"status": status, "mode": label,
                      "wall_seconds": elapsed, "peak_rss_bytes": peak_rss,
                      "matrix_counts": matrix_counts}), flush=True)


def full():
    protocol = protocol_checked()
    preflight = json.loads((HERE / "preflight/result.json").read_text())
    assert preflight["source_sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert preflight["gaussian_matrix_admitted"]
    assert preflight["status"] == "CENSORED_TIME"
    assert preflight["sampled_peak_combined_rss_bytes"] < protocol["rss_cap_bytes"]
    execute("full", protocol["full_solver_wall_cap_seconds"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "preflight", "full"))
    mode = parser.parse_args().mode
    if mode == "freeze":
        freeze()
    elif mode == "preflight":
        execute("preflight", 60)
    else:
        full()
