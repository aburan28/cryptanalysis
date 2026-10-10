#!/usr/bin/env sage -python
"""Frozen W16 decision-graph membership control and bounded query."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import time

import psutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PRIOR = ROOT / "n131_w16_fivepair_sat_gate_20261010"
SUPPORT = ROOT / "n131_w16_w18_sixpair_width_gate_20261010" / "support_w16.tsv"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
RSS_CAP = 4 * 1024**3
TOTAL_CAP = 120
FLAGS = ["--threads=1", "--xor=0", "--printsol=1", "--random=20261010",
         "--maxconfl=20000000", "--maxtime=100"]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


original = load("bdd_original_w16_run", PRIOR / "fivepair_run.py")
method = load("bdd_method", HERE / "core.py")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def sources():
    return {"runner": HERE / "run.py", "bdd": HERE / "bdd.py",
            "core": HERE / "core.py", "support": SUPPORT,
            "original_runner": PRIOR / "fivepair_run.py",
            "original_method": PRIOR / "fivepair_circuit.py",
            "input": PRIOR / "fivepair_input.json",
            "original_control": PRIOR / "fivepair_control_result.json",
            "solver": SOLVER, "runtime": HERE / "sage_runtime_info.json"}


def frozen():
    row = json.loads((HERE / "protocol.json").read_text())
    assert row["source_sha256"] == {k: sha(v) for k, v in sources().items()}
    assert row["solver_flags"] == FLAGS
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    return row


def freeze():
    inp = json.loads((PRIOR / "fivepair_input.json").read_text())
    prior = json.loads((PRIOR / "fivepair_control_result.json").read_text())
    assert prior["status"] == "PASS_FULL_XCNF_AND_GROUP_FIVE_PAIR_CONTROL"
    row = {"status": "FROZEN_BEFORE_W16_BDD_CONTROL_AND_BOUNDED_SEARCH",
           "candidate_id": None, "curve_id": inp["curve_id"],
           "target_law": "constructed signed-prefix exact residual control",
           "target_q": inp["residual_target_q"],
           "fixed_columns": inp["first_pair_columns"],
           "solver_flags": FLAGS, "workers": 1,
           "total_cap_seconds": TOTAL_CAP, "rss_cap_bytes": RSS_CAP,
           "source_sha256": {k: sha(v) for k, v in sources().items()}}
    save(HERE / "protocol.json", row)
    print(json.dumps({"status": row["status"], "curve_id": row["curve_id"]}))


def formula(protocol):
    columns, field, curve, source_w, _ = original.experiment.run.source()
    raw = original.experiment.run.prior.prior.old.target_preimages(
        curve, tuple(protocol["target_q"]))
    reciprocal = [field.inv(point[0]) for point in raw]
    bases = original.experiment.run.bases(field, source_w)[2:]
    rotations = original.experiment.run.prior.ROTATIONS[2:]
    circuit = original.experiment.run.base.KaratsubaCircuit(131,
                                                             original.experiment.run.LOW_TERMS)
    state = method.prepare(circuit, columns)
    membership_clauses = sum(row["clauses"] for row in state["membership"])
    meta = method.finish(circuit, state, field, bases, reciprocal, rotations,
                         original.experiment.run.prior.prior.old.method.frob,
                         protocol["fixed_columns"])
    meta.update({"membership_clauses": membership_clauses,
                 "membership_auxiliary_variables":
                 sum(len(row["wires"]) for row in state["membership"]),
                 "decision_nodes": len(state["membership_graph"])})
    return circuit, state, meta, raw


def profile(circuit, path):
    return {"variables": circuit.next_var - 1,
            "cnf_clauses": len(circuit.clauses),
            "native_xor_rows": len(circuit.xors),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def control():
    protocol = frozen()
    witness = json.loads((PRIOR / "fivepair_input.json").read_text())
    started = time.monotonic_ns()
    circuit, state, meta, raw = formula(protocol)
    built = time.monotonic_ns()
    assert list(raw[witness["residual_target_preimage_index"]]) == witness["residual_raw"]
    with tempfile.TemporaryDirectory(prefix="w16_bdd_control_", dir="/private/tmp") as temp:
        path = Path(temp) / "control.xcnf"
        circuit.write(path)
        written = time.monotonic_ns()
        initial = {}
        for row, member, mask in zip(meta["masks"], state["membership"],
                                     witness["remaining_masks"]):
            initial.update({wire: mask >> bit & 1 for bit, wire in enumerate(row)})
            initial.update(method.bdd.assignment(state["membership_graph"],
                                                 member["wires"], mask))
        for index, wire in enumerate(meta["flags"]):
            initial[wire] = int(index == witness["residual_target_preimage_index"])
        for row, value in zip(meta["middle"], witness["remaining_middle_reciprocals"]):
            initial.update({wire: value >> bit & 1 for bit, wire in enumerate(row)})
        assert len(initial) == meta["primary_variables"] + meta["membership_auxiliary_variables"]
        assignment = original.experiment.run.witness_tools.complete_assignment(circuit, initial)
        check = original.experiment.run.base.check_xcnf(path, assignment)
        form = profile(circuit, path)
    prior = json.loads((PRIOR / "fivepair_control_result.json").read_text())
    assert prior["group_lift_status"] == "GROUP_LIFT_FOUND"
    row = {"status": "PASS_BDD_TRUTH_TABLE_AND_FULL_XCNF_CONTROL",
           "candidate_id": None, "target_q": protocol["target_q"],
           "formula": form, "full_assignment_check": check,
           "group_lift_status": prior["group_lift_status"],
           "membership": {"nodes": meta["decision_nodes"],
                          "clauses": meta["membership_clauses"],
                          "auxiliary_variables": meta["membership_auxiliary_variables"]},
           "phase_ns": {"build": built - started, "write": written - built,
                        "check": time.monotonic_ns() - written},
           "source_sha256": protocol["source_sha256"]}
    save(HERE / "control.json", row)
    print(json.dumps({"status": row["status"], "formula": form,
                      "membership": row["membership"]}))


def query():
    protocol = frozen()
    control_row = json.loads((HERE / "control.json").read_text())
    assert control_row["status"] == "PASS_BDD_TRUTH_TABLE_AND_FULL_XCNF_CONTROL"
    started = time.monotonic()
    circuit, state, meta, _ = formula(protocol)
    with tempfile.TemporaryDirectory(prefix="w16_bdd_query_", dir="/private/tmp") as temp:
        path = Path(temp) / "query.xcnf"
        circuit.write(path)
        form = profile(circuit, path)
        assert form["sha256"] == control_row["formula"]["sha256"]
        build_seconds = time.monotonic() - started
        with (HERE / "solver.stdout.txt").open("x") as out, \
             (HERE / "solver.stderr.txt").open("x") as err:
            child = subprocess.Popen([str(SOLVER), *FLAGS, str(path)],
                                     stdout=out, stderr=err, start_new_session=True)
            proc = psutil.Process(child.pid)
            parent = psutil.Process()
            peak = 0
            sampled_cpu = 0.0
            stop = None
            while child.poll() is None:
                try:
                    peak = max(peak, proc.memory_info().rss + parent.memory_info().rss)
                    cpu = proc.cpu_times()
                    sampled_cpu = max(sampled_cpu, cpu.user + cpu.system)
                except psutil.NoSuchProcess:
                    pass
                if peak >= RSS_CAP:
                    stop = "RSS_CAP"
                elif time.monotonic() - started >= TOTAL_CAP - 5:
                    stop = "SAFE_WALL_STOP"
                if stop:
                    child.terminate()
                    break
                time.sleep(.05)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
                stop = (stop or "DRAIN_TIMEOUT") + "_KILLED"
        output = (HERE / "solver.stdout.txt").read_text(errors="replace")
        statuses = [line for line in output.splitlines() if line.startswith("s ")]
        model_lines = sum(line.startswith("v ") for line in output.splitlines())
        model_check = None
        group_lift = None
        if statuses == ["s SATISFIABLE"] and model_lines:
            model = original.experiment.run.base.read_model(output, form["variables"])
            model_check = original.experiment.run.base.check_xcnf(path, model)
            masks = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                     for row in meta["masks"]]
            middle = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                      for row in meta["middle"]]
            selected = [i for i, wire in enumerate(meta["flags"]) if model[wire]]
            assert len(selected) == 1
            lifted = original.lift.lift(masks, middle, tuple(protocol["target_q"]),
                                        selected[0], protocol["fixed_columns"])
            group_lift = lifted["status"]
            save(HERE / "query_group_lift.json", lifted)
            status = "GROUP_LIFT_FOUND" if group_lift == "GROUP_LIFT_FOUND" else "SAT_NO_GROUP_LIFT"
        elif stop == "RSS_CAP":
            status = "OOM"
        elif stop == "SAFE_WALL_STOP" or "s INDETERMINATE" in statuses:
            status = "CENSORED_TIME"
        elif statuses == ["s UNSATISFIABLE"]:
            status = "PRODUCER_FAILURE_UNSAT_CONSTRUCTED_CONTROL"
        else:
            status = "PRODUCER_OR_SOLVER_FAILURE"
        row = {"status": status, "candidate_id": None,
               "formula": form, "target_q": protocol["target_q"],
               "solver_command": [str(SOLVER), *FLAGS, "<query.xcnf>"],
               "solver_status_lines": statuses, "model_lines": model_lines,
               "model_check": model_check, "group_lift_status": group_lift,
               "stop_reason": stop, "solver_exit_code": child.returncode,
               "phase_seconds": {"build": build_seconds,
                                 "search": time.monotonic() - started - build_seconds,
                                 "total": time.monotonic() - started},
               "sampled_peak_combined_rss_bytes": peak,
               "sampled_solver_cpu_seconds": sampled_cpu,
               "source_sha256": protocol["source_sha256"],
               "output_sha256": {"stdout": sha(HERE / "solver.stdout.txt"),
                                 "stderr": sha(HERE / "solver.stderr.txt")}}
        save(HERE / "query.json", row)
        print(json.dumps({"status": status, "total_seconds": row["phase_seconds"]["total"],
                          "solver_cpu_seconds": sampled_cpu}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "control", "query"))
    {"freeze": freeze, "control": control, "query": query}[parser.parse_args().mode]()
