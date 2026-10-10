#!/usr/bin/env sage -python
"""Pin the exact first-pair output and search the remaining five W15 pairs."""

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
spec = importlib.util.spec_from_file_location("mask_pin_runner", HERE / "run.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
W15 = base.W15
ORIGINAL = base.ORIGINAL
TEMP = Path("/private/tmp/n131_w15_first_pair_point_fixed_20261010")
WALL_CAP = 120
RSS_CAP = 4 * 1024**3


def point_pins(control, wires):
    # Earlier column and seed constraints allocate private XOR variables;
    # use the actual circuit metadata for the first pair-output wires.
    value = control["middle_reciprocals"][0]
    assert len(wires) == 131 and len(set(wires)) == 131
    return [wire if value >> bit & 1 else -wire
            for bit, wire in enumerate(wires)]


def sources():
    return {
        "runner": Path(__file__),
        "terminal_audit": HERE / "point_terminal_audit.py",
        "mask_runner": HERE / "run.py",
        "mask_protocol": HERE / "protocol.json",
        "mask_formula_gzip": HERE / "pinned.xcnf.gz",
        "mask_result": HERE / "result.json",
        "original_control": ORIGINAL / "control.json",
        "w15_experiment": W15 / "experiment.py",
        "w15_circuit": W15 / "w15_circuit.py",
        "w15_lift": W15 / "w15_lift.py",
        "sage_runtime_info": HERE / "sage_runtime_info.json",
        "solver": base.SOLVER,
    }


def freeze():
    control = json.loads((ORIGINAL / "control.json").read_text())
    mask_protocol = json.loads((HERE / "protocol.json").read_text())
    mask_result = json.loads((HERE / "result.json").read_text())
    assert mask_result["status"] == "CENSORED_TIME"
    assert mask_protocol["pinned_masks"] == control["masks"][:2]
    assert json.loads((HERE / "terminal_audit.json").read_text())["status"] == \
        "PASS_PINNED_W15_TERMINAL_AUDIT"
    experiment = base.load("point_pin_freeze_experiment", W15 / "experiment.py")
    circuit, meta, _ = experiment.run.formula_for(tuple(control["target_q"]))
    assert circuit.next_var - 1 == 121787
    assert meta["masks"][0] == list(range(1, 16))
    assert meta["masks"][1] == list(range(16, 31))
    wires = meta["middle"][0]
    pins = point_pins(control, wires)
    assert len(pins) == 131 and all(1 <= abs(pin) <= 121787 for pin in pins)
    record = {
        "status": "FROZEN_BEFORE_EXACT_FIRST_PAIR_OUTPUT_PINNED_SEARCH",
        "candidate_id": None,
        "curve_id": mask_protocol["curve_id"],
        "target_law": "constructed twelve-atom correctness control",
        "target_q": control["target_q"],
        "pinned_masks": control["masks"][:2],
        "pinned_first_pair_reciprocal": control["middle_reciprocals"][0],
        "first_pair_output_wire_ids": wires,
        "additional_pin_literals": pins,
        "workers": 1,
        "construction_plus_search_cap_seconds": WALL_CAP,
        "rss_cap_bytes": RSS_CAP,
        "solver_flags": base.FLAGS,
        "source_sha256": {name: base.sha(path) for name, path in sources().items()},
    }
    base.save(HERE / "point_protocol.json", record)
    print(json.dumps({"status": record["status"],
                      "pinned_first_pair_reciprocal": record[
                          "pinned_first_pair_reciprocal"]}))


def checked_protocol():
    protocol = json.loads((HERE / "point_protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_EXACT_FIRST_PAIR_OUTPUT_PINNED_SEARCH"
    assert protocol["source_sha256"] == {name: base.sha(path) for name, path in sources().items()}
    return protocol


def materialize(destination, pins):
    with gzip.open(HERE / "pinned.xcnf.gz", "rb") as original, destination.open("xb") as out:
        header = original.readline().decode("ascii")
        assert header == "p cnf 121787 480027\n"
        out.write(f"p cnf 121787 {480027 + len(pins)}\n".encode())
        for block in iter(lambda: original.read(1 << 20), b""):
            out.write(block)
        for literal in pins:
            out.write(f"{literal} 0\n".encode())


def run():
    protocol = checked_protocol()
    assert not TEMP.exists()
    TEMP.mkdir()
    formula = TEMP / "point_pinned.xcnf"
    started = time.monotonic()
    materialize(formula, protocol["additional_pin_literals"])
    materialize_seconds = time.monotonic() - started
    parent = psutil.Process()
    peak_rss = parent.memory_info().rss
    assert materialize_seconds < 10 and peak_rss < RSS_CAP
    stdout_path = HERE / "point_solver.stdout.txt"
    stderr_path = HERE / "point_solver.stderr.txt"
    command = [str(base.SOLVER), *base.FLAGS, str(formula)]
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
            elif time.monotonic() - started >= WALL_CAP:
                stop_reason = "PARENT_WALL_CAP"
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
    search_seconds = time.monotonic() - solver_started
    charged_seconds = time.monotonic() - started
    output = stdout_path.read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in output.splitlines())
    model_check = None
    group_lift_status = None
    if statuses == ["s SATISFIABLE"] and model_lines:
        experiment = base.load("point_pin_result_experiment", W15 / "experiment.py")
        circuit, meta, _ = experiment.run.formula_for(tuple(protocol["target_q"]))
        model = experiment.run.base.read_model(output, 121787)
        model_check = experiment.run.base.check_xcnf(formula, model)
        masks = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                 for row in meta["masks"]]
        middle = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                  for row in meta["middle"]]
        selected = [index for index, wire in enumerate(meta["flags"]) if model[wire]]
        assert len(selected) == 1
        group_lift = experiment.lift.lift(masks, middle, tuple(protocol["target_q"]),
                                          selected[0])
        base.save(HERE / "point_group_lift.json", group_lift)
        group_lift_status = group_lift["status"]
        status = ("GROUP_LIFT_PENDING_INDEPENDENT_SAGE" if
                  group_lift_status == "GROUP_LIFT_FOUND" else "SAT_NO_GROUP_LIFT")
    elif stop_reason == "RSS_CAP":
        status = "OOM"
    elif stop_reason == "PARENT_WALL_CAP" or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "PRODUCER_FAILURE_UNSAT_CONSTRUCTED_CONTROL"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    with formula.open("rb") as inp, gzip.open(HERE / "point_pinned.xcnf.gz", "xb") as out:
        for block in iter(lambda: inp.read(1 << 20), b""):
            out.write(block)
    receipt = {
        "status": status,
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "target_q": protocol["target_q"],
        "pinned_masks": protocol["pinned_masks"],
        "pinned_first_pair_reciprocal": protocol["pinned_first_pair_reciprocal"],
        "formula": {"variables": 121787, "cnf_clauses": 436886,
                    "native_xor_rows": 43272, "bytes": formula.stat().st_size,
                    "sha256": base.sha(formula),
                    "gzip_sha256": base.sha(HERE / "point_pinned.xcnf.gz")},
        "solver_command": command,
        "solver_status_lines": statuses,
        "solver_exit_code": child.returncode,
        "model_lines": model_lines,
        "model_check": model_check,
        "group_lift_status": group_lift_status,
        "stop_reason": stop_reason,
        "phase_seconds": {"materialize": materialize_seconds,
                          "search": search_seconds,
                          "materialize_plus_search": charged_seconds},
        "sampled_peak_combined_rss_bytes": peak_rss,
        "sampled_solver_cpu_seconds": sampled_cpu,
        "source_sha256": {"protocol": base.sha(HERE / "point_protocol.json"),
                          "formula_gzip": base.sha(HERE / "point_pinned.xcnf.gz"),
                          "stdout": base.sha(stdout_path), "stderr": base.sha(stderr_path)},
    }
    base.save(HERE / "point_result.json", receipt)
    formula.unlink()
    TEMP.rmdir()
    print(json.dumps({"status": status, "charged_seconds": charged_seconds,
                      "peak_rss_bytes": peak_rss}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "run"))
    freeze() if parser.parse_args().mode == "freeze" else run()
