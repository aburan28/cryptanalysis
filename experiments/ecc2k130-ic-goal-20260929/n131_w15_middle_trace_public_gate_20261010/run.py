#!/usr/bin/env sage -python
"""Freeze and measure trace parity propagation through all W15 middle words."""

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
COUNTS = HERE.parent / "n131_w15_cross_block_seed_offset_20261010/signed_seed_counts.tsv"
CONTROL = HERE.parent / "n131_w14_coupled_sixpair_sat_20261010/control.json"
TRACE = HERE.parent / "n131_w15_one_seed_public_gate_20261010/trace_result.json"
TRACE_PROOF = HERE / "trace_proof.json"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
SEED = 13686
CAP = 600.0
RSS_CAP = 4 * 1024**3
FLAGS = ["--threads=1", "--xor=0", "--printsol=1", "--random=20261010",
         "--maxconfl=20000000"]
TEMP = Path("/private/tmp/n131_w15_middle_trace_public_20261010.xcnf")


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
    return {"runner": Path(__file__), "experiment": BASE / "experiment.py",
            "circuit": BASE / "w15_circuit.py", "support": BASE / "support_w15.tsv",
            "base_protocol": BASE / "protocol.json", "base_control": BASE / "control_result.json",
            "base_public_protocol": BASE / "query_protocol.json",
            "base_public_formula": BASE / "public_query/system.xcnf.gz",
            "seed_counts": COUNTS, "control_fixture": CONTROL,
            "public_trace_audit": TRACE, "trace_parity_proof": TRACE_PROOF,
            "checked_sage_runtime": HERE / "sage_runtime_info.json", "solver": SOLVER}


def counts():
    values = {int(a): int(b) for a, b in
              (line.split() for line in COUNTS.read_text().splitlines())}
    assert len(values) == 32767 and SEED in values
    count = json.loads((BASE / "seed_sum_count.json").read_text())
    n = sum(values.values())
    same = sum(x*x for x in values.values())
    assert n == count["accepted_signed_pair_states_per_rotation"]
    assert same == count["same_seed_two_pair_states"]
    r = int(count["group_order"])
    getcontext().prec = 45
    family = sorted(seed for seed in values if seed >> 3 == SEED >> 3)
    assert family == list(range(13680, 13688))
    family_states = sum(values[seed]**2 for seed in family)
    mean = Decimal(n*n*same*family_states) / r
    return {"seed_family": family, "signed_pair_states_for_control_seed": values[SEED],
            "signed_pair_states_total": n, "same_seed_block_states_total": same,
            "seed_family_block_states": family_states,
            "group_order": str(r),
            "group_wide_mean_before_cross_pair_column_filter": str(mean)}


def frozen():
    obj = json.loads((HERE / "protocol.json").read_text())
    assert obj["status"] == "FROZEN_W15_SEED8_MIDDLETRACE_PUBLIC_GATE"
    assert obj["sources_sha256"] == {key: sha(path) for key, path in sources().items()}
    assert obj["support"] == counts()
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    assert json.loads(TRACE.read_text())["admissible_target_preimage_indices"] == [0, 2]
    assert json.loads(TRACE_PROOF.read_text())["polynomial_basis_trace_support"] == [0, 129]
    return obj


def freeze():
    assert not TEMP.exists()
    base = json.loads((BASE / "query_protocol.json").read_text())
    assert json.loads(TRACE.read_text())["target_q"] == base["target_q"]
    assert json.loads(TRACE_PROOF.read_text())["status"] == "PASS_EXACT_N131_TRACE_PARITY_AND_CONSTRUCTED_MIDDLES"
    obj = {"status": "FROZEN_W15_SEED8_MIDDLETRACE_PUBLIC_GATE", "candidate_id": None,
           "curve_id": base["curve_id"], "target_q": base["target_q"],
           "constructed_q": json.loads(CONTROL.read_text())["target_q"],
           "target_count": 1, "seed_block": [4, 5, 6, 7],
           "seed_pair": [4, 5], "support": counts(),
           "admissible_target_preimage_indices": [0, 2],
           "middle_trace_parity_bit_indices": [0, 129],
           "workers": 1, "construction_plus_search_cap_seconds": CAP,
           "rss_cap_bytes": RSS_CAP, "solver_flags": FLAGS,
           "sources_sha256": {key: sha(path) for key, path in sources().items()}}
    save(HERE / "protocol.json", obj)
    print(json.dumps({"status": obj["status"], "support": obj["support"]}))


def pin_seed_and_trace(circuit, meta):
    """Fix the seed family and expose exact trace parity for every middle."""
    a, b = meta["masks"][4], meta["masks"][5]
    clauses = []
    for bit in range(3, 15):
        left, right = a[bit], b[bit]
        if SEED >> bit & 1:
            clauses.extend((f"{left} {right} 0", f"-{left} -{right} 0"))
        else:
            clauses.extend((f"-{left} {right} 0", f"{left} -{right} 0"))
    clauses.extend((f"-{meta['flags'][1]} 0", f"-{meta['flags'][3]} 0"))
    for row in meta["middle"]:
        left, right = row[0], row[129]
        clauses.extend((f"-{left} {right} 0", f"{left} -{right} 0"))
    assert len(clauses) == 46
    circuit.clauses.extend(clauses)
    return clauses


def build(target):
    experiment = load("w15_one_seed_experiment", BASE / "experiment.py")
    circuit, meta, lifts = experiment.run.formula_for(tuple(target))
    assert [row[0] for row in meta["masks"]] == list(range(1, 181, 15))
    clauses = pin_seed_and_trace(circuit, meta)
    return experiment, circuit, meta, lifts, clauses


def control():
    protocol = frozen()
    fixture = json.loads(CONTROL.read_text())
    assert fixture["masks"][4] ^ fixture["masks"][5] == SEED
    assert fixture["masks"][6] ^ fixture["masks"][7] == SEED
    started = time.monotonic()
    experiment, circuit, meta, lifts, clauses = build(protocol["constructed_q"])
    assert list(lifts[fixture["target_preimage_index"]]) == fixture["raw_sum"]
    assert circuit.next_var - 1 == 121787
    assert len(circuit.clauses) == 436771 and len(circuit.xors) == 43272
    assert not TEMP.exists()
    try:
        circuit.write(TEMP)
        initial = {}
        for row, mask in zip(meta["masks"], fixture["masks"]):
            initial.update({wire: mask >> bit & 1 for bit, wire in enumerate(row)})
        for index, wire in enumerate(meta["flags"]):
            initial[wire] = int(index == fixture["target_preimage_index"])
        for row, value in zip(meta["middle"], fixture["middle_reciprocals"]):
            initial.update({wire: value >> bit & 1 for bit, wire in enumerate(row)})
        assignment = experiment.run.witness_tools.complete_assignment(circuit, initial)
        check = experiment.run.base.check_xcnf(TEMP, assignment)
        receipt = {"status": "PASS_SEED8_MIDDLETRACE_CONSTRUCTED_WITNESS",
                   "target_q": protocol["constructed_q"], "control_seed": SEED,
                   "pin_clauses": clauses, "formula_sha256": sha(TEMP),
                   "xcnf_check": check, "elapsed_seconds": time.monotonic() - started,
                   "protocol_sha256": sha(HERE / "protocol.json")}
        save(HERE / "control.json", receipt)
        print(json.dumps(receipt))
    finally:
        TEMP.unlink(missing_ok=True)


def query():
    protocol = frozen()
    control_result = json.loads((HERE / "control.json").read_text())
    assert control_result["status"] == "PASS_SEED8_MIDDLETRACE_CONSTRUCTED_WITNESS"
    assert control_result["protocol_sha256"] == sha(HERE / "protocol.json")
    assert not TEMP.exists()
    started = time.monotonic()
    experiment, circuit, meta, lifts, clauses = build(protocol["target_q"])
    circuit.write(TEMP)
    build_seconds = time.monotonic() - started
    profile = experiment.metadata(circuit, meta, TEMP)
    assert profile["clauses"] == 436771 and profile["xor_rows"] == 43279
    parent = psutil.Process()
    peak = parent.memory_info().rss
    remaining = CAP - build_seconds - 8
    assert remaining > 0 and peak < RSS_CAP
    command = [str(SOLVER), *FLAGS, f"--maxtime={max(1, int(remaining)-2)}", str(TEMP)]
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
            elif time.monotonic() - started >= CAP - 1:
                stop = "QUERY_WALL_CAP"
            elif time.monotonic() - solver_started >= remaining:
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
            stop = (stop or "DRAIN_TIMEOUT") + "_KILLED"
    solver_seconds = time.monotonic() - solver_started
    output = stdout_path.read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in output.splitlines())
    check = group = None
    if statuses == ["s SATISFIABLE"] and model_lines:
        model = experiment.run.base.read_model(output, profile["variables"])
        check = experiment.run.base.check_xcnf(TEMP, model)
        masks = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                 for row in meta["masks"]]
        middle = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                  for row in meta["middle"]]
        selected = [index for index, wire in enumerate(meta["flags"]) if model[wire]]
        assert len(selected) == 1 and selected[0] in (0, 2)
        assert (masks[4] ^ masks[5]) >> 3 == SEED >> 3
        group = experiment.lift.lift(masks, middle, tuple(protocol["target_q"]), selected[0])
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
    result = {"status": status, "candidate_id": None, "target_q": protocol["target_q"],
              "seed_family": protocol["support"]["seed_family"],
              "admissible_target_preimage_indices": [0, 2],
              "middle_trace_parity_bit_indices": [0, 129],
              "target_count": 1, "formula": profile,
              "formula_gzip_sha256": sha(archive), "pin_clauses": clauses,
              "solver_command": command, "solver_status_lines": statuses,
              "model_lines": model_lines, "solver_exit_code": child.returncode,
              "stop_reason": stop, "producer_xcnf_check": check,
              "group_lift_status": group["status"] if group else None,
              "phase_seconds": {"target_formula": build_seconds, "solver": solver_seconds,
                                "construction_plus_search": build_seconds+solver_seconds},
              "sampled_peak_combined_rss_bytes": peak,
              "sha256": {"protocol": sha(HERE / "protocol.json"),
                         "control": sha(HERE / "control.json"),
                         "stdout": sha(stdout_path), "stderr": sha(stderr_path),
                         "formula_gzip": sha(archive)}}
    save(HERE / "result.json", result)
    print(json.dumps({"status": status, "construction_plus_search_seconds": build_seconds+solver_seconds,
                      "peak_rss_bytes": peak, "formula_sha256": profile["sha256"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "control", "query"))
    mode = parser.parse_args().mode
    {"freeze": freeze, "control": control, "query": query}[mode]()
