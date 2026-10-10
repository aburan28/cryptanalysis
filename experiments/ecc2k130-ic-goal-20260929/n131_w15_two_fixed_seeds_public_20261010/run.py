#!/usr/bin/env sage -python
"""Frozen W15 public gate with two independent fixed-seed pairs."""

import argparse
import gzip
import hashlib
import importlib.util
import json
import subprocess
import time
import traceback
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_w15_coupled_sixpair_20261010"
W14 = HERE.parent / "n131_w14_coupled_sixpair_sat_20261010"
TRACE = HERE.parent / "n131_w15_middle_trace_public_gate_20261010" / "trace_proof.json"
OUT = Path("/private/tmp/n131_w15_two_fixed_seeds_gate_20261010")
RAW = Path("/private/tmp/n131_w15_two_fixed_seeds_public_20261010.xcnf")
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
CAP = 600.0
RSS_CAP = 4*1024**3
FLAGS = ["--threads=1", "--xor=0", "--printsol=1",
         "--random=20261010", "--maxconfl=20000000"]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load("two_fixed_seeds_base_experiment", BASE / "experiment.py")
base.run.method = load("two_fixed_seeds_circuit", HERE / "circuit.py")
lift = load("two_fixed_seeds_lift", HERE / "lift.py")


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
            "lift": HERE / "lift.py", "support_count": HERE / "support_count.json",
            "support_audit": HERE / "support_audit.json",
            "identity": HERE / "identity.json",
            "support_count_script": HERE / "support_count.py",
            "support_audit_script": HERE / "support_audit.py",
            "identity_script": HERE / "identity.py",
            "runtime": HERE / "sage_runtime_info.json",
            "base_experiment": BASE / "experiment.py",
            "base_circuit": BASE / "w15_circuit.py",
            "base_lift": BASE / "w15_lift.py",
            "source_support": BASE / "support_w15.tsv",
            "source_group_audit": BASE / "sage_group_audit.json",
            "constructed_input": W14 / "control.json",
            "published_input": BASE / "query_protocol.json",
            "trace_proof": TRACE, "solver": SOLVER}


def frozen():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_TWO_FIXED_SEEDS_W15_PUBLIC_GATE"
    assert protocol["source_sha256"] == {name: sha(path)
                                             for name, path in sources().items()}
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    assert json.loads((HERE / "support_count.json").read_text())["status"] == \
        "PASS_EXACT_W15_TWO_FIXED_SEED_SOURCE_COUNT"
    assert json.loads((HERE / "support_audit.json").read_text())["status"] == \
        "PASS_INDEPENDENT_TWO_FIXED_SEED_SOURCE_COUNT"
    assert json.loads((HERE / "identity.json").read_text())["status"] == \
        "PASS_EXHAUSTIVE_TWO_FIXED_SEED_LINEAR_PRODUCTS"
    return protocol


def raw_preimages(q):
    _, field, curve, _, _ = base.run.source()
    return base.run.prior.prior.old.target_preimages(curve, tuple(q)), field


def traces(q):
    points, field = raw_preimages(q)
    reciprocals = [field.inv(point[0]) for point in points]
    return [(value & 1) ^ ((value >> 129) & 1) for value in reciprocals]


def freeze():
    assert not (HERE / "protocol.json").exists()
    assert not OUT.exists() and not RAW.exists()
    assert json.loads(TRACE.read_text())["polynomial_basis_trace_support"] == [0, 129]
    count = json.loads((HERE / "support_count.json").read_text())
    assert count["status"] == "PASS_EXACT_W15_TWO_FIXED_SEED_SOURCE_COUNT"
    audit = json.loads((HERE / "support_audit.json").read_text())
    identity = json.loads((HERE / "identity.json").read_text())
    assert audit["status"] == "PASS_INDEPENDENT_TWO_FIXED_SEED_SOURCE_COUNT"
    assert audit["distinct_column_signed_sixpair_tuples"] == \
        count["distinct_column_signed_sixpair_tuples"]
    assert identity["status"] == "PASS_EXHAUSTIVE_TWO_FIXED_SEED_LINEAR_PRODUCTS"
    assert identity["ordered_usable_mask_pairs_checked"] == \
        [2*n for n in count["unordered_distinct_column_pairs_by_seed"]]
    _, _, _, _, control = base.run.source()
    assert [control["masks"][2*i] ^ control["masks"][2*i+1]
            for i in range(2)] == count["fixed_pair_seeds"] == [12004, 9022]
    published = json.loads((BASE / "query_protocol.json").read_text())
    target = published["target_q"]
    control_traces = traces(control["target_q"])
    public_traces = traces(target)
    assert control_traces[control["target_preimage_index"]] == 0
    assert sorted(control_traces) == sorted(public_traces) == [0, 0, 1, 1]
    protocol = {
        "status": "FROZEN_TWO_FIXED_SEEDS_W15_PUBLIC_GATE",
        "candidate_id": None, "curve_id": count["curve_id"],
        "target_count": 1, "target_q": target,
        "target_law": "previously published ECC2K-130 subgroup point",
        "constructed_target_q": control["target_q"],
        "constructed_target_preimage_index": control["target_preimage_index"],
        "public_raw_preimage_traces": public_traces,
        "constructed_raw_preimage_traces": control_traces,
        "trace_parity_bits": [0, 129],
        "source_count": count["distinct_column_signed_sixpair_tuples"],
        "uniform_target_mean": count["uniform_target_mean_before_nonzero_intermediate_filter"],
        "summands": 12, "fixed_pair_seeds": count["fixed_pair_seeds"],
        "fixed_seed_policy": count["fixed_seed_policy"],
        "seed_equality_rows": 0,
        "workers": 1, "construction_plus_search_cap_seconds": CAP,
        "rss_cap_bytes": RSS_CAP, "solver_flags": FLAGS,
        "work_directory": str(OUT),
        "source_sha256": {name: sha(path) for name, path in sources().items()}}
    save(HERE / "protocol.json", protocol)
    OUT.mkdir()
    print(json.dumps({"status": protocol["status"],
                      "source_mean": protocol["uniform_target_mean"],
                      "public_traces": public_traces}))


def build(q, expected_traces):
    circuit, meta, raw = base.run.formula_for(tuple(q))
    assert meta["seed_equality_rows"] == 0 and len(meta["masks"]) == 12
    assert tuple(meta["fixed_seeds"]) == (12004, 9022)
    assert meta["fixed_seed_link_clauses"] == 60
    assert len(meta["middle"]) == 10
    _, field = raw_preimages(q)
    actual_traces = [(field.inv(point[0]) & 1) ^
                     ((field.inv(point[0]) >> 129) & 1) for point in raw]
    assert actual_traces == expected_traces
    clauses = [f"-{meta['flags'][index]} 0"
               for index, value in enumerate(actual_traces) if value == 1]
    for row in meta["middle"]:
        left, right = row[0], row[129]
        clauses.extend((f"-{left} {right} 0", f"{left} -{right} 0"))
    assert len(clauses) == 22
    circuit.clauses.extend(clauses)
    return circuit, meta, raw, clauses


def profile(circuit, formula):
    return {"variables": circuit.next_var-1,
            "clauses": len(circuit.clauses), "xor_rows": len(circuit.xors),
            "and_gates": circuit.and_count,
            "bytes": formula.stat().st_size, "sha256": sha(formula)}


def compress(source, destination):
    with source.open("rb") as inp, gzip.open(destination, "xb", compresslevel=6) as out:
        for block in iter(lambda: inp.read(1 << 20), b""):
            out.write(block)


def control():
    protocol = frozen()
    assert not RAW.exists() and not (OUT / "control.json").exists()
    _, _, _, _, inp = base.run.source()
    started = time.monotonic()
    circuit, meta, raw, clauses = build(inp["target_q"],
                                        protocol["constructed_raw_preimage_traces"])
    selected = protocol["constructed_target_preimage_index"]
    assert list(raw[selected]) == inp["raw_sum"]
    assert [inp["masks"][2*i] ^ inp["masks"][2*i+1]
            for i in range(2)] == protocol["fixed_pair_seeds"]
    try:
        circuit.write(RAW)
        initial = {}
        for row, mask in zip(meta["masks"], inp["masks"]):
            initial.update({wire: mask >> bit & 1 for bit, wire in enumerate(row)})
        for index, wire in enumerate(meta["flags"]):
            initial[wire] = int(index == selected)
        for row, value in zip(meta["middle"], inp["middle_reciprocals"]):
            initial.update({wire: value >> bit & 1 for bit, wire in enumerate(row)})
        assert len(initial) == meta["primary_variables"]
        assignment = base.run.witness_tools.complete_assignment(circuit, initial)
        check = base.run.base.check_xcnf(RAW, assignment)
        group = lift.lift(inp["masks"], inp["middle_reciprocals"],
                          tuple(inp["target_q"]), selected)
        assert group["status"] == "GROUP_LIFT_FOUND"
        save(OUT / "control_group_lift.json", group)
        form = profile(circuit, RAW)
        compress(RAW, OUT / "control.xcnf.gz")
        receipt = {"status": "PASS_TWO_FIXED_SEEDS_CONSTRUCTED_CONTROL",
                   "candidate_id": None, "target_count": 0,
                   "target_q": inp["target_q"],
                   "added_trace_clauses": clauses,
                   "formula": form,
                   "formula_gzip_sha256": sha(OUT / "control.xcnf.gz"),
                   "xcnf_check": check,
                   "group_lift_status": group["status"],
                   "elapsed_seconds": time.monotonic()-started,
                   "sha256": {"protocol": sha(HERE / "protocol.json"),
                              "group_lift": sha(OUT / "control_group_lift.json")}}
        save(OUT / "control.json", receipt)
        print(json.dumps({"status": receipt["status"], "formula": form}))
    finally:
        RAW.unlink(missing_ok=True)


def query():
    protocol = frozen()
    control_result = json.loads((OUT / "control.json").read_text())
    assert control_result["status"] == "PASS_TWO_FIXED_SEEDS_CONSTRUCTED_CONTROL"
    assert control_result["sha256"]["protocol"] == sha(HERE / "protocol.json")
    assert not RAW.exists() and not (OUT / "result.json").exists()
    started = time.monotonic()
    circuit, meta, raw, clauses = build(protocol["target_q"],
                                        protocol["public_raw_preimage_traces"])
    circuit.write(RAW)
    build_seconds = time.monotonic()-started
    form = profile(circuit, RAW)
    assert form["clauses"] == control_result["formula"]["clauses"]
    parent = psutil.Process()
    peak = parent.memory_info().rss
    remaining = CAP-build_seconds-8
    assert remaining > 0 and peak < RSS_CAP
    command = [str(SOLVER), *FLAGS, f"--maxtime={max(1,int(remaining)-2)}", str(RAW)]
    stdout_path, stderr_path = OUT / "solver.stdout.txt", OUT / "solver.stderr.txt"
    with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                 start_new_session=True)
        process = psutil.Process(child.pid)
        solver_started = time.monotonic()
        stop = None
        while child.poll() is None:
            try:
                peak = max(peak, parent.memory_info().rss+process.memory_info().rss)
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
        model = base.run.base.read_model(output, form["variables"])
        check = base.run.base.check_xcnf(RAW, model)
        masks = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                 for row in meta["masks"]]
        middle = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                  for row in meta["middle"]]
        selected = [index for index, wire in enumerate(meta["flags"]) if model[wire]]
        assert len(selected) == 1 and protocol["public_raw_preimage_traces"][selected[0]] == 0
        group = lift.lift(masks, middle, tuple(protocol["target_q"]), selected[0])
        save(OUT / "group_lift.json", group)
        status = "GROUP_RELATION_PENDING_INDEPENDENT_SAGE" if group["status"] == "GROUP_LIFT_FOUND" else "SAT_NO_GROUP_LIFT"
    elif stop == "RSS_CAP":
        status = "OOM"
    elif stop in ("QUERY_WALL_CAP", "SOLVER_WALL_CAP") or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "UNSAT_FORMULA"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    compress(RAW, OUT / "system.xcnf.gz")
    RAW.unlink()
    result = {"status": status, "candidate_id": None,
              "curve_id": protocol["curve_id"], "target_count": 1,
              "target_q": protocol["target_q"],
              "raw_target_preimages": [list(point) for point in raw],
              "added_trace_clauses": clauses,
              "formula": form, "formula_gzip_sha256": sha(OUT / "system.xcnf.gz"),
              "solver_command": command, "solver_status_lines": statuses,
              "model_lines": model_lines, "solver_exit_code": child.returncode,
              "stop_reason": stop, "producer_xcnf_check": check,
              "group_lift_status": group["status"] if group else None,
              "phase_seconds": {"target_formula": build_seconds,
                                "solver": solver_seconds,
                                "construction_plus_search": build_seconds+solver_seconds},
              "sampled_peak_combined_rss_bytes": peak,
              "sha256": {"protocol": sha(HERE / "protocol.json"),
                         "control": sha(OUT / "control.json"),
                         "stdout": sha(stdout_path), "stderr": sha(stderr_path),
                         "formula_gzip": sha(OUT / "system.xcnf.gz")}}
    save(OUT / "result.json", result)
    print(json.dumps({"status": status,
                      "construction_plus_search_seconds": build_seconds+solver_seconds,
                      "peak_rss_bytes": peak, "formula_sha256": form["sha256"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "control", "query"))
    mode = parser.parse_args().mode
    try:
        {"freeze": freeze, "control": control, "query": query}[mode]()
    except Exception:
        if OUT.exists() and not (OUT / "failure.json").exists():
            save(OUT / "failure.json", {"status": "PRODUCER_FAILURE", "mode": mode,
                                        "traceback": traceback.format_exc(),
                                        "raw_formula_sha256": sha(RAW) if RAW.exists() else None,
                                        "protocol_sha256": sha(HERE / "protocol.json")
                                        if (HERE / "protocol.json").exists() else None})
        raise
