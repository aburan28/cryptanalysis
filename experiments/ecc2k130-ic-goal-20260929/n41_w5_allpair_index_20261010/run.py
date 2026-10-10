#!/usr/bin/env python3
"""Freeze and test an exact five-pair indexed N41 public-point formula."""

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
PRIOR = ROOT / "n41_w5_pair_index_20261010"
SAMEPAIR = ROOT / "n41_w5_samepair_hybrid_20261010"
SOURCE = ROOT / "n41_w5_ten_source_gate_20261010"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


single = load("n41_single_pair_index_runner_for_all_five", PRIOR / "run.py")
allpairs = load("n41_all_five_pair_index_circuit", HERE / "circuit.py")
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open("x") as out:
        json.dump(value, out, indent=2, sort_keys=True)
        out.write("\n")


def sources():
    return {"runner": Path(__file__), "circuit": HERE / "circuit.py",
            "single_runner": PRIOR / "run.py",
            "single_circuit": PRIOR / "circuit.py",
            "pair_index": PRIOR / "pair_index.json",
            "pair_index_sage_audit": PRIOR / "sage_index_audit.json",
            "samepair_hit": SAMEPAIR / "run/hits.jsonl",
            "samepair_sage_audit": SAMEPAIR / "sage_audit.json",
            "geometry": SOURCE / "geometry_result.json",
            "runtime": HERE / "sage_runtime_info.json",
            "solver": SOLVER}


def context_and_witness():
    ctx = single.context()
    entries = single.inputs()
    hit = json.loads((SAMEPAIR / "run/hits.jsonl").read_text().strip())
    masks, signs = list(hit["masks"]), list(hit["signs"])
    for i in range(5):
        if masks[2*i] > masks[2*i+1]:
            masks[2*i], masks[2*i+1] = masks[2*i+1], masks[2*i]
            signs[2*i], signs[2*i+1] = signs[2*i+1], signs[2*i]
    assert all(masks[2*i] < masks[2*i+1] for i in range(5))
    leaves, middle, total = single.old.chain(ctx, masks, signs)
    assert single.old.regular(ctx, [*leaves, *middle, total])
    assert list(total) == hit["raw_sum"]
    qprime = single.old.qprime_of(ctx, ctx["q"])
    targets = single.old.old.base.target_preimages(ctx["field"], ctx["curve"], qprime)
    assert total == targets[hit["target_preimage_index"]]
    selectors = []
    for pair in range(5):
        rotation = allpairs.ROTATIONS[2*pair]
        z_global = single.old.old.transformed(ctx["field"], middle[pair])
        z_local = allpairs.method.frob(ctx["field"], z_global,
                                       (41 - rotation) % 41)
        signature = (masks[2*pair], masks[2*pair+1], z_local)
        selector = next(i for i, entry in enumerate(entries)
                        if (entry["mask_a"], entry["mask_b"], entry["z_local"])
                        == signature)
        selectors.append(selector)
    return ctx, entries, hit, masks, signs, middle, targets, selectors


def build(ctx, targets, entries):
    target_us = [single.old.old.transformed(ctx["field"], point)
                 for point in targets]
    circuit = single.old.old.base.KaratsubaCircuit(41, [0, 3])
    meta = allpairs.build(circuit, ctx["field"], ctx["geometry"],
                          target_us, entries)
    return circuit, meta


def stats(circuit, path):
    return {"variables": circuit.next_var - 1,
            "clauses": len(circuit.clauses), "xor_rows": len(circuit.xors),
            "and_gates": circuit.and_count,
            "bytes": Path(path).stat().st_size, "sha256": sha(path)}


def freeze():
    ctx, entries, hit, masks, signs, middle, targets, selectors = context_and_witness()
    assert len(entries) == 264 and len(selectors) == 5
    record = {"status": "FROZEN_BEFORE_ALL_PAIR_FORMULA_AND_QUERIES",
              "kind": "n41_w5_five_exact_pair_output_indices",
              "candidate_id": None,
              "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
              "public_target_q": [1458168294740, 1672312028033],
              "target_count": 1, "summands": 10, "source_width": 5,
              "rotations": list(allpairs.ROTATIONS),
              "actual_factor_base_points_B": 170,
              "folded_columns_K": 14,
              "entries_per_pair": 264,
              "known_relation_selectors": selectors,
              "caps_seconds": {"all_fixed": 20, "four_fixed": 45,
                               "public": 120},
              "rss_cap_bytes": 4 * 1024**3, "workers": 1,
              "solver_flags": ["--threads=1", "--xor=0", "--printsol=1",
                               "--random=20261010"],
              "source_sha256": {name: sha(path) for name, path in sources().items()}}
    save(HERE / "protocol.json", record)
    print(json.dumps({"status": record["status"],
                      "known_selectors": selectors}))


def verify():
    record = json.loads((HERE / "protocol.json").read_text())
    assert record["status"] == "FROZEN_BEFORE_ALL_PAIR_FORMULA_AND_QUERIES"
    assert record["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    return record


def preflight():
    protocol = verify()
    ctx, entries, hit, masks, signs, middle, targets, selected = context_and_witness()
    started = time.monotonic()
    circuit, meta = build(ctx, targets, entries)
    formula = HERE / "public_allpair.xcnf"
    circuit.write(formula)
    initial = {}
    for row, mask in zip(meta["masks"], masks):
        initial.update({wire: mask >> i & 1 for i, wire in enumerate(row)})
    for i, wire in enumerate(meta["flags"]):
        initial[wire] = int(i == hit["target_preimage_index"])
    for row, point in zip(meta["middle"], middle):
        value = single.old.old.transformed(ctx["field"], point)
        initial.update({wire: value >> i & 1 for i, wire in enumerate(row)})
    for pair in range(5):
        for i, wire in enumerate(meta["pair_selectors"][pair]):
            initial[wire] = int(i == selected[pair])
        for i, wire in enumerate(meta["pair_sequences"][pair]):
            initial[wire] = int(selected[pair] <= i)
    assignment = single.old.old.witness_tools.complete_assignment(circuit, initial)
    checks = {}
    formulas = {}
    def inspect(label, path):
        circuit.write(path)
        checks[label] = single.old.old.base.check_xcnf(path, assignment)
        formulas[label] = stats(circuit, path)
    checks["public"] = single.old.old.base.check_xcnf(formula, assignment)
    formulas["public"] = stats(circuit, formula)
    decoded = single.old.decode(assignment, meta, ctx,
                                single.old.qprime_of(ctx, ctx["q"]), targets)
    assert decoded["valid"] and decoded["masks"] == masks
    for pair in range(4):
        circuit.clauses.append(f"{meta['pair_selectors'][pair][selected[pair]]} 0")
    inspect("four_fixed", HERE / "four_fixed.xcnf")
    circuit.clauses.append(f"{meta['pair_selectors'][4][selected[4]]} 0")
    inspect("all_fixed", HERE / "all_fixed.xcnf")
    receipt = {"status": "PASS_FULL_FIVE_PAIR_INDEX_CONTROLS",
               "candidate_id": None, "curve_id": protocol["curve_id"],
               "public_target_q": protocol["public_target_q"],
               "formulas": formulas, "xcnf_checks": checks,
               "known_selectors": selected,
               "known_relation": decoded,
               "build_and_check_wall_seconds": time.monotonic() - started,
               "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                                 "index": sha(PRIOR / "pair_index.json"),
                                 **{name + "_formula": value["sha256"]
                                    for name, value in formulas.items()}}}
    save(HERE / "preflight.json", receipt)
    print(json.dumps({"status": receipt["status"],
                      "public_formula": formulas["public"]}))


def query(mode):
    protocol = verify()
    preflight = json.loads((HERE / "preflight.json").read_text())
    assert preflight["status"] == "PASS_FULL_FIVE_PAIR_INDEX_CONTROLS"
    formula = HERE / {"all_fixed": "all_fixed.xcnf",
                      "four_fixed": "four_fixed.xcnf",
                      "public": "public_allpair.xcnf"}[mode]
    fstats = preflight["formulas"][mode]
    assert fstats["sha256"] == sha(formula)
    folder = HERE / (mode + "_query")
    folder.mkdir(exist_ok=False)
    cap = protocol["caps_seconds"][mode]
    command = [str(SOLVER), *protocol["solver_flags"],
               f"--maxtime={cap-2}", str(formula)]
    out_path, err_path = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
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
    output = out_path.read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in output.splitlines())
    relation = xcnf_check = selected = None
    if statuses == ["s SATISFIABLE"] and model_lines:
        model = single.old.old.base.read_model(output, fstats["variables"])
        xcnf_check = single.old.old.base.check_xcnf(formula, model)
        ctx, entries, _, _, _, _, targets, _ = context_and_witness()
        _, meta = build(ctx, targets, entries)
        selected = [[i for i, wire in enumerate(row) if model[wire]]
                    for row in meta["pair_selectors"]]
        relation = single.old.decode(model, meta, ctx,
                                     single.old.qprime_of(ctx, ctx["q"]), targets)
        valid = relation["valid"] and all(len(row) == 1 for row in selected)
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
              "target_count": 1, "mode": mode,
              "solver_command": command, "solver_exit_code": proc.returncode,
              "solver_status_lines": statuses, "model_lines": model_lines,
              "stop_reason": stop, "solver_wall_seconds": time.monotonic() - start,
              "sampled_solver_peak_rss_bytes": peak_rss,
              "selected_indices": selected, "xcnf_check": xcnf_check,
              "relation": relation, "verified_relations": 0,
              "useful_rank": 0,
              "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                                "formula": sha(formula), "stdout": sha(out_path),
                                "stderr": sha(err_path)}}
    save(folder / "result.json", result)
    print(json.dumps({"status": status, "mode": mode,
                      "solver_wall_seconds": result["solver_wall_seconds"],
                      "selected_indices": selected}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "preflight", "all_fixed",
                                         "four_fixed", "public"))
    mode = parser.parse_args().mode
    {"freeze": freeze, "preflight": preflight,
     "all_fixed": lambda: query("all_fixed"),
     "four_fixed": lambda: query("four_fixed"),
     "public": lambda: query("public")}[mode]()
