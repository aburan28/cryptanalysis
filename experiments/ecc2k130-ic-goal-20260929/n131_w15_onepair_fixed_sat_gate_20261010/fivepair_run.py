#!/usr/bin/env sage -python
"""Construct, control, and query the exact N131 W15 five-pair residual."""

import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time

import psutil

HERE = Path(__file__).resolve().parent
W15 = HERE.parent / "n131_w15_coupled_sixpair_20261010"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
TEMP = Path("/private/tmp/n131_w15_exact_fivepair_residual_20261010")
WALL_CAP = 120
PARENT_SAFE_STOP = 115
RSS_CAP = 4 * 1024**3
FLAGS = ["--threads=1", "--xor=0", "--printsol=1", "--random=20261010",
         "--maxconfl=20000000", "--maxtime=106"]


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


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


experiment = load("fivepair_w15_experiment", W15 / "experiment.py")
method = load("fivepair_w15_method", HERE / "fivepair_circuit.py")
lift = load("fivepair_w15_lift", HERE / "fivepair_lift.py")


def sources():
    return {"runner": Path(__file__),
            "circuit": HERE / "fivepair_circuit.py",
            "group_lift": HERE / "fivepair_lift.py",
            "input": HERE / "fivepair_input.json",
            "input_preparation": HERE / "prepare_fivepair.py",
            "w15_experiment": W15 / "experiment.py",
            "w15_circuit": W15 / "w15_circuit.py",
            "w15_support": W15 / "support_w15.tsv",
            "w15_group_control": W15 / "control_group_lift.json",
            "runtime": HERE / "sage_runtime_info.json",
            "solver": SOLVER}


def input_record():
    record = json.loads((HERE / "fivepair_input.json").read_text())
    assert record["status"] == "PASS_EXACT_CONSTRUCTED_W15_FIVE_PAIR_RESIDUAL"
    return record


def formula_for(target, fixed_columns):
    columns, field, curve, source_w, _ = experiment.run.source()
    raw_targets = experiment.run.prior.prior.old.target_preimages(curve, target)
    target_reciprocals = [field.inv(point[0]) for point in raw_targets]
    bases = experiment.run.bases(field, source_w)[2:]
    rotations = experiment.run.prior.ROTATIONS[2:]
    circuit = experiment.run.base.KaratsubaCircuit(131, experiment.run.LOW_TERMS)
    meta = method.build(circuit, field, bases, columns, target_reciprocals,
                        rotations, experiment.run.prior.prior.old.method.frob,
                        fixed_columns)
    return circuit, meta, raw_targets


def freeze():
    record = input_record()
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    protocol = {
        "status": "FROZEN_BEFORE_EXACT_CONSTRUCTED_W15_FIVE_PAIR_CONTROL_AND_SEARCH",
        "candidate_id": None,
        "curve_id": record["curve_id"],
        "target_law": "constructed residual from signed first pair",
        "target_q": record["residual_target_q"],
        "fixed_first_pair_raw": record["first_pair_raw"],
        "fixed_first_pair_columns": record["first_pair_columns"],
        "remaining_masks": record["remaining_masks"],
        "workers": 1,
        "construction_plus_search_cap_seconds": WALL_CAP,
        "parent_safe_stop_seconds": PARENT_SAFE_STOP,
        "rss_cap_bytes": RSS_CAP,
        "solver_flags": FLAGS,
        "source_sha256": {name: sha(path) for name, path in sources().items()},
    }
    save(HERE / "fivepair_protocol.json", protocol)
    print(json.dumps({"status": protocol["status"],
                      "target_q": protocol["target_q"]}))


def checked_protocol():
    protocol = json.loads((HERE / "fivepair_protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_EXACT_CONSTRUCTED_W15_FIVE_PAIR_CONTROL_AND_SEARCH"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    assert protocol["solver_flags"] == FLAGS
    return protocol


def profile(circuit, formula):
    cnf = len(circuit.clauses)
    xor = len(circuit.xors)
    with formula.open("rb") as inp:
        assert inp.readline() == f"p cnf {circuit.next_var - 1} {cnf + xor}\n".encode()
    return {"variables": circuit.next_var - 1,
            "cnf_clauses": cnf, "native_xor_rows": xor,
            "bytes": formula.stat().st_size, "sha256": sha(formula)}


def constructed_control():
    protocol = checked_protocol()
    witness = input_record()
    started = time.monotonic()
    circuit, meta, raw_targets = formula_for(
        tuple(protocol["target_q"]), protocol["fixed_first_pair_columns"])
    assert list(raw_targets[witness["residual_target_preimage_index"]]) == witness[
        "residual_raw"]
    formula = HERE / "fivepair_control.xcnf"
    circuit.write(formula)
    built = time.monotonic() - started
    initial = {}
    for row, mask in zip(meta["masks"], witness["remaining_masks"]):
        initial.update({wire: mask >> bit & 1 for bit, wire in enumerate(row)})
    for index, wire in enumerate(meta["flags"]):
        initial[wire] = int(index == witness["residual_target_preimage_index"])
    for row, value in zip(meta["middle"], witness["remaining_middle_reciprocals"]):
        initial.update({wire: value >> bit & 1 for bit, wire in enumerate(row)})
    assert len(initial) == meta["primary_variables"]
    assignment = experiment.run.witness_tools.complete_assignment(circuit, initial)
    check = experiment.run.base.check_xcnf(formula, assignment)
    lifted = lift.lift(witness["remaining_masks"],
                       witness["remaining_middle_reciprocals"],
                       tuple(protocol["target_q"]),
                       witness["residual_target_preimage_index"],
                       protocol["fixed_first_pair_columns"])
    assert lifted["status"] == "GROUP_LIFT_FOUND"
    assert any(item["raw_sum"] == witness["residual_raw"]
               for item in lifted["solutions"])
    save(HERE / "fivepair_control_group_lift.json", lifted)
    form = profile(circuit, formula)
    with formula.open("rb") as inp, gzip.open(HERE / "fivepair_control.xcnf.gz", "xb") as out:
        for block in iter(lambda: inp.read(1 << 20), b""):
            out.write(block)
    formula.unlink()
    elapsed = time.monotonic() - started
    receipt = {"status": "PASS_FULL_XCNF_AND_GROUP_FIVE_PAIR_CONTROL",
               "candidate_id": None, "target_q": protocol["target_q"],
               "formula": {**form, "gzip_sha256": sha(HERE / "fivepair_control.xcnf.gz")},
               "full_assignment_check": check,
               "group_lift_status": lifted["status"],
               "phase_seconds": {"build": built, "check_lift_archive": elapsed - built,
                                 "total": elapsed},
               "source_sha256": {"protocol": sha(HERE / "fivepair_protocol.json"),
                                 "group_lift": sha(HERE / "fivepair_control_group_lift.json")}}
    save(HERE / "fivepair_control_result.json", receipt)
    print(json.dumps({"status": receipt["status"], "formula": form,
                      "build_seconds": built}))


def query():
    protocol = checked_protocol()
    control = json.loads((HERE / "fivepair_control_result.json").read_text())
    assert control["status"] == "PASS_FULL_XCNF_AND_GROUP_FIVE_PAIR_CONTROL"
    assert not TEMP.exists()
    TEMP.mkdir()
    formula = TEMP / "fivepair.xcnf"
    started = time.monotonic()
    circuit, meta, _ = formula_for(tuple(protocol["target_q"]),
                                    protocol["fixed_first_pair_columns"])
    circuit.write(formula)
    built = time.monotonic() - started
    form = profile(circuit, formula)
    assert form["sha256"] == control["formula"]["sha256"]
    parent = psutil.Process()
    peak_rss = parent.memory_info().rss
    if built >= 10 or peak_rss >= RSS_CAP:
        raise RuntimeError("five-pair formula exceeded preflight")
    stdout_path = HERE / "fivepair_solver.stdout.txt"
    stderr_path = HERE / "fivepair_solver.stderr.txt"
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
    search_seconds = time.monotonic() - search_started
    charged = time.monotonic() - started
    output = stdout_path.read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in output.splitlines())
    model_check = None
    group_lift_status = None
    if statuses == ["s SATISFIABLE"] and model_lines:
        model = experiment.run.base.read_model(output, form["variables"])
        model_check = experiment.run.base.check_xcnf(formula, model)
        masks = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                 for row in meta["masks"]]
        middle = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                  for row in meta["middle"]]
        selected = [index for index, wire in enumerate(meta["flags"]) if model[wire]]
        assert len(selected) == 1
        lifted = lift.lift(masks, middle, tuple(protocol["target_q"]), selected[0],
                           protocol["fixed_first_pair_columns"])
        save(HERE / "fivepair_query_group_lift.json", lifted)
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
    receipt = {
        "status": status, "candidate_id": None,
        "target_q": protocol["target_q"],
        "fixed_first_pair_raw": protocol["fixed_first_pair_raw"],
        "formula": form,
        "solver_command": command,
        "solver_status_lines": statuses,
        "solver_exit_code": child.returncode,
        "model_lines": model_lines, "model_check": model_check,
        "group_lift_status": group_lift_status,
        "stop_reason": stop_reason,
        "phase_seconds": {"build": built, "search": search_seconds,
                          "build_plus_search": charged},
        "sampled_peak_combined_rss_bytes": peak_rss,
        "sampled_solver_cpu_seconds": sampled_cpu,
        "source_sha256": {"protocol": sha(HERE / "fivepair_protocol.json"),
                          "formula_gzip": sha(HERE / "fivepair_control.xcnf.gz"),
                          "stdout": sha(stdout_path), "stderr": sha(stderr_path)},
    }
    save(HERE / "fivepair_query_result.json", receipt)
    formula.unlink()
    TEMP.rmdir()
    print(json.dumps({"status": status, "charged_seconds": charged,
                      "peak_rss_bytes": peak_rss}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "control", "query"))
    mode = parser.parse_args().mode
    {"freeze": freeze, "control": constructed_control, "query": query}[mode]()
