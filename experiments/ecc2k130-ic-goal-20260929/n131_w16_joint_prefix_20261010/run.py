#!/usr/bin/env sage -python
"""Build, replay, and query one joint 32-prefix W16 residual circuit."""

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
OLD = ROOT / "n131_w16_fivepair_sat_gate_20261010"
COMPACT = ROOT / "n131_w16_bdd_membership_20261010"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
FLAGS = ["--threads=1", "--xor=0", "--printsol=1", "--random=20261010",
         "--maxconfl=20000000", "--maxtime=100"]
RSS_CAP = 4 * 1024**3
TOTAL_CAP = 120


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load("joint_prefix_old_run", OLD / "fivepair_run.py")
method = load("joint_prefix_circuit", HERE / "circuit.py")


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
    return {"runner": HERE / "run.py", "circuit": HERE / "circuit.py",
            "preparation": HERE / "prepare.py", "prefixes": HERE / "prefixes.json",
            "runtime": HERE / "sage_runtime_info.json", "solver": SOLVER,
            "old_runner": OLD / "fivepair_run.py", "old_lift": OLD / "fivepair_lift.py",
            "old_control": OLD / "fivepair_control_result.json",
            "bdd": COMPACT / "bdd.py", "bdd_core": COMPACT / "core.py"}


def frozen():
    row = json.loads((HERE / "protocol.json").read_text())
    assert row["source_sha256"] == {k: sha(v) for k, v in sources().items()}
    assert row["solver_flags"] == FLAGS
    return row


def freeze():
    prefixes = json.loads((HERE / "prefixes.json").read_text())
    assert prefixes["status"] == "FROZEN_32_SIGNED_FIRST_PAIR_CHOICES"
    assert len(prefixes["prefixes"]) == 32
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    row = {"status": "FROZEN_BEFORE_W16_JOINT_PREFIX_CONTROL_AND_SEARCH",
           "candidate_id": None, "curve_id": prefixes["curve_id"],
           "target_law": prefixes["target_law"],
           "target_q": prefixes["target_q"], "prefix_count": 32,
           "target_branch_count": 128, "workers": 1,
           "total_cap_seconds": TOTAL_CAP, "rss_cap_bytes": RSS_CAP,
           "solver_flags": FLAGS,
           "source_sha256": {k: sha(v) for k, v in sources().items()}}
    save(HERE / "protocol.json", row)
    print(json.dumps({"status": row["status"], "choices": 128}))


def formula(protocol):
    prefixes = json.loads((HERE / "prefixes.json").read_text())["prefixes"]
    columns, field, curve, source_w, _ = old.experiment.run.source()
    bases = old.experiment.run.bases(field, source_w)[2:]
    rotations = old.experiment.run.prior.ROTATIONS[2:]
    circuit = old.experiment.run.base.KaratsubaCircuit(131,
                                                       old.experiment.run.LOW_TERMS)
    meta = method.build(circuit, field, bases, columns,
                        [row["target_reciprocals"] for row in prefixes],
                        [row["columns"] for row in prefixes], rotations,
                        old.experiment.run.prior.prior.old.method.frob)
    return circuit, meta, field, curve, prefixes


def profile(circuit, path):
    return {"variables": circuit.next_var - 1,
            "cnf_clauses": len(circuit.clauses),
            "native_xor_rows": len(circuit.xors),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def control():
    protocol = frozen()
    witness = json.loads((OLD / "fivepair_input.json").read_text())
    started = time.monotonic_ns()
    circuit, meta, field, curve, prefixes = formula(protocol)
    built = time.monotonic_ns()
    with tempfile.TemporaryDirectory(prefix="w16_joint_control_", dir="/private/tmp") as temp:
        path = Path(temp) / "control.xcnf"
        circuit.write(path)
        written = time.monotonic_ns()
        selected = 4 * 0 + witness["residual_target_preimage_index"]
        assert prefixes[0]["preimages"][selected % 4] == witness["residual_raw"]
        initial = {}
        for row, wires, mask in zip(meta["masks"], meta["member_wires"],
                                    witness["remaining_masks"]):
            initial.update({wire: mask >> bit & 1 for bit, wire in enumerate(row)})
            initial.update(method.bdd.assignment(meta["member_graph"], wires, mask))
        for i, wire in enumerate(meta["flags"]):
            initial[wire] = int(i == selected)
        for row, value in zip(meta["middle"], witness["remaining_middle_reciprocals"]):
            initial.update({wire: value >> bit & 1 for bit, wire in enumerate(row)})
        assert len(initial) == meta["primary_variables"] + 10*meta["membership_nodes_per_mask"]
        complete = old.experiment.run.witness_tools.complete_assignment(circuit, initial)
        checked = old.experiment.run.base.check_xcnf(path, complete)
        form = profile(circuit, path)
    lifted = old.lift.lift(witness["remaining_masks"],
                           witness["remaining_middle_reciprocals"],
                           tuple(prefixes[0]["residual_q"]), selected % 4,
                           prefixes[0]["columns"])
    assert lifted["status"] == "GROUP_LIFT_FOUND"
    assert any(curve.add(tuple(prefixes[0]["projected_sum"]),
                         tuple(solution["projected_sum"])) == tuple(protocol["target_q"])
               for solution in lifted["solutions"])
    row = {"status": "PASS_JOINT_32_PREFIX_FULL_XCNF_AND_GROUP_CONTROL",
           "candidate_id": None, "target_q": protocol["target_q"],
           "known_control_choice": selected, "formula": form,
           "full_assignment_check": checked,
           "group_lift_status": lifted["status"],
           "conditional_fixed_column_clauses": meta["conditional_fixed_column_clauses"],
           "membership_nodes_per_mask": meta["membership_nodes_per_mask"],
           "phase_ns": {"build": built - started, "write": written - built,
                        "check_and_group": time.monotonic_ns() - written},
           "source_sha256": protocol["source_sha256"]}
    save(HERE / "control.json", row)
    print(json.dumps({"status": row["status"], "formula": form}))


def query():
    protocol = frozen()
    control_row = json.loads((HERE / "control.json").read_text())
    assert control_row["status"] == "PASS_JOINT_32_PREFIX_FULL_XCNF_AND_GROUP_CONTROL"
    started = time.monotonic()
    circuit, meta, field, curve, prefixes = formula(protocol)
    with tempfile.TemporaryDirectory(prefix="w16_joint_query_", dir="/private/tmp") as temp:
        path = Path(temp) / "query.xcnf"
        circuit.write(path)
        form = profile(circuit, path)
        assert form == control_row["formula"]
        build_seconds = time.monotonic() - started
        with (HERE / "solver.stdout.txt").open("x") as out, \
             (HERE / "solver.stderr.txt").open("x") as err:
            child = subprocess.Popen([str(SOLVER), *FLAGS, str(path)],
                                     stdout=out, stderr=err, start_new_session=True)
            proc = psutil.Process(child.pid)
            parent = psutil.Process()
            peak = 0
            cpu_sample = 0.0
            stop = None
            while child.poll() is None:
                try:
                    peak = max(peak, proc.memory_info().rss + parent.memory_info().rss)
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
        group_status = None
        selected = None
        if statuses == ["s SATISFIABLE"] and model_lines:
            model = old.experiment.run.base.read_model(output, form["variables"])
            model_check = old.experiment.run.base.check_xcnf(path, model)
            choices = [i for i, wire in enumerate(meta["flags"]) if model[wire]]
            assert len(choices) == 1
            selected = choices[0]
            prefix = prefixes[selected // 4]
            masks = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                     for row in meta["masks"]]
            middle = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                      for row in meta["middle"]]
            lifted = old.lift.lift(masks, middle, tuple(prefix["residual_q"]),
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
