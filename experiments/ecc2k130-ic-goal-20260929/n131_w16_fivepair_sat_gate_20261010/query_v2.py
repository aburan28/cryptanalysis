#!/usr/bin/env sage -python
"""Bounded W16 five-pair extraction with formula, model, and group checks."""

import hashlib
import importlib.util
import json
import subprocess
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
W16 = HERE.parent / "n131_w16_w18_sixpair_width_gate_20261010"
TEMP = Path("/private/tmp/n131_w16_fivepair_query_v2_20261010")
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
WALL_CAP = 120
SAFE_STOP = 115
RSS_CAP = 4 * 1024**3
FLAGS = ["--threads=1", "--xor=0", "--printsol=1", "--random=20261010",
         "--maxconfl=20000000", "--maxtime=106"]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run = load("w16_control_runner", HERE / "fivepair_run.py")


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def paths():
    return {"query": HERE / "query_v2.py", "control_runner": HERE / "fivepair_run.py",
            "circuit": HERE / "fivepair_circuit.py", "lift": HERE / "fivepair_lift.py",
            "input": HERE / "fivepair_input.json", "control_protocol": HERE / "fivepair_protocol.json",
            "control_result": HERE / "fivepair_control_result.json",
            "control_formula": HERE / "fivepair_control.xcnf.gz",
            "control_group_lift": HERE / "fivepair_control_group_lift.json",
            "support": W16 / "support_w16.tsv", "support_audit": W16 / "audit_result.json",
            "runtime": HERE / "sage_runtime_info.json", "solver": SOLVER}


def main():
    protocol = json.loads((HERE / "query_v2_protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_W16_FIVE_PAIR_QUERY_V2"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in paths().items()}
    assert protocol["wall_cap_seconds"] == WALL_CAP
    assert protocol["parent_safe_stop_seconds"] == SAFE_STOP
    assert protocol["rss_cap_bytes"] == RSS_CAP
    assert protocol["solver_flags"] == FLAGS
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    control = json.loads((HERE / "fivepair_control_result.json").read_text())
    assert control["status"] == "PASS_FULL_XCNF_AND_GROUP_FIVE_PAIR_CONTROL"
    assert not TEMP.exists()
    TEMP.mkdir()
    formula = TEMP / "fivepair.xcnf"
    started = time.monotonic()
    circuit, meta, _ = run.formula_for(tuple(protocol["target_q"]),
                                       protocol["fixed_first_pair_columns"])
    circuit.write(formula)
    built = time.monotonic() - started
    form = run.profile(circuit, formula)
    assert form["sha256"] == control["formula"]["sha256"]
    parent = psutil.Process()
    peak_rss = parent.memory_info().rss
    if built >= 60 or peak_rss >= RSS_CAP:
        raise RuntimeError("W16 formula exceeded construction preflight")
    stdout_path = HERE / "query_v2_solver.stdout.txt"
    stderr_path = HERE / "query_v2_solver.stderr.txt"
    command = [str(SOLVER), *FLAGS, str(formula)]
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                 start_new_session=True)
        process = psutil.Process(child.pid)
        search_started = time.monotonic()
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
            elif time.monotonic() - started >= SAFE_STOP:
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
    search_seconds = time.monotonic() - search_started
    charged = time.monotonic() - started
    output = stdout_path.read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in output.splitlines())
    model_check = None
    group_lift_status = None
    if statuses == ["s SATISFIABLE"] and model_lines:
        model = run.experiment.run.base.read_model(output, form["variables"])
        model_check = run.experiment.run.base.check_xcnf(formula, model)
        masks = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                 for row in meta["masks"]]
        middle = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                  for row in meta["middle"]]
        selected = [index for index, wire in enumerate(meta["flags"]) if model[wire]]
        assert len(selected) == 1
        lifted = run.lift.lift(masks, middle, tuple(protocol["target_q"]),
                               selected[0], protocol["fixed_first_pair_columns"])
        (HERE / "query_v2_group_lift.json").write_text(
            json.dumps(lifted, sort_keys=True, indent=2) + "\n")
        group_lift_status = lifted["status"]
        status = ("GROUP_LIFT_PENDING_INDEPENDENT_SAGE" if
                  group_lift_status == "GROUP_LIFT_FOUND" else "SAT_NO_GROUP_LIFT")
    elif stop_reason == "RSS_CAP":
        status = "OOM"
    elif stop_reason == "PARENT_SAFE_STOP" or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "PRODUCER_FAILURE_UNSAT_CONSTRUCTED_CONTROL"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    if charged > WALL_CAP:
        status = "CENSORED_TIME_OVERRUN"
    receipt = {"status": status, "candidate_id": None,
               "target_q": protocol["target_q"],
               "fixed_first_pair_columns": protocol["fixed_first_pair_columns"],
               "formula": form, "solver_command": command,
               "solver_status_lines": statuses, "solver_exit_code": child.returncode,
               "model_lines": model_lines, "model_check": model_check,
               "group_lift_status": group_lift_status, "stop_reason": stop_reason,
               "phase_seconds": {"build": built, "search": search_seconds,
                                 "build_plus_search": charged},
               "sampled_peak_combined_rss_bytes": peak_rss,
               "sampled_solver_cpu_seconds": sampled_cpu,
               "source_sha256": {"protocol": sha(HERE / "query_v2_protocol.json"),
                                 "formula_gzip": sha(HERE / "fivepair_control.xcnf.gz"),
                                 "stdout": sha(stdout_path), "stderr": sha(stderr_path)}}
    (HERE / "query_v2_result.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    formula.unlink()
    TEMP.rmdir()
    print(json.dumps({"status": status, "charged_seconds": charged,
                      "peak_rss_bytes": peak_rss}), flush=True)


if __name__ == "__main__":
    main()
