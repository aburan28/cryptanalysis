#!/usr/bin/env sage -python
"""Freeze and test the exact trace-zero raw target fiber for W15."""

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
PRIOR = HERE.parent / "n131_w15_onepair_fixed_sat_gate_20261010"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
TEMP = Path("/private/tmp/n131_w15_trace_fiber_gate_20261010.xcnf")
FLAGS = ["--threads=1", "--xor=0", "--printsol=1", "--random=20261010",
         "--maxconfl=20000000", "--maxtime=106"]
CAP = 120
SAFE_STOP = 115
RSS_CAP = 4 * 1024**3


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prior = load_module("trace_fiber_prior", PRIOR / "fivepair_run.py")


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
            "sage_auditor": HERE / "sage_trace_audit.py",
            "runtime": HERE / "sage_runtime_info.json",
            "prior_runner": PRIOR / "fivepair_run.py",
            "prior_circuit": PRIOR / "fivepair_circuit.py",
            "prior_input": PRIOR / "fivepair_input.json",
            "prior_control": PRIOR / "fivepair_control_result.json",
            "prior_group_audit": PRIOR / "fivepair_sage_audit.json",
            "prior_formula_gzip": PRIOR / "fivepair_control.xcnf.gz",
            "solver": SOLVER}


def record():
    value = json.loads((PRIOR / "fivepair_input.json").read_text())
    assert value["status"] == "PASS_EXACT_CONSTRUCTED_W15_FIVE_PAIR_RESIDUAL"
    return value


def trace(field, value):
    total = 0
    power = value
    for _ in range(131):
        total ^= power
        power = field.mul(power, power)
    assert total in (0, 1)
    return total


def state():
    inp = record()
    columns, field, curve, source_w, _ = prior.experiment.run.source()
    assert len(columns) == 16441
    assert source_w == [1 << i for i in range(1, 16)]
    assert all(trace(field, basis) == 0 for basis in source_w)
    raw = prior.experiment.run.prior.prior.old.target_preimages(
        curve, tuple(inp["residual_target_q"]))
    reciprocals = [field.inv(point[0]) for point in raw]
    traces = [trace(field, value) for value in reciprocals]
    assert traces == [0, 1, 0, 1]
    assert inp["residual_target_preimage_index"] == 2
    return inp, field, raw, reciprocals, traces


def formula():
    inp, _, raw, _, _ = state()
    circuit, meta, source_raw = prior.formula_for(
        tuple(inp["residual_target_q"]), inp["first_pair_columns"])
    assert source_raw == raw
    assert meta["flags"] == [151, 152, 153, 154]
    return inp, circuit, meta


def frozen():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_TRACE_FIBER_CONTROL_AND_QUERY"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    return protocol


def freeze():
    inp, _, _, values, traces = state()
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    prior_result = json.loads((PRIOR / "fivepair_control_result.json").read_text())
    assert prior_result["status"] == "PASS_FULL_XCNF_AND_GROUP_FIVE_PAIR_CONTROL"
    protocol = {
        "status": "FROZEN_BEFORE_TRACE_FIBER_CONTROL_AND_QUERY",
        "candidate_id": None,
        "curve_id": inp["curve_id"],
        "target_law": "constructed exact signed-prefix W15 five-pair residual",
        "target_q": inp["residual_target_q"],
        "raw_target_reciprocals": values,
        "raw_target_reciprocal_traces": traces,
        "admissible_target_preimage_indices": [0, 2],
        "eliminated_flag_wires": [152, 154],
        "constructed_witness_preimage_index": inp["residual_target_preimage_index"],
        "base_formula_sha256": prior_result["formula"]["sha256"],
        "workers": 1, "construction_plus_search_cap_seconds": CAP,
        "parent_safe_stop_seconds": SAFE_STOP, "rss_cap_bytes": RSS_CAP,
        "solver_flags": FLAGS,
        "source_sha256": {name: sha(path) for name, path in sources().items()},
    }
    save(HERE / "protocol.json", protocol)
    print(json.dumps({"status": protocol["status"], "traces": traces,
                      "admissible": protocol["admissible_target_preimage_indices"]}))


def write_variant(circuit, meta, protocol):
    assert meta["flags"] == [151, 152, 153, 154]
    for wire in protocol["eliminated_flag_wires"]:
        circuit.clauses.append(f"-{wire} 0")
    circuit.write(TEMP)
    return {"sha256": sha(TEMP), "bytes": TEMP.stat().st_size,
            "variables": circuit.next_var - 1,
            "cnf_clauses": len(circuit.clauses),
            "native_xor_rows": len(circuit.xors)}


def control():
    protocol = frozen()
    assert not TEMP.exists()
    inp, circuit, meta = formula()
    form = write_variant(circuit, meta, protocol)
    assert form["variables"] == 97105
    assert form["cnf_clauses"] == 354230
    assert form["native_xor_rows"] == 34540
    initial = {}
    for row, mask in zip(meta["masks"], inp["remaining_masks"]):
        initial.update({wire: mask >> bit & 1 for bit, wire in enumerate(row)})
    for index, wire in enumerate(meta["flags"]):
        initial[wire] = int(index == inp["residual_target_preimage_index"])
    for row, value in zip(meta["middle"], inp["remaining_middle_reciprocals"]):
        initial.update({wire: value >> bit & 1 for bit, wire in enumerate(row)})
    assignment = prior.experiment.run.witness_tools.complete_assignment(circuit, initial)
    check = prior.experiment.run.base.check_xcnf(TEMP, assignment)
    assert check == {"cnf_clauses": 354230, "xor_rows": 34540}
    with TEMP.open("rb") as source, gzip.open(HERE / "trace_fiber.xcnf.gz", "xb") as sink:
        for block in iter(lambda: source.read(1 << 20), b""):
            sink.write(block)
    TEMP.unlink()
    receipt = {"status": "PASS_FULL_TRACE_FIBER_XCNF_CONTROL",
               "candidate_id": None, "formula": {**form,
                   "gzip_sha256": sha(HERE / "trace_fiber.xcnf.gz")},
               "full_assignment_check": check,
               "witness_preimage_index": inp["residual_target_preimage_index"],
               "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                                 "prior_group_audit": sha(PRIOR / "fivepair_sage_audit.json")}}
    save(HERE / "control_result.json", receipt)
    print(json.dumps({"status": receipt["status"], "formula": form}))


def query():
    protocol = frozen()
    control_result = json.loads((HERE / "control_result.json").read_text())
    sage_audit = json.loads((HERE / "sage_trace_audit.json").read_text())
    assert sage_audit["status"] == "PASS_INDEPENDENT_SAGE_TRACE_FIBER_AUDIT"
    assert control_result["status"] == "PASS_FULL_TRACE_FIBER_XCNF_CONTROL"
    assert not TEMP.exists()
    started = time.monotonic()
    inp, circuit, meta = formula()
    form = write_variant(circuit, meta, protocol)
    built = time.monotonic() - started
    assert form["sha256"] == control_result["formula"]["sha256"]
    assert built < 10
    stdout_path = HERE / "solver.stdout.txt"
    stderr_path = HERE / "solver.stderr.txt"
    command = [str(SOLVER), *FLAGS, str(TEMP)]
    parent = psutil.Process()
    peak_rss = parent.memory_info().rss
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                 start_new_session=True)
        process = psutil.Process(child.pid)
        search_started = time.monotonic()
        stop_reason = None
        while child.poll() is None:
            try:
                peak_rss = max(peak_rss, parent.memory_info().rss + process.memory_info().rss)
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
    charged = time.monotonic() - started
    search = time.monotonic() - search_started
    output = stdout_path.read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in output.splitlines())
    model_check = None
    group_status = None
    if statuses == ["s SATISFIABLE"] and model_lines:
        model = prior.experiment.run.base.read_model(output, form["variables"])
        model_check = prior.experiment.run.base.check_xcnf(TEMP, model)
        masks = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                 for row in meta["masks"]]
        middle = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                  for row in meta["middle"]]
        selected = [index for index, wire in enumerate(meta["flags"]) if model[wire]]
        assert len(selected) == 1 and selected[0] in (0, 2)
        lifted = prior.lift.lift(masks, middle, tuple(inp["residual_target_q"]),
                                 selected[0], inp["first_pair_columns"])
        save(HERE / "query_group_lift.json", lifted)
        group_status = lifted["status"]
        status = ("GROUP_LIFT_PENDING_INDEPENDENT_SAGE" if group_status == "GROUP_LIFT_FOUND"
                  else "SAT_NO_GROUP_LIFT")
    elif stop_reason == "RSS_CAP":
        status = "OOM"
    elif stop_reason == "PARENT_SAFE_STOP" or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "PRODUCER_FAILURE_UNSAT_CONSTRUCTED_CONTROL"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    receipt = {"status": status, "candidate_id": None, "target_q": inp["residual_target_q"],
               "formula": form, "solver_command": command,
               "solver_status_lines": statuses, "solver_exit_code": child.returncode,
               "model_lines": model_lines, "model_check": model_check,
               "group_lift_status": group_status, "stop_reason": stop_reason,
               "phase_seconds": {"build": built, "search": search,
                                 "build_plus_search": charged},
               "sampled_peak_combined_rss_bytes": peak_rss,
               "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                                 "formula_gzip": sha(HERE / "trace_fiber.xcnf.gz"),
                                 "stdout": sha(stdout_path), "stderr": sha(stderr_path)}}
    save(HERE / "query_result.json", receipt)
    TEMP.unlink()
    print(json.dumps({"status": status, "charged_seconds": charged,
                      "peak_rss_bytes": peak_rss}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "control", "query"))
    {"freeze": freeze, "control": control, "query": query}[parser.parse_args().mode]()
