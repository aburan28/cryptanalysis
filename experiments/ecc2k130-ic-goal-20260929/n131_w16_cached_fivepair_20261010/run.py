#!/usr/bin/env sage -python
"""Freeze, precompute, and query a reusable W16 five-pair circuit core."""

import argparse
import gzip
import hashlib
import importlib.util
import json
import pickle
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "n131_w16_fivepair_sat_gate_20261010"
WIDTH = HERE.parent / "n131_w16_w18_sixpair_width_gate_20261010"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
CORE = HERE / "core.pickle.gz"
TEMP = Path("/private/tmp/n131_w16_cached_fivepair_20261010")
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


old = load("cached_w16_previous", OLD / "fivepair_run.py")
method = load("cached_w16_core", HERE / "core.py")


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def save(name, row):
    with (HERE / name).open("x") as output:
        json.dump(row, output, sort_keys=True, indent=2)
        output.write("\n")


def sources():
    return {"runner": HERE / "run.py", "core": HERE / "core.py",
            "input": OLD / "fivepair_input.json",
            "prior_runner": OLD / "fivepair_run.py",
            "prior_circuit": OLD / "fivepair_circuit.py",
            "prior_lift": OLD / "fivepair_lift.py",
            "prior_query": OLD / "query_v2_result.json",
            "width_result": WIDTH / "result.json",
            "width_audit": WIDTH / "audit_result.json",
            "width_support": WIDTH / "support_w16.tsv",
            "runtime": HERE / "sage_runtime_info.json", "solver": SOLVER}


def input_record():
    row = json.loads((OLD / "fivepair_input.json").read_text())
    assert row["status"] == "PASS_EXACT_CONSTRUCTED_W15_FIVE_PAIR_RESIDUAL"
    return row


def freeze():
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    row = input_record()
    protocol = {"status": "FROZEN_BEFORE_W16_CACHED_CORE",
                "candidate_id": None, "curve_id": row["curve_id"],
                "target_law": "constructed signed-prefix residual control",
                "target_q": row["residual_target_q"],
                "fixed_first_pair_columns": row["first_pair_columns"],
                "workers": 1, "wall_cap_seconds": WALL_CAP,
                "parent_safe_stop_seconds": SAFE_STOP,
                "rss_cap_bytes": RSS_CAP, "solver_flags": FLAGS,
                "source_sha256": {name: sha(path) for name, path in sources().items()}}
    save("protocol.json", protocol)
    print(json.dumps({"status": protocol["status"]}))


def protocol():
    row = json.loads((HERE / "protocol.json").read_text())
    assert row["status"] == "FROZEN_BEFORE_W16_CACHED_CORE"
    assert row["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    return row


def load_core():
    receipt = json.loads((HERE / "core_result.json").read_text())
    assert receipt["status"] == "PASS_REUSABLE_W16_SOURCE_CORE"
    assert receipt["core_gzip_sha256"] == sha(CORE)
    with gzip.open(CORE, "rb") as stream:
        circuit, state = pickle.load(stream)
        assert not stream.read(1)
    assert circuit.next_var-1 == receipt["variables"]
    assert len(circuit.clauses) == receipt["cnf_clauses"]
    assert len(circuit.xors) == receipt["native_xor_rows"]
    return circuit, state


def precompute():
    frozen = protocol()
    assert not CORE.exists()
    started = time.monotonic_ns()
    columns, field, _, basis, _ = old.experiment.run.source()
    bases = old.experiment.run.bases(field, basis)[2:]
    rotations = old.experiment.run.prior.ROTATIONS[2:]
    circuit = old.experiment.run.base.KaratsubaCircuit(131, old.experiment.run.LOW_TERMS)
    state = method.prepare(circuit, field, bases, columns, rotations,
                           old.experiment.run.prior.prior.old.method.frob)
    built = time.monotonic_ns()-started
    with gzip.open(CORE, "xb", compresslevel=6) as stream:
        pickle.dump((circuit, state), stream, protocol=5)
    wall = time.monotonic_ns()-started
    rss = psutil.Process().memory_info().rss
    status = "PASS_REUSABLE_W16_SOURCE_CORE"
    if wall > WALL_CAP*10**9:
        status = "CENSORED_TIME"
    if rss >= RSS_CAP:
        status = "CENSORED_MEMORY"
    receipt = {"status": status, "candidate_id": None,
               "core_gzip_sha256": sha(CORE), "core_bytes": CORE.stat().st_size,
               "variables": circuit.next_var-1,
               "cnf_clauses": len(circuit.clauses),
               "native_xor_rows": len(circuit.xors),
               "bilinear_pair_ands": state["bilinear_pair_ands"],
               "build_ns": built, "build_and_archive_ns": wall,
               "rss_bytes_at_end": rss, "protocol_sha256": sha(HERE / "protocol.json"),
               "source_sha256": frozen["source_sha256"]}
    save("core_result.json", receipt)
    print(json.dumps({"status": status, "build_seconds": built/1e9,
                      "core_bytes": receipt["core_bytes"]}))
    if status != "PASS_REUSABLE_W16_SOURCE_CORE":
        raise SystemExit(1)


def formula_for(target_q, fixed_columns):
    circuit, state = load_core()
    _, field, curve, _, _ = old.experiment.run.source()
    started = time.monotonic_ns()
    raw_targets = old.experiment.run.prior.prior.old.target_preimages(curve, target_q)
    target_reciprocals = [field.inv(point[0]) for point in raw_targets]
    meta = method.finish(circuit, field, state, target_reciprocals, fixed_columns)
    return circuit, meta, raw_targets, time.monotonic_ns()-started


def profile(circuit, formula):
    return {"variables": circuit.next_var-1,
            "cnf_clauses": len(circuit.clauses),
            "native_xor_rows": len(circuit.xors),
            "bytes": formula.stat().st_size, "sha256": sha(formula)}


def control():
    frozen = protocol()
    witness = input_record()
    started = time.monotonic_ns()
    circuit, meta, raw_targets, completion_ns = formula_for(
        tuple(frozen["target_q"]), frozen["fixed_first_pair_columns"])
    formula = HERE / "control.xcnf"
    circuit.write(formula)
    formed = time.monotonic_ns()-started
    assert list(raw_targets[witness["residual_target_preimage_index"]]) == witness[
        "residual_raw"]
    initial = {}
    for row, mask in zip(meta["masks"], witness["remaining_masks"]):
        initial.update({wire: mask >> bit & 1 for bit, wire in enumerate(row)})
    for index, wire in enumerate(meta["flags"]):
        initial[wire] = int(index == witness["residual_target_preimage_index"])
    for row, value in zip(meta["middle"], witness["remaining_middle_reciprocals"]):
        initial.update({wire: value >> bit & 1 for bit, wire in enumerate(row)})
    assert len(initial) == meta["primary_variables"]
    assignment = old.experiment.run.witness_tools.complete_assignment(circuit, initial)
    check = old.experiment.run.base.check_xcnf(formula, assignment)
    lifted = old.lift.lift(witness["remaining_masks"],
                           witness["remaining_middle_reciprocals"],
                           tuple(frozen["target_q"]),
                           witness["residual_target_preimage_index"],
                           frozen["fixed_first_pair_columns"])
    assert lifted["status"] == "GROUP_LIFT_FOUND"
    save("control_group_lift.json", lifted)
    form = profile(circuit, formula)
    with formula.open("rb") as inp, gzip.open(HERE / "control.xcnf.gz", "xb") as out:
        for block in iter(lambda: inp.read(1 << 20), b""):
            out.write(block)
    formula.unlink()
    total = time.monotonic_ns()-started
    receipt = {"status": "PASS_CACHED_W16_FULL_XCNF_AND_GROUP_CONTROL",
               "candidate_id": None, "formula": {**form,
                                                  "gzip_sha256": sha(HERE / "control.xcnf.gz")},
               "full_assignment_check": check,
               "group_lift_status": lifted["status"],
               "phase_ns": {"target_completion": completion_ns,
                            "load_complete_write": formed,
                            "control_total": total},
               "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                                 "core_result": sha(HERE / "core_result.json"),
                                 "group_lift": sha(HERE / "control_group_lift.json")}}
    save("control_result.json", receipt)
    print(json.dumps({"status": receipt["status"], "formula": form,
                      "target_completion_ms": completion_ns/1e6}))


def freeze_query():
    frozen = protocol()
    control = json.loads((HERE / "control_result.json").read_text())
    assert control["status"] == "PASS_CACHED_W16_FULL_XCNF_AND_GROUP_CONTROL"
    query_protocol = {"status": "FROZEN_BEFORE_CACHED_W16_QUERY",
                      "target_q": frozen["target_q"],
                      "fixed_first_pair_columns": frozen["fixed_first_pair_columns"],
                      "workers": 1, "wall_cap_seconds": WALL_CAP,
                      "parent_safe_stop_seconds": SAFE_STOP,
                      "rss_cap_bytes": RSS_CAP, "solver_flags": FLAGS,
                      "source_sha256": {**frozen["source_sha256"],
                          "protocol": sha(HERE / "protocol.json"),
                          "core": sha(CORE),
                          "core_result": sha(HERE / "core_result.json"),
                          "control_result": sha(HERE / "control_result.json"),
                          "control_formula": sha(HERE / "control.xcnf.gz")}}
    save("query_protocol.json", query_protocol)
    print(json.dumps({"status": query_protocol["status"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "precompute", "control", "freeze_query"))
    {"freeze": freeze, "precompute": precompute, "control": control,
     "freeze_query": freeze_query}[parser.parse_args().mode]()
