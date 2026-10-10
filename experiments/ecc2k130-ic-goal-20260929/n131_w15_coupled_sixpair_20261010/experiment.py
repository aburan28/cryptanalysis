#!/usr/bin/env sage -python
"""Exact W15 six-pair control and unpinned ECC2K-130 public query."""

import argparse
import collections
import gzip
import hashlib
import importlib.util
import json
import os
import resource
import subprocess
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent / "n131_w14_coupled_sixpair_sat_20261010"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
CAP_SECONDS = 600
RSS_CAP = 4 * 1024**3
FLAGS = ["--threads=1", "--xor=0", "--printsol=1",
         "--random=20261010", "--maxconfl=20000000"]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run = load("n131_w15_original_run", ORIGINAL / "run.py")
compact = load("n131_w15_circuit", HERE / "w15_circuit.py")
original_source = run.source


def w15_source():
    _, field, curve, old_basis, control = original_source()
    assert old_basis == [1 << i for i in range(1, 15)]
    columns = {int(mask): int(column) for mask, column in
               (line.split() for line in (HERE / "support_w15.tsv").read_text().splitlines())}
    assert len(columns) == 16441 and len(set(columns.values())) == 16381
    return columns, field, curve, old_basis + [1 << 15], control


run.source = w15_source
run.method = compact
lift = load("n131_w15_group_lift", HERE / "w15_lift.py")


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def save(path, value):
    with Path(path).open("x") as out:
        json.dump(value, out, indent=2, sort_keys=True)
        out.write("\n")


def source_paths():
    return {"experiment": Path(__file__), "w15_circuit": HERE / "w15_circuit.py",
            "w15_lift": HERE / "w15_lift.py",
            "w15_support": HERE / "support_w15.tsv",
            "w15_support_receipt": HERE / "support_receipt.json",
            "w15_source_audit": HERE / "sage_support_audit.json",
            "w15_group_audit": HERE / "sage_group_audit.json",
            "original_run": ORIGINAL / "run.py",
            "original_circuit": ORIGINAL / "circuit.py",
            "original_control": ORIGINAL / "control.json",
            "original_sage_audit": ORIGINAL / "sage_audit.json",
            "original_public_protocol": ORIGINAL / "query_protocol.json",
            "checked_sage_runtime": HERE / "sage_runtime_info.json",
            "solver": SOLVER}


def checked_sources():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_W15_N131_CONTROL_AND_PUBLIC_QUERY"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in source_paths().items()}
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    return protocol


def freeze():
    original = json.loads((ORIGINAL / "query_protocol.json").read_text())
    audit = json.loads((ORIGINAL / "sage_audit.json").read_text())
    assert original["status"] == "FROZEN_BEFORE_COUPLED_SIXPAIR_PUBLISHED_QUERY"
    assert audit["status"] == "PASS_INDEPENDENT_SAGE_N131_COUPLED_SIXPAIR_GROUP_REPLAY"
    support = json.loads((HERE / "support_receipt.json").read_text())
    support_audit = json.loads((HERE / "sage_support_audit.json").read_text())
    group_audit = json.loads((HERE / "sage_group_audit.json").read_text())
    assert support["status"] == "COMPLETE"
    assert support_audit["status"] == "PASS_FULL_MASKS_ORBITS_AND_SIX_WINDOW_BASE"
    assert group_audit["status"] == "PASS_EXACT_PROJECTED_GROUP_BASE"
    columns, _, _, _, control = run.source()
    aliases = collections.Counter(columns.values())
    assert len(columns) == support["rational_masks"] == 16441
    assert len(aliases) == support["folded_columns_K"] == 16381
    assert collections.Counter(aliases.values()) == {1: 16323, 2: 56, 3: 2}
    ordered_cross_aliases = sum(size * (size - 1) for size in aliases.values())
    assert ordered_cross_aliases == 124
    pair_count = compact.ATOMS * (compact.ATOMS - 1) // 2
    assert pair_count == 66
    expected_compact_clauses = pair_count * (1 + ordered_cross_aliases)
    assert expected_compact_clauses == 8250
    # For any two valid masks, equal columns means either equal masks or one
    # of the enumerated distinct within-column alias pairs. These cases are
    # exactly the XOR-inequality and sparse alias constraints, respectively.
    record = {
        "status": "FROZEN_BEFORE_W15_N131_CONTROL_AND_PUBLIC_QUERY",
        "candidate_id": None, "curve_id": original["curve_id"],
        "public_target_q": original["target_q"],
        "constructed_control_q": control["target_q"],
        "target_count": 1, "workers": 1,
        "source_dimension": 15,
        "actual_projected_factor_base_B": 197292,
        "folded_columns_K": 16381, "summands": 12,
        "distinct_mask_values": len(columns),
        "distinct_alias_oriented_pairs_per_slot_pair": ordered_cross_aliases,
        "slot_pair_count": pair_count,
        "expected_compact_column_clauses": expected_compact_clauses,
        "expected_extra_native_xor_rows": pair_count * 15,
        "control_wall_cap_seconds": 120,
        "public_construction_plus_search_cap_seconds": CAP_SECONDS,
        "rss_cap_bytes": RSS_CAP, "solver_flags": FLAGS,
        "source_sha256": {name: sha(path) for name, path in source_paths().items()},
    }
    save(HERE / "protocol.json", record)
    print(json.dumps({"status": record["status"],
                      "B": record["actual_projected_factor_base_B"],
                      "K": record["folded_columns_K"],
                      "compact_column_clauses": expected_compact_clauses}))


def formula_path(label):
    path = Path(f"/private/tmp/n131_w15_coupled_sixpair_{label}_{os.getpid()}.xcnf")
    if path.exists():
        raise FileExistsError(path)
    return path


def compress(source, destination):
    with source.open("rb") as inp, gzip.open(destination, "xb", compresslevel=6) as out:
        while block := inp.read(1 << 20):
            out.write(block)


def metadata(circuit, meta, formula):
    return {"variables": circuit.next_var - 1,
            "clauses": len(circuit.clauses), "xor_rows": len(circuit.xors),
            "and_gates": circuit.and_count,
            "column_clauses": meta["duplicate_column_clauses"],
            "mask_inequality_clauses": meta["mask_inequality_clauses"],
            "mask_inequality_xor_rows": meta["mask_inequality_xor_rows"],
            "distinct_alias_clauses": meta["distinct_alias_clauses"],
            "bytes": formula.stat().st_size,
            "sha256": sha(formula)}


def control():
    protocol = checked_sources()
    control = json.loads((ORIGINAL / "control.json").read_text())
    assert control["target_q"] == protocol["constructed_control_q"]
    started = time.monotonic()
    circuit, meta, lifts = run.formula_for(tuple(control["target_q"]))
    assert list(lifts[control["target_preimage_index"]]) == control["raw_sum"]
    assert meta["duplicate_column_clauses"] == protocol["expected_compact_column_clauses"]
    assert meta["mask_inequality_xor_rows"] == protocol["expected_extra_native_xor_rows"]
    build_seconds = time.monotonic() - started
    formula = formula_path("control")
    try:
        circuit.write(formula)
        initial = {}
        for row, mask in zip(meta["masks"], control["masks"]):
            initial.update({wire: mask >> bit & 1 for bit, wire in enumerate(row)})
        for index, wire in enumerate(meta["flags"]):
            initial[wire] = int(index == control["target_preimage_index"])
        for row, value in zip(meta["middle"], control["middle_reciprocals"]):
            initial.update({wire: value >> bit & 1 for bit, wire in enumerate(row)})
        assert len(initial) == meta["primary_variables"]
        assignment = run.witness_tools.complete_assignment(circuit, initial)
        check = run.base.check_xcnf(formula, assignment)
        profile = metadata(circuit, meta, formula)
        compress(formula, HERE / "constructed.xcnf.gz")
        profile["gzip_sha256"] = sha(HERE / "constructed.xcnf.gz")
    finally:
        formula.unlink(missing_ok=True)
    elapsed = time.monotonic() - started
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    status = "PASS_FULL_COMPACT_N131_CONSTRUCTED_ASSIGNMENT" if (
        elapsed <= protocol["control_wall_cap_seconds"]
        and peak_rss <= protocol["rss_cap_bytes"]) else "RESOURCE_GATE_EXCEEDED"
    receipt = {"status": status, "candidate_id": None,
               "curve_id": protocol["curve_id"], "target_q": control["target_q"],
               "formula": profile, "full_xcnf_assignment_check": check,
               "phase_seconds": {"build": build_seconds,
                                 "check_and_archive": elapsed - build_seconds,
                                 "total": elapsed},
               "peak_rss_bytes": peak_rss,
               "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                                 "constructed_formula_gzip": profile["gzip_sha256"]}}
    save(HERE / "control_result.json", receipt)
    print(json.dumps({"status": status, "formula": profile,
                      "elapsed_seconds": elapsed, "peak_rss_bytes": peak_rss}))


def query():
    protocol = checked_sources()
    control_receipt = json.loads((HERE / "control_result.json").read_text())
    assert control_receipt["status"] == "PASS_FULL_COMPACT_N131_CONSTRUCTED_ASSIGNMENT"
    assert control_receipt["source_sha256"]["protocol"] == sha(HERE / "protocol.json")
    target = tuple(protocol["public_target_q"])
    folder = HERE / "public_query"
    folder.mkdir(exist_ok=False)
    started = time.monotonic()
    circuit, meta, lifts = run.formula_for(target)
    assert meta["duplicate_column_clauses"] == protocol["expected_compact_column_clauses"]
    formula = formula_path("public")
    circuit.write(formula)
    build_seconds = time.monotonic() - started
    form = metadata(circuit, meta, formula)
    parent = psutil.Process()
    peak_rss = parent.memory_info().rss
    remaining = CAP_SECONDS - build_seconds - 1
    if remaining <= 5 or peak_rss >= RSS_CAP:
        raise RuntimeError("public construction exceeded frozen resource gate")
    command = [str(SOLVER), *FLAGS,
               f"--maxtime={max(1, int(remaining) - 2)}", str(formula)]
    stdout_path = folder / "solver.stdout.txt"
    stderr_path = folder / "solver.stderr.txt"
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                 start_new_session=True)
        process = psutil.Process(child.pid)
        stop_reason = None
        solve_started = time.monotonic()
        sampled_cpu = 0.0
        while child.poll() is None:
            try:
                peak_rss = max(peak_rss, parent.memory_info().rss
                               + process.memory_info().rss)
                cpu = process.cpu_times()
                sampled_cpu = max(sampled_cpu, cpu.user + cpu.system)
            except psutil.NoSuchProcess:
                pass
            if peak_rss >= RSS_CAP:
                stop_reason = "RSS_CAP"
            elif time.monotonic() - started >= CAP_SECONDS:
                stop_reason = "QUERY_WALL_CAP"
            elif time.monotonic() - solve_started >= remaining:
                stop_reason = "SOLVER_WALL_CAP"
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
    solve_seconds = time.monotonic() - solve_started
    output = stdout_path.read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in output.splitlines())
    model_check = None
    group_lift = None
    if statuses == ["s SATISFIABLE"] and model_lines:
        model = run.base.read_model(output, form["variables"])
        model_check = run.base.check_xcnf(formula, model)
        masks = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                 for row in meta["masks"]]
        middle = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
                  for row in meta["middle"]]
        selected = [index for index, wire in enumerate(meta["flags"]) if model[wire]]
        assert len(selected) == 1
        group_lift = lift.lift(masks, middle, target, selected[0])
        save(folder / "group_lift.json", group_lift)
        status = "GROUP_RELATION_PENDING_INDEPENDENT_SAGE" if (
            group_lift["status"] == "GROUP_LIFT_FOUND") else "SAT_NO_GROUP_LIFT"
    elif stop_reason == "RSS_CAP":
        status = "OOM"
    elif stop_reason in ("QUERY_WALL_CAP", "SOLVER_WALL_CAP") or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "UNSAT_FORMULA"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    compress(formula, folder / "system.xcnf.gz")
    formula.unlink()
    receipt = {
        "status": status, "candidate_id": None,
        "curve_id": protocol["curve_id"], "target_count": 1,
        "target_q": list(target), "raw_target_preimages": [list(p) for p in lifts],
        "formula": {**form, "gzip_sha256": sha(folder / "system.xcnf.gz")},
        "solver_command": command, "solver_status_lines": statuses,
        "model_lines": model_lines, "solver_exit_code": child.returncode,
        "stop_reason": stop_reason, "producer_xcnf_check": model_check,
        "group_lift_status": group_lift["status"] if group_lift else None,
        "verified_relations": 0, "useful_rank": 0,
        "phase_seconds": {"target_formula": build_seconds,
                          "solver": solve_seconds,
                          "construction_plus_search": build_seconds + solve_seconds,
                          "process_through_archive": time.monotonic() - started},
        "sampled_peak_combined_rss_bytes": peak_rss,
        "sampled_solver_cpu_seconds": sampled_cpu,
        "sha256": {"protocol": sha(HERE / "protocol.json"),
                   "control": sha(HERE / "control_result.json"),
                   "stdout": sha(stdout_path), "stderr": sha(stderr_path),
                   "formula_gzip": sha(folder / "system.xcnf.gz")},
    }
    save(folder / "result.json", receipt)
    print(json.dumps({"status": status,
                      "construction_plus_search_seconds": build_seconds + solve_seconds,
                      "formula": form, "peak_rss_bytes": peak_rss}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "control", "query"))
    {"freeze": freeze, "control": control, "query": query}[parser.parse_args().mode]()
