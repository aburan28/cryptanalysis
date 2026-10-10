#!/usr/bin/env sage -python
"""Freeze, control, and query five unrestricted W15 pairs on the public point."""

import argparse
import gzip
import hashlib
import importlib.util
import json
import subprocess
import time
from decimal import Decimal, getcontext
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_w15_coupled_sixpair_20261010"
PRIOR = HERE.parent / "n131_w15_onepair_fixed_sat_gate_20261010"
TRACE_PROOF = HERE.parent / "n131_w15_middle_trace_public_gate_20261010/trace_proof.json"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
TEMP = Path("/private/tmp/n131_w15_unrestricted_fivepair_public_20261010.xcnf")
CAP = 600.0
RSS_CAP = 4 * 1024**3
FLAGS = ["--threads=1", "--xor=0", "--printsol=1", "--random=20261010",
         "--maxconfl=20000000"]


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


def save(path, obj):
    with path.open("x") as stream:
        json.dump(obj, stream, indent=2, sort_keys=True)
        stream.write("\n")


def sources():
    return {"runner": Path(__file__), "circuit": HERE / "circuit.py",
            "group_lift": HERE / "lift.py", "input": HERE / "input.json",
            "input_producer": HERE / "prepare.py", "source_support": BASE / "support_w15.tsv",
            "base_experiment": BASE / "experiment.py", "base_circuit": BASE / "w15_circuit.py",
            "base_lift": BASE / "w15_lift.py", "prior_runner": PRIOR / "fivepair_run.py",
            "prior_circuit": PRIOR / "fivepair_circuit.py",
            "prior_control": PRIOR / "fivepair_input.json",
            "trace_proof": TRACE_PROOF,
            "checked_sage_runtime": HERE / "sage_runtime_info.json", "solver": SOLVER}


def modules():
    prior = load("unrestricted_prior_fivepair", PRIOR / "fivepair_run.py")
    prior.method = load("unrestricted_fivepair_circuit", HERE / "circuit.py")
    prior.lift = load("unrestricted_fivepair_lift", HERE / "lift.py")
    return prior


def support_mean():
    n = 540579832
    count = json.loads((BASE / "seed_sum_count.json").read_text())
    assert count["accepted_signed_pair_states_per_rotation"] == n
    r = int(count["group_order"])
    getcontext().prec = 45
    return {"signed_pair_states_per_free_slot": n, "free_pair_slots": 5,
            "subgroup_order": str(r), "group_wide_mean_before_cross_pair_filter": str(Decimal(n**5)/r)}


def frozen():
    obj = json.loads((HERE / "protocol.json").read_text())
    assert obj["status"] == "FROZEN_UNRESTRICTED_W15_FIVEPAIR_PUBLIC_GATE"
    assert obj["sources_sha256"] == {name: sha(path) for name, path in sources().items()}
    assert obj["support"] == support_mean()
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    return obj


def target_traces(prior, q):
    _, field, curve, _, _ = prior.experiment.run.source()
    raw = prior.experiment.run.prior.prior.old.target_preimages(curve, tuple(q))
    reciprocals = [field.inv(point[0]) for point in raw]
    traces = [(value & 1) ^ ((value >> 129) & 1) for value in reciprocals]
    return traces


def freeze():
    assert not TEMP.exists()
    inp = json.loads((HERE / "input.json").read_text())
    assert inp["status"] == "PASS_TARGET_INDEPENDENT_PREFIX_AND_RESIDUALS"
    assert json.loads(TRACE_PROOF.read_text())["polynomial_basis_trace_support"] == [0, 129]
    prior = modules()
    control_traces = target_traces(prior, inp["constructed_residual_target_q"])
    public_traces = target_traces(prior, inp["public_residual_target_q"])
    assert control_traces[inp["constructed_residual_preimage_index"]] == 0
    assert sorted(control_traces) == sorted(public_traces) == [0, 0, 1, 1]
    obj = {"status": "FROZEN_UNRESTRICTED_W15_FIVEPAIR_PUBLIC_GATE",
           "candidate_id": None, "curve_id": inp["curve_id"],
           "target_count": 1, "target_q": inp["public_target_q"],
           "target_law": "previously published ECC2K-130 subgroup point",
           "prefix_policy": inp["selection_rule"],
           "prefix_masks": inp["prefix_masks"], "prefix_columns": inp["prefix_columns"],
           "prefix_projected_sum": inp["prefix_projected_sum"],
           "public_residual_target_q": inp["public_residual_target_q"],
           "constructed_residual_target_q": inp["constructed_residual_target_q"],
           "public_raw_preimage_traces": public_traces,
           "constructed_raw_preimage_traces": control_traces,
           "trace_parity_bits": [0, 129],
           "support": support_mean(), "workers": 1,
           "construction_plus_search_cap_seconds": CAP,
           "rss_cap_bytes": RSS_CAP, "solver_flags": FLAGS,
           "sources_sha256": {name: sha(path) for name, path in sources().items()}}
    save(HERE / "protocol.json", obj)
    print(json.dumps({"status": obj["status"], "prefix": obj["prefix_masks"],
                      "public_traces": public_traces, "support": obj["support"]}))


def build(prior, residual_q, fixed_columns, expected_traces):
    circuit, meta, raw = prior.formula_for(tuple(residual_q), fixed_columns)
    assert meta["seed_equality_rows"] == 0
    assert len(meta["masks"]) == 10 and len(meta["middle"]) == 8
    _, field, _, _, _ = prior.experiment.run.source()
    traces = [(field.inv(point[0]) & 1) ^ ((field.inv(point[0]) >> 129) & 1)
              for point in raw]
    assert traces == expected_traces
    clauses = [f"-{meta['flags'][index]} 0" for index, value in enumerate(traces)
               if value == 1]
    for row in meta["middle"]:
        left, right = row[0], row[129]
        clauses.extend((f"-{left} {right} 0", f"{left} -{right} 0"))
    assert len(clauses) == 18
    circuit.clauses.extend(clauses)
    return circuit, meta, raw, clauses


def profile(circuit, formula):
    return {"variables": circuit.next_var-1,
            "clauses": len(circuit.clauses), "xor_rows": len(circuit.xors),
            "and_gates": circuit.and_count,
            "bytes": formula.stat().st_size, "sha256": sha(formula)}


def control():
    protocol = frozen()
    inp = json.loads((HERE / "input.json").read_text())
    prior = modules()
    started = time.monotonic()
    circuit, meta, raw, clauses = build(prior, protocol["constructed_residual_target_q"],
                                        protocol["prefix_columns"],
                                        protocol["constructed_raw_preimage_traces"])
    selected = inp["constructed_residual_preimage_index"]
    assert list(raw[selected]) == inp["constructed_residual_raw"]
    assert len(set(protocol["prefix_columns"] + [
        int(mask) for mask in inp["constructed_remaining_masks"]])) == 12
    assert not TEMP.exists()
    try:
        circuit.write(TEMP)
        initial = {}
        for row, mask in zip(meta["masks"], inp["constructed_remaining_masks"]):
            initial.update({wire: mask >> bit & 1 for bit, wire in enumerate(row)})
        for index, wire in enumerate(meta["flags"]):
            initial[wire] = int(index == selected)
        for row, value in zip(meta["middle"], inp["constructed_remaining_middle_reciprocals"]):
            initial.update({wire: value >> bit & 1 for bit, wire in enumerate(row)})
        assert len(initial) == meta["primary_variables"]
        assignment = prior.experiment.run.witness_tools.complete_assignment(circuit, initial)
        check = prior.experiment.run.base.check_xcnf(TEMP, assignment)
        group = prior.lift.lift(inp["constructed_remaining_masks"],
                                inp["constructed_remaining_middle_reciprocals"],
                                tuple(protocol["constructed_residual_target_q"]),
                                selected, protocol["prefix_columns"])
        assert group["status"] == "GROUP_LIFT_FOUND"
        assert any(item["raw_sum"] == inp["constructed_residual_raw"]
                   for item in group["solutions"])
        receipt = {"status": "PASS_UNRESTRICTED_FIVEPAIR_CONSTRUCTED_CONTROL",
                   "candidate_id": None, "target_count": 0,
                   "target_q": protocol["constructed_residual_target_q"],
                   "prefix_masks": protocol["prefix_masks"], "added_trace_clauses": clauses,
                   "formula": profile(circuit, TEMP), "xcnf_check": check,
                   "group_lift_status": group["status"],
                   "elapsed_seconds": time.monotonic()-started,
                   "protocol_sha256": sha(HERE / "protocol.json")}
        save(HERE / "control.json", receipt)
        print(json.dumps({"status": receipt["status"], "formula": receipt["formula"]}))
    finally:
        TEMP.unlink(missing_ok=True)


def query():
    protocol = frozen()
    control_result = json.loads((HERE / "control.json").read_text())
    assert control_result["status"] == "PASS_UNRESTRICTED_FIVEPAIR_CONSTRUCTED_CONTROL"
    assert control_result["protocol_sha256"] == sha(HERE / "protocol.json")
    assert not TEMP.exists()
    prior = modules()
    inp = json.loads((HERE / "input.json").read_text())
    _, _, curve, _, _ = prior.experiment.run.source()
    started = time.monotonic()
    residual = curve.add(tuple(protocol["target_q"]),
                         curve.neg(tuple(protocol["prefix_projected_sum"])))
    assert list(residual) == protocol["public_residual_target_q"]
    circuit, meta, raw, clauses = build(prior, residual,
                                        protocol["prefix_columns"],
                                        protocol["public_raw_preimage_traces"])
    circuit.write(TEMP)
    build_seconds = time.monotonic()-started
    form = profile(circuit, TEMP)
    assert form["variables"] == control_result["formula"]["variables"]
    assert form["clauses"] == control_result["formula"]["clauses"]
    assert form["xor_rows"] == control_result["formula"]["xor_rows"]
    parent = psutil.Process()
    peak = parent.memory_info().rss
    remaining = CAP-build_seconds-8
    assert remaining > 0 and peak < RSS_CAP
    command = [str(SOLVER), *FLAGS, f"--maxtime={max(1,int(remaining)-2)}", str(TEMP)]
    stdout_path = HERE / "solver.stdout.txt"
    stderr_path = HERE / "solver.stderr.txt"
    with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                 start_new_session=True)
        process = psutil.Process(child.pid)
        solver_started = time.monotonic()
        stop = None
        while child.poll() is None:
            try:
                peak = max(peak, parent.memory_info().rss + process.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            if peak >= RSS_CAP:
                stop = "RSS_CAP"
            elif time.monotonic()-started >= CAP-1:
                stop = "QUERY_WALL_CAP"
            elif time.monotonic()-solver_started >= remaining:
                stop = "SOLVER_WALL_CAP"
            if stop:
                child.terminate()
                break
            time.sleep(.1)
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
            stop = (stop or "DRAIN_TIMEOUT")+"_KILLED"
    solver_seconds = time.monotonic()-solver_started
    output = stdout_path.read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in output.splitlines())
    check = group = None
    if statuses == ["s SATISFIABLE"] and model_lines:
        model = prior.experiment.run.base.read_model(output, form["variables"])
        check = prior.experiment.run.base.check_xcnf(TEMP, model)
        masks = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                 for row in meta["masks"]]
        middle = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                  for row in meta["middle"]]
        selected = [index for index, wire in enumerate(meta["flags"]) if model[wire]]
        assert len(selected) == 1 and protocol["public_raw_preimage_traces"][selected[0]] == 0
        group = prior.lift.lift(masks, middle, tuple(residual), selected[0],
                                protocol["prefix_columns"])
        save(HERE / "group_lift.json", group)
        status = "GROUP_RELATION_PENDING_INDEPENDENT_SAGE" if group["status"] == "GROUP_LIFT_FOUND" else "SAT_NO_GROUP_LIFT"
    elif stop == "RSS_CAP":
        status = "OOM"
    elif stop in ("QUERY_WALL_CAP", "SOLVER_WALL_CAP") or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "UNSAT_FORMULA"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    archive = HERE / "system.xcnf.gz"
    with TEMP.open("rb") as source, gzip.open(archive, "xb", compresslevel=6) as dest:
        for block in iter(lambda: source.read(1 << 20), b""):
            dest.write(block)
    TEMP.unlink()
    result = {"status": status, "candidate_id": None,
              "curve_id": protocol["curve_id"], "target_count": 1,
              "target_q": protocol["target_q"], "residual_q": list(residual),
              "prefix_masks": protocol["prefix_masks"],
              "prefix_columns": protocol["prefix_columns"],
              "raw_target_preimages": [list(point) for point in raw],
              "added_trace_clauses": clauses,
              "formula": form, "formula_gzip_sha256": sha(archive),
              "solver_command": command, "solver_status_lines": statuses,
              "model_lines": model_lines, "solver_exit_code": child.returncode,
              "stop_reason": stop, "producer_xcnf_check": check,
              "group_lift_status": group["status"] if group else None,
              "phase_seconds": {"target_formula": build_seconds,
                                "solver": solver_seconds,
                                "construction_plus_search": build_seconds+solver_seconds},
              "sampled_peak_combined_rss_bytes": peak,
              "sha256": {"protocol": sha(HERE / "protocol.json"),
                         "control": sha(HERE / "control.json"),
                         "stdout": sha(stdout_path), "stderr": sha(stderr_path),
                         "formula_gzip": sha(archive)}}
    save(HERE / "result.json", result)
    print(json.dumps({"status": status, "construction_plus_search_seconds": build_seconds+solver_seconds,
                      "peak_rss_bytes": peak, "formula_sha256": form["sha256"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "control", "query"))
    {"freeze": freeze, "control": control, "query": query}[parser.parse_args().mode]()
