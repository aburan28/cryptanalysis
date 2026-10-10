#!/usr/bin/env sage -python
"""Pin one free W15 pair on a verified constructed N131 six-pair formula."""

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

import psutil

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
W15 = BASE / "n131_w15_coupled_sixpair_20261010"
ORIGINAL = BASE / "n131_w14_coupled_sixpair_sat_20261010"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
TEMP = Path("/private/tmp/n131_w15_onepair_fixed_sat_20261010")
WALL_CAP = 120
RSS_CAP = 4 * 1024**3
FLAGS = ["--threads=1", "--xor=0", "--printsol=1", "--random=20261010",
         "--maxconfl=20000000", "--maxtime=110"]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def save(path, record):
    with Path(path).open("x") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sources():
    return {
        "runner": Path(__file__),
        "terminal_audit": HERE / "terminal_audit.py",
        "independent_group_audit": HERE / "independent_group_audit.py",
        "original_control": ORIGINAL / "control.json",
        "constructed_formula_gzip": W15 / "constructed.xcnf.gz",
        "constructed_receipt": W15 / "control_result.json",
        "constructed_group_lift": W15 / "control_group_lift.json",
        "w15_circuit": W15 / "w15_circuit.py",
        "w15_experiment": W15 / "experiment.py",
        "w15_lift": W15 / "w15_lift.py",
        "w15_protocol": W15 / "protocol.json",
        "sage_runtime_info": HERE / "sage_runtime_info.json",
        "solver": SOLVER,
    }


def pin_literals(control):
    # w15_circuit.build allocates all twelve 15-bit masks first, in order.
    assert len(control["masks"]) == 12
    return [wire if (control["masks"][atom] >> bit) & 1 else -wire
            for atom in range(2) for bit in range(15)
            for wire in [1 + atom * 15 + bit]]


def freeze():
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    control = json.loads((ORIGINAL / "control.json").read_text())
    receipt = json.loads((W15 / "control_result.json").read_text())
    lift = json.loads((W15 / "control_group_lift.json").read_text())
    assert receipt["status"] == "PASS_FULL_COMPACT_N131_CONSTRUCTED_ASSIGNMENT"
    assert lift["status"] == "PASS_W15_CONSTRUCTED_GROUP_LIFT"
    assert control["target_q"] == receipt["target_q"]
    pins = pin_literals(control)
    assert len(pins) == 30 and max(abs(value) for value in pins) == 30
    record = {
        "status": "FROZEN_BEFORE_CONSTRUCTED_W15_ONE_FREE_PAIR_PINNED_SEARCH",
        "candidate_id": None,
        "curve_id": receipt["curve_id"],
        "target_law": "constructed twelve-atom correctness control",
        "target_q": control["target_q"],
        "pinned_pair_index": 0,
        "pinned_masks": control["masks"][:2],
        "pin_literals": pins,
        "workers": 1,
        "construction_plus_search_cap_seconds": WALL_CAP,
        "rss_cap_bytes": RSS_CAP,
        "solver_flags": FLAGS,
        "source_sha256": {name: sha(path) for name, path in sources().items()},
    }
    save(HERE / "protocol.json", record)
    print(json.dumps({"status": record["status"], "pinned_masks": record["pinned_masks"]}))


def checked_protocol():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_CONSTRUCTED_W15_ONE_FREE_PAIR_PINNED_SEARCH"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    assert protocol["solver_flags"] == FLAGS
    return protocol


def materialize(source, destination, pins):
    with gzip.open(source, "rb") as original, destination.open("xb") as out:
        header = original.readline().decode("ascii")
        assert header == "p cnf 121787 479997\n"
        out.write(f"p cnf 121787 {479997 + len(pins)}\n".encode())
        for block in iter(lambda: original.read(1 << 20), b""):
            out.write(block)
        for literal in pins:
            out.write(f"{literal} 0\n".encode())


def run():
    protocol = checked_protocol()
    assert not TEMP.exists()
    TEMP.mkdir()
    formula = TEMP / "pinned.xcnf"
    started = time.monotonic()
    materialize(W15 / "constructed.xcnf.gz", formula, protocol["pin_literals"])
    materialize_seconds = time.monotonic() - started
    parent = psutil.Process()
    peak_rss = parent.memory_info().rss
    if materialize_seconds >= 10 or peak_rss >= RSS_CAP:
        raise RuntimeError("pinned formula materialization exceeded preflight")
    stdout_path = HERE / "solver.stdout.txt"
    stderr_path = HERE / "solver.stderr.txt"
    command = [str(SOLVER), *FLAGS, str(formula)]
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
    lift_status = None
    if statuses == ["s SATISFIABLE"] and model_lines:
        experiment = load("w15_fixed_pair_experiment", W15 / "experiment.py")
        circuit, meta, _ = experiment.run.formula_for(tuple(protocol["target_q"]))
        assert circuit.next_var - 1 == 121787
        assert meta["masks"][0] == list(range(1, 16))
        assert meta["masks"][1] == list(range(16, 31))
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
        save(HERE / "group_lift.json", group_lift)
        lift_status = group_lift["status"]
        status = ("GROUP_LIFT_PENDING_INDEPENDENT_SAGE" if
                  lift_status == "GROUP_LIFT_FOUND" else "SAT_NO_GROUP_LIFT")
    elif stop_reason == "RSS_CAP":
        status = "OOM"
    elif stop_reason == "PARENT_WALL_CAP" or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "PRODUCER_FAILURE_UNSAT_CONSTRUCTED_CONTROL"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"

    with formula.open("rb") as inp, gzip.open(HERE / "pinned.xcnf.gz", "xb") as out:
        for block in iter(lambda: inp.read(1 << 20), b""):
            out.write(block)
    receipt = {
        "status": status,
        "candidate_id": None,
        "curve_id": protocol["curve_id"],
        "target_q": protocol["target_q"],
        "pinned_pair_index": 0,
        "pinned_masks": protocol["pinned_masks"],
        "formula": {"variables": 121787, "cnf_clauses": 436755,
                    "native_xor_rows": 43272, "bytes": formula.stat().st_size,
                    "sha256": sha(formula), "gzip_sha256": sha(HERE / "pinned.xcnf.gz")},
        "solver_command": command,
        "solver_status_lines": statuses,
        "solver_exit_code": child.returncode,
        "model_lines": model_lines,
        "model_check": model_check,
        "group_lift_status": lift_status,
        "stop_reason": stop_reason,
        "phase_seconds": {"materialize": materialize_seconds,
                          "search": search_seconds,
                          "materialize_plus_search": charged_seconds},
        "sampled_peak_combined_rss_bytes": peak_rss,
        "sampled_solver_cpu_seconds": sampled_cpu,
        "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                          "formula_gzip": sha(HERE / "pinned.xcnf.gz"),
                          "stdout": sha(stdout_path), "stderr": sha(stderr_path)},
    }
    save(HERE / "result.json", receipt)
    formula.unlink()
    TEMP.rmdir()
    print(json.dumps({"status": status, "charged_seconds": charged_seconds,
                      "peak_rss_bytes": peak_rss}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "run"))
    freeze() if parser.parse_args().mode == "freeze" else run()
