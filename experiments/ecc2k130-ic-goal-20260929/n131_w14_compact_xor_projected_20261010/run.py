#!/usr/bin/env python3
"""Exact private-XOR projection and bounded solve of the compact N131 XCNF."""

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
SOURCE = GOAL / "n131_w14_compact_columns_20261010"
PROJECTOR = GOAL / "xor_projection_20261009/project_xcnf.py"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
RSS_CAP = 4 * 1024**3
TOTAL_CAP = 600.0
PROJECT_CAP = 180.0
FLAGS = ["--threads=1", "--xor=0", "--printsol=1",
         "--random=20261010", "--maxconfl=20000000"]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def save(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")


def source_paths():
    return {
        "run": HERE / "run.py",
        "projector": PROJECTOR,
        "public_formula_gzip": SOURCE / "public_query/system.xcnf.gz",
        "constructed_formula_gzip": SOURCE / "constructed.xcnf.gz",
        "public_result": SOURCE / "public_query/result.json",
        "constructed_result": SOURCE / "control_result.json",
        "compact_terminal_audit": SOURCE / "terminal_audit.json",
        "checked_sage_runtime": HERE / "sage_runtime_info.json",
        "solver": SOLVER,
    }


def freeze():
    public = json.loads((SOURCE / "public_query/result.json").read_text())
    control = json.loads((SOURCE / "control_result.json").read_text())
    terminal = json.loads((SOURCE / "terminal_audit.json").read_text())
    assert terminal["status"] == "PASS_COMPACT_N131_TERMINAL_CENSORED_AUDIT"
    assert public["status"] == "CENSORED_TIME"
    assert control["status"] == "PASS_FULL_COMPACT_N131_CONSTRUCTED_ASSIGNMENT"
    assert public["formula"]["sha256"] == "01ff129bda5bc03722bfe97fa4f09b71145ca336a7e2c91779312d9f73446eac"
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    protocol = {
        "status": "FROZEN_BEFORE_COMPACT_N131_XOR_PROJECTION_AND_SEARCH",
        "candidate_id": None,
        "curve_id": public["curve_id"],
        "target_q": public["target_q"],
        "target_count": 1,
        "workers": 1,
        "rss_cap_bytes": RSS_CAP,
        "total_construction_projection_search_cap_seconds": TOTAL_CAP,
        "projection_wall_cap_seconds_per_formula": PROJECT_CAP,
        "original_target_formula_seconds": public["phase_seconds"]["target_formula"],
        "projected_solver_flags": FLAGS,
        "input_uncompressed_sha256": {
            "public": public["formula"]["sha256"],
            "constructed": control["formula"]["sha256"],
        },
        "input_uncompressed_bytes": {
            "public": public["formula"]["bytes"],
            "constructed": control["formula"]["bytes"],
        },
        "source_sha256": {name: sha(path) for name, path in source_paths().items()},
    }
    assert protocol["original_target_formula_seconds"] < 5
    save(HERE / "protocol.json", protocol)
    print(json.dumps({"status": protocol["status"], "target_q": protocol["target_q"]}))


def checked_protocol():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_COMPACT_N131_XOR_PROJECTION_AND_SEARCH"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in source_paths().items()}
    return protocol


def input_to_temp(label, directory, protocol):
    source = (SOURCE / "constructed.xcnf.gz" if label == "constructed"
              else SOURCE / "public_query/system.xcnf.gz")
    path = directory / "input.xcnf"
    digest = hashlib.sha256()
    size = 0
    with gzip.open(source, "rb") as inp, path.open("xb") as out:
        for block in iter(lambda: inp.read(1 << 20), b""):
            digest.update(block)
            size += len(block)
            out.write(block)
    assert digest.hexdigest() == protocol["input_uncompressed_sha256"][label]
    assert size == protocol["input_uncompressed_bytes"][label]
    return path


def monitored(command, stdout_path, stderr_path, cap_seconds):
    parent = psutil.Process()
    peak_rss = parent.memory_info().rss
    sampled_cpu = 0.0
    started = time.monotonic()
    stop_reason = None
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                 start_new_session=True)
        process = psutil.Process(child.pid)
        while child.poll() is None:
            try:
                peak_rss = max(peak_rss, parent.memory_info().rss + process.memory_info().rss)
                cpu = process.cpu_times()
                sampled_cpu = max(sampled_cpu, cpu.user + cpu.system)
            except psutil.NoSuchProcess:
                pass
            if peak_rss >= RSS_CAP:
                stop_reason = "RSS_CAP"
            elif time.monotonic() - started >= cap_seconds:
                stop_reason = "WALL_CAP"
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
    return {"wall_seconds": time.monotonic() - started,
            "sampled_peak_combined_rss_bytes": peak_rss,
            "sampled_child_cpu_seconds": sampled_cpu,
            "exit_code": child.returncode,
            "stop_reason": stop_reason,
            "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path)}


def compress(source, destination):
    with source.open("rb") as inp, gzip.open(destination, "xb", compresslevel=6) as out:
        for block in iter(lambda: inp.read(1 << 20), b""):
            out.write(block)


def project(label):
    protocol = checked_protocol()
    folder = HERE / label
    folder.mkdir(exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="n131_compact_xor_projection_", dir="/private/tmp") as temp:
        directory = Path(temp)
        input_path = input_to_temp(label, directory, protocol)
        output = directory / "projected"
        command = [sys.executable, str(PROJECTOR),
                   "--input", str(input_path),
                   "--expected-sha256", protocol["input_uncompressed_sha256"][label],
                   "--runtime", str(HERE / "sage_runtime_info.json"),
                   "--output-dir", str(output)]
        monitor = monitored(command, folder / "projector.stdout.txt",
                            folder / "projector.stderr.txt", PROJECT_CAP)
        status = "PASS" if monitor["exit_code"] == 0 and monitor["stop_reason"] is None else (
            "OOM" if monitor["stop_reason"] == "RSS_CAP" else "CENSORED_TIME"
            if monitor["stop_reason"] == "WALL_CAP" else "PRODUCER_FAILURE")
        projected = None
        if status == "PASS":
            projector_result = json.loads((output / "result.json").read_text())
            assert projector_result["status"] == "PASS"
            assert projector_result["source_sha256"]["input_xcnf"] == sha(input_path)
            assert projector_result["source_sha256"]["projected_xcnf"] == sha(output / "projected.xcnf")
            assert projector_result["projected_contradictions"] == 0
            for name in ("result.json", "variable_map.json", "lift_rows.jsonl"):
                shutil.copyfile(output / name, folder / name)
            compress(output / "projected.xcnf", folder / "projected.xcnf.gz")
            projected = {"source_result": projector_result,
                         "gzip_sha256": sha(folder / "projected.xcnf.gz"),
                         "source_sha256": {name: sha(folder / name) for name in
                                           ("result.json", "variable_map.json", "lift_rows.jsonl")}}
        receipt = {"status": status, "label": label, "candidate_id": None,
                   "curve_id": protocol["curve_id"],
                   "target_q": protocol["target_q"] if label == "public" else None,
                   "command": command, "projection": projected,
                   "monitor": monitor,
                   "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                                     "input_gzip": protocol["source_sha256"][
                                         "public_formula_gzip" if label == "public"
                                         else "constructed_formula_gzip"]}}
        save(folder / "projection_receipt.json", receipt)
        print(json.dumps({"status": status, "label": label,
                          "wall_seconds": monitor["wall_seconds"],
                          "projected_variables": projected["source_result"]["projected_variables"]
                          if projected else None}), flush=True)


def solve():
    protocol = checked_protocol()
    control = json.loads((HERE / "constructed/control_audit.json").read_text())
    assert control["status"] == "PASS_PROJECTED_CONSTRUCTED_WITNESS"
    projected = json.loads((HERE / "public/projection_receipt.json").read_text())
    assert projected["status"] == "PASS"
    projection_seconds = projected["monitor"]["wall_seconds"]
    solver_cap = TOTAL_CAP - protocol["original_target_formula_seconds"] - projection_seconds - 10
    assert solver_cap > 30
    folder = HERE / "public_solver"
    folder.mkdir(exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="n131_compact_xor_solver_", dir="/private/tmp") as temp:
        formula = Path(temp) / "projected.xcnf"
        digest = hashlib.sha256()
        with gzip.open(HERE / "public/projected.xcnf.gz", "rb") as inp, formula.open("xb") as out:
            for block in iter(lambda: inp.read(1 << 20), b""):
                digest.update(block)
                out.write(block)
        assert digest.hexdigest() == projected["projection"]["source_result"]["source_sha256"]["projected_xcnf"]
        command = [str(SOLVER), *FLAGS, f"--maxtime={max(1, int(solver_cap) - 2)}", str(formula)]
        monitor = monitored(command, folder / "solver.stdout.txt",
                            folder / "solver.stderr.txt", solver_cap)
    lines = (folder / "solver.stdout.txt").read_text(errors="replace").splitlines()
    statuses = [line for line in lines if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in lines)
    if statuses == ["s SATISFIABLE"] and model_lines:
        status = "SAT_MODEL_PENDING_CHECK"
    elif monitor["stop_reason"] == "RSS_CAP":
        status = "OOM"
    elif monitor["stop_reason"] == "WALL_CAP" or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "UNSAT_FORMULA"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    receipt = {"status": status, "candidate_id": None,
               "curve_id": protocol["curve_id"], "target_q": protocol["target_q"],
               "target_count": 1, "workers": 1, "command": command,
               "solver_status_lines": statuses, "model_lines": model_lines,
               "monitor": monitor,
               "charged_formula_projection_solver_seconds":
                   protocol["original_target_formula_seconds"] + projection_seconds + monitor["wall_seconds"],
               "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                                 "projected_formula_gzip": sha(HERE / "public/projected.xcnf.gz"),
                                 "public_projection_receipt": sha(HERE / "public/projection_receipt.json"),
                                 "constructed_control_audit": sha(HERE / "constructed/control_audit.json")}}
    save(folder / "result.json", receipt)
    print(json.dumps({"status": status, "solver_wall_seconds": monitor["wall_seconds"],
                      "charged_seconds": receipt["charged_formula_projection_solver_seconds"],
                      "peak_rss_bytes": monitor["sampled_peak_combined_rss_bytes"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "project_constructed", "project_public", "solve"))
    mode = parser.parse_args().mode
    if mode == "freeze":
        freeze()
    elif mode.startswith("project_"):
        project(mode.removeprefix("project_"))
    else:
        solve()
