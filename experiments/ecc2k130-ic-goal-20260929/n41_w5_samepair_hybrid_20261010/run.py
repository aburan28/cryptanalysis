#!/usr/bin/env python3
"""Freeze, check, and query the N41 W5 target-conditioned pair relaxation."""

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / "n41_w5_ten_source_gate_20261010"
LOW = ROOT / "n41_w5_ten_lowproduct_20261010" / "circuit.py"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
ROTATIONS = (0, 0, 8, 8, 16, 16, 24, 24, 32, 32)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load("n41_w5_original_runner_for_hybrid", OLD / "run.py")
hybrid = load("n41_w5_samepair_hybrid_circuit", HERE / "hybrid_circuit.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open("x") as out:
        json.dump(value, out, indent=2, sort_keys=True)
        out.write("\n")


def sources():
    return {"runner": Path(__file__), "hybrid_circuit": HERE / "hybrid_circuit.py",
            "lowproduct_circuit": LOW, "original_runner": OLD / "run.py",
            "geometry": OLD / "geometry_result.json",
            "source_audit": OLD / "sage_geometry_audit.json",
            "samepair_protocol": HERE / "protocol.json",
            "samepair_sage_audit": HERE / "sage_audit.json",
            "samepair_hit": HERE / "run/hits.jsonl",
            "runtime": HERE / "sage_runtime_info.json", "solver": SOLVER}


def context():
    ctx = old.setup()
    ctx["geometry"] = dict(ctx["geometry"])
    ctx["geometry"]["rotations"] = list(ROTATIONS)
    ctx["geometry"]["bases_u"] = [ctx["geometry"]["bases_u"][r // 4]
                                    for r in ROTATIONS]
    return ctx


def witness(ctx):
    hit = json.loads((HERE / "run/hits.jsonl").read_text().strip())
    masks, signs = hit["masks"], hit["signs"]
    leaves, middle, total = old.chain(ctx, masks, signs)
    assert old.regular(ctx, [*leaves, *middle, total])
    assert list(total) == hit["raw_sum"]
    qprime = old.qprime_of(ctx, ctx["q"])
    targets = old.old.base.target_preimages(ctx["field"], ctx["curve"], qprime)
    assert total == targets[hit["target_preimage_index"]]
    assert len({ctx["columns"][mask] for mask in masks}) == 10
    w_basis = ctx["geometry"]["source_basis_w"]
    mask_a, mask_b = masks[8:10]
    w_a = 0
    w_b = 0
    for bit, w in enumerate(w_basis):
        if mask_a >> bit & 1:
            w_a ^= w
        if mask_b >> bit & 1:
            w_b ^= w
    product = ctx["field"].mul(w_a, w_b)
    assert product & ~sum(1 << bit for bit in range(2, 11)) == 0
    return hit, targets, middle, product


def freeze():
    assert json.loads((HERE / "sage_audit.json").read_text())["status"] == \
        "PASS_INDEPENDENT_SAGE_SAMEPAIR_PUBLIC_RELATION"
    record = {"status": "FROZEN_BEFORE_HYBRID_FORMULA",
              "kind": "n41_w5_fifth_pair_low_product_relaxation",
              "proposal_id": "Q_N41_W5_SAMEPAIR_HYBRID_GATE",
              "candidate_id": None, "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
              "public_target_q": [1458168294740, 1672312028033],
              "target_count": 1, "summands": 10, "source_width": 5,
              "rotations": list(ROTATIONS), "actual_factor_base_points_B": 170,
              "folded_columns_K": 14, "exact_pair_links": 4,
              "relaxed_pair_index": 4, "relaxed_product_degrees": list(range(2, 11)),
              "solver_wall_cap_seconds": 60, "rss_cap_bytes": 4 * 1024**3,
              "workers": 1, "solver_flags": ["--threads=1", "--xor=0",
                                            "--printsol=1", "--random=20261010"],
              "source_sha256": {name: sha(path) for name, path in sources().items()}}
    save(HERE / "hybrid_protocol.json", record)
    print(json.dumps({"status": record["status"], "B": 170, "K": 14}))


def verify():
    record = json.loads((HERE / "hybrid_protocol.json").read_text())
    assert record["status"] == "FROZEN_BEFORE_HYBRID_FORMULA"
    assert record["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    return record


def build(ctx, targets):
    target_us = [old.old.transformed(ctx["field"], point) for point in targets]
    circuit = old.old.base.KaratsubaCircuit(41, [0, 3])
    meta = hybrid.build(circuit, ctx["field"], ctx["geometry"], target_us)
    return circuit, meta


def preflight():
    record = verify()
    ctx = context()
    hit, targets, middle, product = witness(ctx)
    started = time.monotonic()
    circuit, meta = build(ctx, targets)
    formula = HERE / "public_hybrid.xcnf"
    circuit.write(formula)
    initial = {}
    for row, mask in zip(meta["masks"], hit["masks"]):
        initial.update({wire: (mask >> i) & 1 for i, wire in enumerate(row)})
    for i, wire in enumerate(meta["flags"]):
        initial[wire] = int(i == hit["target_preimage_index"])
    for row, point in zip(meta["middle"], middle):
        value = old.old.transformed(ctx["field"], point)
        initial.update({wire: (value >> i) & 1 for i, wire in enumerate(row)})
    for i, wire in enumerate(meta["relaxed_product_bits"]):
        initial[wire] = (product >> (i + 2)) & 1
    model = old.old.witness_tools.complete_assignment(circuit, initial)
    check = old.old.base.check_xcnf(formula, model)
    relation = old.decode(model, meta, ctx,
                          old.qprime_of(ctx, ctx["q"]), targets)
    assert relation["valid"] and relation["masks"] == hit["masks"]
    stats = {"variables": circuit.next_var - 1,
             "clauses": len(circuit.clauses), "xor_rows": len(circuit.xors),
             "and_gates": circuit.and_count, "bytes": formula.stat().st_size,
             "sha256": sha(formula)}
    result = {"status": "PASS_FULL_HYBRID_FORMULA_PUBLIC_RELATION",
              "candidate_id": None, "curve_id": record["curve_id"],
              "formula": stats, "xcnf_check": check, "relation": relation,
              "relaxed_product_bits_value": product >> 2,
              "wall_seconds": time.monotonic() - started,
              "source_sha256": {"protocol": sha(HERE / "hybrid_protocol.json"),
                                "formula": sha(formula)}}
    save(HERE / "preflight.json", result)
    print(json.dumps({"status": result["status"], "formula": stats}))


def query():
    record = verify()
    receipt = json.loads((HERE / "preflight.json").read_text())
    assert receipt["status"] == "PASS_FULL_HYBRID_FORMULA_PUBLIC_RELATION"
    formula = HERE / "public_hybrid.xcnf"
    assert receipt["formula"]["sha256"] == sha(formula)
    ctx = context()
    qprime = old.qprime_of(ctx, ctx["q"])
    targets = old.old.base.target_preimages(ctx["field"], ctx["curve"], qprime)
    circuit, meta = build(ctx, targets)
    assert circuit.next_var - 1 == receipt["formula"]["variables"]
    out_path = HERE / "solver.stdout.txt"
    err_path = HERE / "solver.stderr.txt"
    command = [str(SOLVER), *record["solver_flags"],
               "--maxtime=58", str(formula)]
    start = time.monotonic()
    peak_rss = 0
    stop = None
    with out_path.open("xb") as out, err_path.open("xb") as err:
        proc = subprocess.Popen(command, stdout=out, stderr=err,
                                start_new_session=True)
        child = psutil.Process(proc.pid)
        while proc.poll() is None:
            try:
                peak_rss = max(peak_rss, child.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            if peak_rss > record["rss_cap_bytes"]:
                stop = "RSS_CAP"
            elif time.monotonic() - start >= record["solver_wall_cap_seconds"]:
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
    output = out_path.read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in output.splitlines())
    relation = xcnf_check = None
    if statuses == ["s SATISFIABLE"] and model_lines:
        model = old.old.base.read_model(output, receipt["formula"]["variables"])
        xcnf_check = old.old.base.check_xcnf(formula, model)
        relation = old.decode(model, meta, ctx, qprime, targets)
        status = "SAT_MODEL_PENDING_INDEPENDENT_SAGE" if relation["valid"] else "RELAXED_MODEL_REJECTED_EXACT_PAIR"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "UNSAT_FORMULA"
    elif stop == "RSS_CAP":
        status = "OOM"
    elif stop == "SOLVER_WALL_CAP" or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    result = {"status": status, "candidate_id": None,
              "curve_id": record["curve_id"], "public_target_q": record["public_target_q"],
              "target_count": 1, "solver_command": command,
              "solver_exit_code": proc.returncode, "stop_reason": stop,
              "solver_status_lines": statuses, "model_lines": model_lines,
              "solver_wall_seconds": time.monotonic() - start,
              "sampled_solver_peak_rss_bytes": peak_rss,
              "xcnf_check": xcnf_check, "relation": relation,
              "verified_relations": 0, "useful_rank": 0,
              "source_sha256": {"protocol": sha(HERE / "hybrid_protocol.json"),
                                "formula": sha(formula), "stdout": sha(out_path),
                                "stderr": sha(err_path)}}
    save(HERE / "query_result.json", result)
    print(json.dumps({"status": status, "solver_wall_seconds": result["solver_wall_seconds"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "preflight", "query"))
    {"freeze": freeze, "preflight": preflight,
     "query": query}[parser.parse_args().mode]()
