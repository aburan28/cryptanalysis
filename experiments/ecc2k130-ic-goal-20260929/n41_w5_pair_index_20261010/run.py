#!/usr/bin/env python3
"""Exact pair-indexed N41 public-point formula and bounded SAT queries."""

import argparse
import hashlib
import importlib.util
import json
import subprocess
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / "n41_w5_ten_source_gate_20261010"
LOW = ROOT / "n41_w5_ten_lowproduct_20261010" / "circuit.py"
SAMEPAIR = ROOT / "n41_w5_samepair_hybrid_20261010"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
ROTATIONS = (0, 0, 8, 8, 16, 16, 24, 24, 32, 32)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load("n41_w5_source_runner_for_indexed_query", SOURCE / "run.py")
indexed = load("n41_w5_pair_index_circuit", HERE / "circuit.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open("x") as out:
        json.dump(value, out, indent=2, sort_keys=True)
        out.write("\n")


def sources():
    return {"runner": Path(__file__), "circuit": HERE / "circuit.py",
            "index_builder": HERE / "build_index.py",
            "pair_index": HERE / "pair_index.json",
            "index_sage_audit": HERE / "sage_index_audit.json",
            "runtime": HERE / "sage_runtime_info.json",
            "geometry": SOURCE / "geometry_result.json",
            "source_runner": SOURCE / "run.py",
            "lowproduct_circuit": LOW,
            "public_hit": SAMEPAIR / "run/hits.jsonl",
            "public_hit_sage_audit": SAMEPAIR / "sage_audit.json",
            "solver": SOLVER}


def context():
    ctx = old.setup()
    ctx["geometry"] = dict(ctx["geometry"])
    ctx["geometry"]["rotations"] = list(ROTATIONS)
    ctx["geometry"]["bases_u"] = [ctx["geometry"]["bases_u"][r // 4]
                                    for r in ROTATIONS]
    return ctx


def inputs():
    record = json.loads((HERE / "pair_index.json").read_text())
    audit = json.loads((HERE / "sage_index_audit.json").read_text())
    assert record["status"] == "PASS_EXACT_W5_UNORDERED_PAIR_INDEX"
    assert audit["status"] == "PASS_INDEPENDENT_SAGE_COMPLETE_W5_PAIR_INDEX"
    assert audit["source_sha256"]["index"] == sha(HERE / "pair_index.json")
    return record["entries"]


def known_witness(ctx, entries):
    hit = json.loads((SAMEPAIR / "run/hits.jsonl").read_text().strip())
    leaves, middle, total = old.chain(ctx, hit["masks"], hit["signs"])
    assert old.regular(ctx, [*leaves, *middle, total])
    assert list(total) == hit["raw_sum"]
    qprime = old.qprime_of(ctx, ctx["q"])
    targets = old.old.base.target_preimages(ctx["field"], ctx["curve"], qprime)
    assert total == targets[hit["target_preimage_index"]]
    local_z = indexed.method.frob(
        ctx["field"], old.old.transformed(ctx["field"], middle[4]), 9)
    pair = (hit["masks"][8], hit["masks"][9], local_z)
    assert pair[0] < pair[1]
    selector = next(i for i, entry in enumerate(entries)
                    if (entry["mask_a"], entry["mask_b"], entry["z_local"]) == pair)
    return hit, targets, middle, selector


def build(ctx, targets, entries):
    target_us = [old.old.transformed(ctx["field"], point) for point in targets]
    circuit = old.old.base.KaratsubaCircuit(41, [0, 3])
    meta = indexed.build(circuit, ctx["field"], ctx["geometry"],
                         target_us, entries)
    return circuit, meta


def freeze():
    entries = inputs()
    ctx = context()
    _, _, _, selector = known_witness(ctx, entries)
    record = {"status": "FROZEN_BEFORE_INDEXED_FORMULA_AND_SEARCH",
              "kind": "n41_w5_same_rotation_exact_fifth_pair_index",
              "candidate_id": None, "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
              "public_target_q": [1458168294740, 1672312028033],
              "target_count": 1, "source_width": 5, "summands": 10,
              "rotations": list(ROTATIONS),
              "actual_factor_base_points_B": 170,
              "folded_columns_K": 14,
              "exact_pair_index_entries": len(entries),
              "known_relation_selector_index": selector,
              "fixed_selector_cap_seconds": 45,
              "unpinned_cap_seconds": 120,
              "rss_cap_bytes": 4 * 1024**3,
              "workers": 1,
              "solver_flags": ["--threads=1", "--xor=0", "--printsol=1",
                               "--random=20261010"],
              "source_sha256": {name: sha(path) for name, path in sources().items()}}
    save(HERE / "protocol.json", record)
    print(json.dumps({"status": record["status"],
                      "entries": len(entries), "known_selector": selector}))


def verify():
    record = json.loads((HERE / "protocol.json").read_text())
    assert record["status"] == "FROZEN_BEFORE_INDEXED_FORMULA_AND_SEARCH"
    assert record["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    return record


def formula_stats(circuit, path):
    return {"variables": circuit.next_var - 1,
            "clauses": len(circuit.clauses), "xor_rows": len(circuit.xors),
            "and_gates": circuit.and_count,
            "bytes": Path(path).stat().st_size,
            "sha256": sha(path)}


def preflight():
    protocol = verify()
    entries = inputs()
    ctx = context()
    hit, targets, middle, selector = known_witness(ctx, entries)
    began = time.monotonic()
    circuit, meta = build(ctx, targets, entries)
    public = HERE / "public_indexed.xcnf"
    circuit.write(public)
    initial = {}
    for row, mask in zip(meta["masks"], hit["masks"]):
        initial.update({wire: mask >> i & 1 for i, wire in enumerate(row)})
    for i, wire in enumerate(meta["flags"]):
        initial[wire] = int(i == hit["target_preimage_index"])
    for row, point in zip(meta["middle"], middle):
        value = old.old.transformed(ctx["field"], point)
        initial.update({wire: value >> i & 1 for i, wire in enumerate(row)})
    for i, wire in enumerate(meta["pair_selectors"]):
        initial[wire] = int(i == selector)
    for i, wire in enumerate(meta["pair_sequence"]):
        initial[wire] = int(selector <= i)
    assignment = old.old.witness_tools.complete_assignment(circuit, initial)
    public_check = old.old.base.check_xcnf(public, assignment)
    decoded = old.decode(assignment, meta, ctx,
                         old.qprime_of(ctx, ctx["q"]), targets)
    assert decoded["valid"] and decoded["masks"] == hit["masks"]
    public_stats = formula_stats(circuit, public)
    circuit.clauses.append(f"{meta['pair_selectors'][selector]} 0")
    fixed = HERE / "fixed_selector.xcnf"
    circuit.write(fixed)
    fixed_check = old.old.base.check_xcnf(fixed, assignment)
    fixed_stats = formula_stats(circuit, fixed)
    receipt = {"status": "PASS_FULL_INDEXED_PUBLIC_AND_FIXED_CONTROLS",
               "candidate_id": None, "curve_id": protocol["curve_id"],
               "public_target_q": protocol["public_target_q"],
               "public_formula": public_stats, "fixed_formula": fixed_stats,
               "public_xcnf_check": public_check,
               "fixed_xcnf_check": fixed_check,
               "known_selector_index": selector,
               "known_relation": decoded,
               "build_and_check_wall_seconds": time.monotonic() - began,
               "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                                 "index": sha(HERE / "pair_index.json"),
                                 "public_formula": sha(public),
                                 "fixed_formula": sha(fixed)}}
    save(HERE / "preflight.json", receipt)
    print(json.dumps({"status": receipt["status"],
                      "public_formula": public_stats,
                      "fixed_formula": fixed_stats}))


def solve(mode):
    protocol = verify()
    receipt = json.loads((HERE / "preflight.json").read_text())
    assert receipt["status"] == "PASS_FULL_INDEXED_PUBLIC_AND_FIXED_CONTROLS"
    fixed = mode == "fixed"
    folder = HERE / ("fixed_query" if fixed else "public_query")
    folder.mkdir(exist_ok=False)
    formula = HERE / ("fixed_selector.xcnf" if fixed else "public_indexed.xcnf")
    stats = receipt["fixed_formula" if fixed else "public_formula"]
    assert stats["sha256"] == sha(formula)
    cap = protocol["fixed_selector_cap_seconds" if fixed else "unpinned_cap_seconds"]
    command = [str(SOLVER), *protocol["solver_flags"],
               f"--maxtime={cap-2}", str(formula)]
    start = time.monotonic()
    peak_rss = 0
    stop = None
    stdout, stderr = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
    with stdout.open("xb") as out, stderr.open("xb") as err:
        proc = subprocess.Popen(command, stdout=out, stderr=err,
                                start_new_session=True)
        child = psutil.Process(proc.pid)
        while proc.poll() is None:
            try:
                peak_rss = max(peak_rss, child.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            if peak_rss > protocol["rss_cap_bytes"]:
                stop = "RSS_CAP"
            elif time.monotonic() - start >= cap:
                stop = "SOLVER_WALL_CAP"
            if stop:
                proc.terminate()
                break
            time.sleep(0.1)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            stop = (stop or "DRAIN_TIMEOUT") + "_KILLED"
    output = stdout.read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in output.splitlines())
    relation = xcnf_check = selected = None
    if statuses == ["s SATISFIABLE"] and model_lines:
        model = old.old.base.read_model(output, stats["variables"])
        xcnf_check = old.old.base.check_xcnf(formula, model)
        ctx = context()
        targets = old.old.base.target_preimages(
            ctx["field"], ctx["curve"], old.qprime_of(ctx, ctx["q"]))
        _, meta = build(ctx, targets, inputs())
        selected = [i for i, wire in enumerate(meta["pair_selectors"])
                    if model[wire]]
        relation = old.decode(model, meta, ctx,
                              old.qprime_of(ctx, ctx["q"]), targets)
        valid = relation["valid"] and len(selected) == 1
        status = "SAT_MODEL_PENDING_INDEPENDENT_SAGE" if valid else "INVALID_INDEXED_MODEL"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "UNSAT_FORMULA"
    elif stop == "RSS_CAP":
        status = "OOM"
    elif stop == "SOLVER_WALL_CAP" or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    result = {"status": status, "candidate_id": None,
              "curve_id": protocol["curve_id"],
              "public_target_q": protocol["public_target_q"],
              "target_count": 1, "fixed_selector": fixed,
              "known_selector_index": protocol["known_relation_selector_index"] if fixed else None,
              "solver_command": command, "solver_exit_code": proc.returncode,
              "solver_status_lines": statuses, "model_lines": model_lines,
              "stop_reason": stop, "solver_wall_seconds": time.monotonic() - start,
              "sampled_solver_peak_rss_bytes": peak_rss,
              "selected_index": selected, "xcnf_check": xcnf_check,
              "relation": relation, "verified_relations": 0,
              "useful_rank": 0,
              "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                                "formula": sha(formula),
                                "stdout": sha(stdout), "stderr": sha(stderr)}}
    save(folder / "result.json", result)
    print(json.dumps({"status": status,
                      "solver_wall_seconds": result["solver_wall_seconds"],
                      "selected_index": selected}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "preflight", "fixed", "public"))
    mode = parser.parse_args().mode
    {"freeze": freeze, "preflight": preflight,
     "fixed": lambda: solve("fixed"),
     "public": lambda: solve("public")}[mode]()
