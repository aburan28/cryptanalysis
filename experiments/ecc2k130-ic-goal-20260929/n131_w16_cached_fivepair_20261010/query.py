#!/usr/bin/env sage -python
"""Search one exact W16 residual from the reusable source circuit."""

import hashlib
import importlib.util
import json
import subprocess
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "n131_w16_fivepair_sat_gate_20261010"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
TEMP = Path("/private/tmp/n131_w16_cached_fivepair_query_20261010")
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


run = load("cached_w16_runner", HERE / "run.py")


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def paths():
    return {"query": HERE / "query.py", "runner": HERE / "run.py",
            "core_source": HERE / "core.py", "core": HERE / "core.pickle.gz",
            "core_result": HERE / "core_result.json",
            "base_protocol": HERE / "protocol.json",
            "control_result": HERE / "control_result.json",
            "control_formula": HERE / "control.xcnf.gz",
            "input": OLD / "fivepair_input.json",
            "runtime": HERE / "sage_runtime_info.json", "solver": SOLVER}


def main():
    frozen = json.loads((HERE / "query_protocol.json").read_text())
    assert frozen["status"] == "FROZEN_BEFORE_CACHED_W16_QUERY"
    assert frozen["source_sha256"] == {name: sha(path) for name, path in paths().items()}
    assert frozen["wall_cap_seconds"] == WALL_CAP
    assert frozen["parent_safe_stop_seconds"] == SAFE_STOP
    assert frozen["rss_cap_bytes"] == RSS_CAP
    assert frozen["solver_flags"] == FLAGS
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    control = json.loads((HERE / "control_result.json").read_text())
    assert control["status"] == "PASS_CACHED_W16_FULL_XCNF_AND_GROUP_CONTROL"
    assert not TEMP.exists()
    setup_started = time.monotonic_ns()
    circuit, state = run.load_core()
    _, field, curve, _, _ = run.old.experiment.run.source()
    setup_ns = time.monotonic_ns()-setup_started
    TEMP.mkdir()
    formula = TEMP / "query.xcnf"
    started = time.monotonic_ns()
    raw_targets = run.old.experiment.run.prior.prior.old.target_preimages(
        curve, tuple(frozen["target_q"]))
    target_reciprocals = [field.inv(point[0]) for point in raw_targets]
    query_ns = time.monotonic_ns()-started
    meta = run.method.finish(circuit, field, state, target_reciprocals,
                             frozen["fixed_first_pair_columns"])
    finish_ns = time.monotonic_ns()-started-query_ns
    circuit.write(formula)
    formula_ns = time.monotonic_ns()-started-query_ns-finish_ns
    form = run.profile(circuit, formula)
    assert form["sha256"] == control["formula"]["sha256"]
    parent = psutil.Process()
    peak_rss = parent.memory_info().rss
    if (time.monotonic_ns()-started >= 30*10**9 or peak_rss >= RSS_CAP):
        raise RuntimeError("cached formula exceeded query preflight")
    command = [str(SOLVER), *FLAGS, str(formula)]
    stdout_path = HERE / "solver.stdout.txt"
    stderr_path = HERE / "solver.stderr.txt"
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                 start_new_session=True)
        process = psutil.Process(child.pid)
        search_started = time.monotonic_ns()
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
            elif time.monotonic_ns()-started >= SAFE_STOP*10**9:
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
    search_ns = time.monotonic_ns()-search_started
    charged_ns = time.monotonic_ns()-started
    output = stdout_path.read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in output.splitlines())
    model_check = None
    group_lift_status = None
    if statuses == ["s SATISFIABLE"] and model_lines:
        model = run.old.experiment.run.base.read_model(output, form["variables"])
        model_check = run.old.experiment.run.base.check_xcnf(formula, model)
        masks = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                 for row in meta["masks"]]
        middle = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                  for row in meta["middle"]]
        selected = [index for index, wire in enumerate(meta["flags"]) if model[wire]]
        assert len(selected) == 1
        lifted = run.old.lift.lift(masks, middle, tuple(frozen["target_q"]),
                                   selected[0], frozen["fixed_first_pair_columns"])
        (HERE / "query_group_lift.json").write_text(
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
    if charged_ns > WALL_CAP*10**9:
        status = "CENSORED_TIME_OVERRUN"
    receipt = {"status": status, "candidate_id": None,
               "target_q": frozen["target_q"],
               "fixed_first_pair_columns": frozen["fixed_first_pair_columns"],
               "formula": form, "solver_command": command,
               "solver_status_lines": statuses, "solver_exit_code": child.returncode,
               "model_lines": model_lines, "model_check": model_check,
               "group_lift_status": group_lift_status, "stop_reason": stop_reason,
               "phase_ns": {"target_independent_cache_load": setup_ns,
                            "target_preimages": query_ns,
                            "target_suffix": finish_ns,
                            "formula_write": formula_ns,
                            "solver_search": search_ns,
                            "charged_total": charged_ns},
               "sampled_peak_combined_rss_bytes": peak_rss,
               "sampled_solver_cpu_seconds": sampled_cpu,
               "source_sha256": {"protocol": sha(HERE / "query_protocol.json"),
                                 "control_formula": sha(HERE / "control.xcnf.gz"),
                                 "stdout": sha(stdout_path), "stderr": sha(stderr_path)}}
    (HERE / "query_result.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    formula.unlink()
    TEMP.rmdir()
    print(json.dumps({"status": status, "charged_seconds": charged_ns/1e9,
                      "target_suffix_seconds": finish_ns/1e9,
                      "peak_rss_bytes": peak_rss}), flush=True)


if __name__ == "__main__":
    main()
