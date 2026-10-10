#!/usr/bin/env sage -python
"""Run the frozen W15 public query with large artifacts on the local temp volume."""

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
import subprocess
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
OUTPUT = Path("/private/tmp/n131_w15_coupled_sixpair_public_20261010")
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
RSS_CAP = 4 * 1024**3
CAP_SECONDS = 600.0
FLAGS = ["--threads=1", "--xor=0", "--printsol=1",
         "--random=20261010", "--maxconfl=20000000"]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def save(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def sources():
    return {"runner": Path(__file__),
            "experiment": HERE / "experiment.py",
            "circuit": HERE / "w15_circuit.py",
            "group_lift": HERE / "w15_lift.py",
            "support": HERE / "support_w15.tsv",
            "support_audit": HERE / "sage_support_audit.json",
            "group_audit": HERE / "sage_group_audit.json",
            "control": HERE / "control_result.json",
            "control_group_lift": HERE / "control_group_lift.json",
            "checked_sage_runtime": HERE / "sage_runtime_info.json",
            "solver": SOLVER}


def freeze():
    protocol = json.loads((HERE / "protocol.json").read_text())
    control = json.loads((HERE / "control_result.json").read_text())
    lift = json.loads((HERE / "control_group_lift.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_W15_N131_CONTROL_AND_PUBLIC_QUERY"
    assert control["status"] == "PASS_FULL_COMPACT_N131_CONSTRUCTED_ASSIGNMENT"
    assert lift["status"] == "PASS_W15_CONSTRUCTED_GROUP_LIFT"
    assert not OUTPUT.exists()
    record = {
        "status": "FROZEN_BEFORE_W15_N131_UNPINNED_PUBLIC_QUERY_ON_TEMP_VOLUME",
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "target_q": protocol["public_target_q"],
        "target_count": 1,
        "workers": 1,
        "output_dir": str(OUTPUT),
        "construction_plus_search_cap_seconds": CAP_SECONDS,
        "rss_cap_bytes": RSS_CAP,
        "solver_flags": FLAGS,
        "source_sha256": {name: sha(path) for name, path in sources().items()},
        "w15_protocol_sha256": sha(HERE / "protocol.json"),
    }
    save(HERE / "query_protocol.json", record)
    print(json.dumps({"status": record["status"], "target_q": record["target_q"]}))


def checked_protocol():
    protocol = json.loads((HERE / "query_protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_W15_N131_UNPINNED_PUBLIC_QUERY_ON_TEMP_VOLUME"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    assert protocol["w15_protocol_sha256"] == sha(HERE / "protocol.json")
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    return protocol


def compress(source, destination):
    with source.open("rb") as inp, gzip.open(destination, "xb", compresslevel=6) as out:
        for block in iter(lambda: inp.read(1 << 20), b""):
            out.write(block)


def query():
    protocol = checked_protocol()
    experiment = load("w15_temp_query_experiment", HERE / "experiment.py")
    OUTPUT.mkdir(exist_ok=False)
    started = time.monotonic()
    target = tuple(protocol["target_q"])
    circuit, meta, lifts = experiment.run.formula_for(target)
    assert meta["duplicate_column_clauses"] == 8250
    formula = OUTPUT / "system.xcnf"
    circuit.write(formula)
    construction_seconds = time.monotonic() - started
    formula_profile = experiment.metadata(circuit, meta, formula)
    parent = psutil.Process()
    peak_rss = parent.memory_info().rss
    remaining = CAP_SECONDS - construction_seconds - 10
    if remaining <= 30 or peak_rss >= RSS_CAP:
        raise RuntimeError("W15 formula exceeded frozen resource gate")
    command = [str(SOLVER), *FLAGS,
               f"--maxtime={max(1, int(remaining) - 2)}", str(formula)]
    stdout_path = OUTPUT / "solver.stdout.txt"
    stderr_path = OUTPUT / "solver.stderr.txt"
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                 start_new_session=True)
        process = psutil.Process(child.pid)
        solver_started = time.monotonic()
        stop_reason = None
        sampled_cpu = 0.0
        while child.poll() is None:
            try:
                peak_rss = max(peak_rss, parent.memory_info().rss + process.memory_info().rss)
                cpu = process.cpu_times()
                sampled_cpu = max(sampled_cpu, cpu.user + cpu.system)
            except psutil.NoSuchProcess:
                pass
            if peak_rss >= RSS_CAP:
                stop_reason = "RSS_CAP"
            elif time.monotonic() - started >= CAP_SECONDS:
                stop_reason = "QUERY_WALL_CAP"
            elif time.monotonic() - solver_started >= remaining:
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
    solver_seconds = time.monotonic() - solver_started
    output = stdout_path.read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in output.splitlines())
    model_check = None
    group_lift = None
    if statuses == ["s SATISFIABLE"] and model_lines:
        model = experiment.run.base.read_model(output, formula_profile["variables"])
        model_check = experiment.run.base.check_xcnf(formula, model)
        masks = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                 for row in meta["masks"]]
        middle = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                  for row in meta["middle"]]
        selected = [index for index, wire in enumerate(meta["flags"]) if model[wire]]
        assert len(selected) == 1
        group_lift = experiment.lift.lift(masks, middle, target, selected[0])
        save(OUTPUT / "group_lift.json", group_lift)
        status = ("GROUP_RELATION_PENDING_INDEPENDENT_SAGE" if
                  group_lift["status"] == "GROUP_LIFT_FOUND" else "SAT_NO_GROUP_LIFT")
    elif stop_reason == "RSS_CAP":
        status = "OOM"
    elif stop_reason in ("QUERY_WALL_CAP", "SOLVER_WALL_CAP") or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "UNSAT_FORMULA"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    compress(formula, OUTPUT / "system.xcnf.gz")
    formula.unlink()
    receipt = {
        "status": status, "candidate_id": None,
        "curve_id": protocol["curve_id"], "target_count": 1,
        "target_q": list(target), "raw_target_preimages": [list(point) for point in lifts],
        "formula": {**formula_profile,
                    "gzip_sha256": sha(OUTPUT / "system.xcnf.gz")},
        "solver_command": command,
        "solver_status_lines": statuses,
        "model_lines": model_lines,
        "solver_exit_code": child.returncode,
        "stop_reason": stop_reason,
        "producer_xcnf_check": model_check,
        "group_lift_status": group_lift["status"] if group_lift else None,
        "verified_relations": 0,
        "useful_rank": 0,
        "phase_seconds": {
            "target_formula": construction_seconds,
            "solver": solver_seconds,
            "construction_plus_search": construction_seconds + solver_seconds,
            "process_through_archive": time.monotonic() - started,
        },
        "sampled_peak_combined_rss_bytes": peak_rss,
        "sampled_solver_cpu_seconds": sampled_cpu,
        "sha256": {
            "query_protocol": sha(HERE / "query_protocol.json"),
            "w15_protocol": sha(HERE / "protocol.json"),
            "control": sha(HERE / "control_result.json"),
            "control_group_lift": sha(HERE / "control_group_lift.json"),
            "stdout": sha(stdout_path), "stderr": sha(stderr_path),
            "formula_gzip": sha(OUTPUT / "system.xcnf.gz"),
        },
    }
    save(OUTPUT / "result.json", receipt)
    try:
        save(HERE / "public_query_result.json", receipt)
    except OSError:
        pass  # Exact receipt and raw artifacts remain in OUTPUT.
    print(json.dumps({"status": status,
                      "construction_plus_search_seconds": construction_seconds + solver_seconds,
                      "formula": formula_profile,
                      "peak_rss_bytes": peak_rss,
                      "result_path": str(OUTPUT / "result.json")}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "query"))
    freeze() if parser.parse_args().mode == "freeze" else query()
