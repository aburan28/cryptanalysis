#!/usr/bin/env sage -python
"""Full-control and bounded search for canonical W16 joint-prefix pairs."""

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
JOINT = ROOT / "n131_w16_joint_prefix_20261010"
OLD = ROOT / "n131_w16_fivepair_sat_gate_20261010"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
FLAGS = ["--threads=1", "--xor=0", "--printsol=1", "--random=20261010",
         "--maxconfl=20000000", "--maxtime=570"]
TOTAL_CAP = 600
RSS_CAP = 4 * 1024**3


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


joint = load("canonical_prior_joint", JOINT / "run.py")
canonical = load("canonical_pairs", HERE / "canonical.py")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def save(path, row):
    with Path(path).open("x") as stream:
        json.dump(row, stream, indent=2, sort_keys=True)
        stream.write("\n")


def sources():
    return {"runner": HERE / "run.py", "canonical": HERE / "canonical.py",
            "joint_runner": JOINT / "run.py", "joint_circuit": JOINT / "circuit.py",
            "joint_protocol": JOINT / "protocol.json",
            "joint_control": JOINT / "control.json",
            "prefixes": JOINT / "prefixes.json",
            "original_witness": OLD / "fivepair_input.json",
            "solver": SOLVER, "runtime": HERE / "sage_runtime_info.json"}


def frozen():
    row = json.loads((HERE / "protocol.json").read_text())
    assert row["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    assert row["solver_flags"] == FLAGS
    return row


def freeze():
    prior = joint.frozen()
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    row = {"status": "FROZEN_BEFORE_CANONICAL_W16_JOINT_CONTROL_AND_SEARCH",
           "candidate_id": None, "curve_id": prior["curve_id"],
           "target_law": prior["target_law"], "target_q": prior["target_q"],
           "prefix_count": 32, "target_branch_count": 128,
           "pair_swap_symmetry_factor": 32, "workers": 1,
           "total_cap_seconds": TOTAL_CAP, "rss_cap_bytes": RSS_CAP,
           "solver_flags": FLAGS,
           "source_sha256": {name: sha(path) for name, path in sources().items()}}
    save(HERE / "protocol.json", row)
    print(json.dumps({"status": row["status"], "pair_symmetry_factor": 32}))


def formula():
    prior = joint.frozen()
    circuit, meta, field, curve, prefixes = joint.formula(prior)
    steps = canonical.add_pair_order(circuit, meta["masks"])
    return circuit, meta, steps, field, curve, prefixes


def profile(circuit, path):
    return {"variables": circuit.next_var - 1,
            "cnf_clauses": len(circuit.clauses),
            "native_xor_rows": len(circuit.xors),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def control():
    protocol = frozen()
    witness = json.loads((OLD / "fivepair_input.json").read_text())
    started = time.monotonic_ns()
    circuit, meta, steps, field, curve, prefixes = formula()
    built = time.monotonic_ns()
    masks = canonical.canonical_masks(witness["remaining_masks"])
    assert all(masks[i] < masks[i+1] for i in range(0, 10, 2))
    with tempfile.TemporaryDirectory(prefix="w16_canonical_control_", dir="/private/tmp") as temp:
        path = Path(temp) / "control.xcnf"
        circuit.write(path)
        written = time.monotonic_ns()
        initial = {}
        for row, wires, mask in zip(meta["masks"], meta["member_wires"], masks):
            initial.update({wire: mask >> bit & 1 for bit, wire in enumerate(row)})
            initial.update(joint.method.bdd.assignment(meta["member_graph"], wires, mask))
        selected = witness["residual_target_preimage_index"]
        for i, wire in enumerate(meta["flags"]):
            initial[wire] = int(i == selected)
        for row, value in zip(meta["middle"], witness["remaining_middle_reciprocals"]):
            initial.update({wire: value >> bit & 1 for bit, wire in enumerate(row)})
        initial.update(canonical.assignment(masks, steps))
        completed = joint.old.experiment.run.witness_tools.complete_assignment(circuit, initial)
        check = joint.old.experiment.run.base.check_xcnf(path, completed)
        form = profile(circuit, path)
    prefix = prefixes[0]
    lifted = joint.old.lift.lift(masks, witness["remaining_middle_reciprocals"],
                                 tuple(prefix["residual_q"]), selected,
                                 prefix["columns"])
    assert lifted["status"] == "GROUP_LIFT_FOUND"
    assert any(curve.add(tuple(prefix["projected_sum"]),
                         tuple(sol["projected_sum"])) == tuple(protocol["target_q"])
               for sol in lifted["solutions"])
    row = {"status": "PASS_CANONICAL_JOINT_FULL_XCNF_AND_GROUP_CONTROL",
           "candidate_id": None, "target_q": protocol["target_q"],
           "canonical_control_masks": masks, "control_choice": selected,
           "pair_order_steps": sum(map(len, steps)),
           "formula": form, "full_assignment_check": check,
           "group_lift_status": lifted["status"],
           "phase_ns": {"build": built - started, "write": written - built,
                        "check_and_group": time.monotonic_ns() - written},
           "source_sha256": protocol["source_sha256"]}
    save(HERE / "control.json", row)
    print(json.dumps({"status": row["status"], "formula": form}))


def query():
    protocol = frozen()
    control_row = json.loads((HERE / "control.json").read_text())
    assert control_row["status"] == "PASS_CANONICAL_JOINT_FULL_XCNF_AND_GROUP_CONTROL"
    started = time.monotonic()
    circuit, meta, steps, field, curve, prefixes = formula()
    with tempfile.TemporaryDirectory(prefix="w16_canonical_query_", dir="/private/tmp") as temp:
        path = Path(temp) / "query.xcnf"
        circuit.write(path)
        form = profile(circuit, path)
        assert form == control_row["formula"]
        build_seconds = time.monotonic() - started
        with (HERE / "solver.stdout.txt").open("x") as out, \
             (HERE / "solver.stderr.txt").open("x") as err:
            child = subprocess.Popen([str(SOLVER), *FLAGS, str(path)],
                                     stdout=out, stderr=err, start_new_session=True)
            parent = psutil.Process()
            proc = psutil.Process(child.pid)
            peak = 0
            cpu_sample = 0.0
            stop = None
            while child.poll() is None:
                try:
                    peak = max(peak, parent.memory_info().rss + proc.memory_info().rss)
                    cpu = proc.cpu_times()
                    cpu_sample = max(cpu_sample, cpu.user + cpu.system)
                except psutil.NoSuchProcess:
                    pass
                if peak >= RSS_CAP:
                    stop = "RSS_CAP"
                elif time.monotonic() - started >= TOTAL_CAP - 5:
                    stop = "SAFE_WALL_STOP"
                if stop:
                    child.terminate()
                    break
                time.sleep(.1)
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
        group_status = None
        selected = None
        if statuses == ["s SATISFIABLE"] and model_lines:
            model = joint.old.experiment.run.base.read_model(output, form["variables"])
            model_check = joint.old.experiment.run.base.check_xcnf(path, model)
            choices = [i for i, wire in enumerate(meta["flags"]) if model[wire]]
            assert len(choices) == 1
            selected = choices[0]
            prefix = prefixes[selected // 4]
            masks = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                     for row in meta["masks"]]
            assert all(masks[i] < masks[i+1] for i in range(0, 10, 2))
            middle = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                      for row in meta["middle"]]
            lifted = joint.old.lift.lift(masks, middle,
                                         tuple(prefix["residual_q"]),
                                         selected % 4, prefix["columns"])
            group_status = lifted["status"]
            if group_status == "GROUP_LIFT_FOUND":
                assert any(curve.add(tuple(prefix["projected_sum"]),
                                     tuple(sol["projected_sum"])) == tuple(protocol["target_q"])
                           for sol in lifted["solutions"])
            save(HERE / "query_group_lift.json", lifted)
            status = "GROUP_LIFT_FOUND" if group_status == "GROUP_LIFT_FOUND" else "SAT_NO_GROUP_LIFT"
        elif stop == "RSS_CAP":
            status = "OOM"
        elif stop == "SAFE_WALL_STOP" or "s INDETERMINATE" in statuses:
            status = "CENSORED_TIME"
        elif statuses == ["s UNSATISFIABLE"]:
            status = "PRODUCER_FAILURE_UNSAT_CONSTRUCTED_CONTROL"
        else:
            status = "PRODUCER_OR_SOLVER_FAILURE"
        phases = {"build": build_seconds,
                  "search": time.monotonic() - started - build_seconds,
                  "total": time.monotonic() - started}
        row = {"status": status, "candidate_id": None,
               "target_q": protocol["target_q"], "formula": form,
               "selected_choice": selected, "solver_flags": FLAGS,
               "solver_status_lines": statuses, "model_lines": model_lines,
               "model_check": model_check, "group_lift_status": group_status,
               "stop_reason": stop, "solver_exit_code": child.returncode,
               "phase_seconds": phases, "sampled_peak_combined_rss_bytes": peak,
               "sampled_solver_cpu_seconds": cpu_sample,
               "source_sha256": protocol["source_sha256"],
               "output_sha256": {"stdout": sha(HERE / "solver.stdout.txt"),
                                 "stderr": sha(HERE / "solver.stderr.txt")}}
        save(HERE / "query.json", row)
        print(json.dumps({"status": status, "phase_seconds": phases,
                          "solver_cpu_seconds": cpu_sample}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "control", "query"))
    {"freeze": freeze, "control": control, "query": query}[parser.parse_args().mode]()
