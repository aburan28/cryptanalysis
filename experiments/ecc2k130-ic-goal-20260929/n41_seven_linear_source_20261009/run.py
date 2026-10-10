#!/usr/bin/env python3
"""Frozen linear-leaf seven-source public-point SAT experiment."""
import argparse
import hashlib
import importlib.util
import itertools
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "n41_n131_seven_diagonal_20261009"
sys.path.insert(0, str(OLD))
import run as old

spec = importlib.util.spec_from_file_location("linear_source_circuit", HERE / "circuit.py")
method = importlib.util.module_from_spec(spec)
spec.loader.exec_module(method)

SCREEN = old.SCREEN
PUBLIC = old.PUBLIC
RANK = OLD / "sage_rank_audit.json"
HITS = OLD / "join_hits.jsonl"
RUNTIME = HERE / "sage_runtime_info.json"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
PROTOCOL = HERE / "protocol.json"
CONTROL = HERE / "control.json"
R = old.R
ROTATIONS = old.ROTATIONS


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


def setup_base():
    context = old.setup()
    field, curve = context["field"], context["curve"]
    lam = json.loads(RANK.read_text())["frobenius_eigenvalue_mod_r"]
    if (lam*lam + lam + 2) % R or pow(lam, 41, R) != 1:
        raise ValueError("Frobenius eigenvalue changed")
    q = context["public_q"]
    if old.point_frob(field, q, 1) != curve.mul(lam, q):
        raise ValueError("Frobenius eigenvalue fails public point")
    halves = [int(value) for value in context["screen"]["window_basis_halftrace"][0]]
    context["bases_u"] = [[old.frob(field, value, rotation) for value in halves]
                           for rotation in ROTATIONS]
    context["lambda"] = lam
    for block in range(7):
        for mask, pair in context["states"][block].items():
            value = old.base.coordinate(context["bases_u"][block], mask)
            if value in (0, 1) or any(old.transformed(field, row["raw_leaves"][0]) != value
                                     for row in pair):
                raise ValueError("source coordinate is not linear in mask")
    return context


def transformed_target(context):
    curve, q = context["curve"], context["public_q"]
    qprime = curve.mul(pow(1 + context["lambda"], -1, R), q)
    if (qprime is None or curve.mul(R, qprime) is not None or
            curve.add(qprime, old.point_frob(context["field"], qprime, 1)) != q):
        raise ValueError("one-plus-Frobenius target transport failed")
    return qprime


def source_chain(context, masks, signs):
    rows = [context["states"][i][mask][sign]
            for i, (mask, sign) in enumerate(zip(masks, signs))]
    leaves = [row["raw_leaves"][0] for row in rows]
    middle, total = old.chain(context["curve"], leaves)
    return rows, leaves, middle, total


def control_from_hit(context, qprime):
    hit = json.loads(HITS.read_text().splitlines()[0])
    rows, leaves, middle, total = source_chain(context, hit["masks"], hit["signs"])
    targets = old.base.target_preimages(context["field"], context["curve"], qprime)
    if total not in targets or context["curve"].mul(4, total) != qprime:
        raise ValueError("frozen public relation failed target transport")
    values = [old.transformed(context["field"], p) for p in [*leaves, *middle, total]]
    if any(value in (None, 0, 1) for value in values):
        raise ValueError("public relation has exceptional transformed coordinate")
    return {"kind": "known_relation_formula_control", "masks": hit["masks"],
            "signs": hit["signs"], "folded_columns": [row["column"] for row in rows],
            "raw_leaves": [list(point) for point in leaves],
            "raw_sum": list(total), "target_qprime": list(qprime),
            "target_preimage_index": targets.index(total),
            "leaf_u": values[:7], "middle_u": values[7:12]}


def frozen_files():
    return {"run": Path(__file__), "circuit": Path(method.__file__),
            "old_run": OLD / "run.py", "base": Path(old.base.__file__),
            "witness": Path(old.witness_tools.__file__), "screen": SCREEN,
            "public": PUBLIC, "rank": RANK, "hits": HITS,
            "runtime": RUNTIME, "solver": SOLVER, "control": CONTROL}


def freeze():
    if PROTOCOL.exists() or CONTROL.exists():
        raise FileExistsError("preserve first protocol and control")
    if json.loads(RUNTIME.read_text()).get("status") != "verified":
        raise ValueError("checked Sage runtime receipt missing")
    context = setup_base()
    qprime = transformed_target(context)
    control = control_from_hit(context, qprime)
    save(CONTROL, control)
    protocol = {
        "kind": "n41_seven_linear_source_public_query", "status": "FROZEN_BEFORE_MEASUREMENT",
        "proposal_id": "Q20261009175000", "candidate_id": None, "run_id": None,
        "curve_id": context["screen"]["curve_id"],
        "public_target_q": list(context["public_q"]),
        "transported_target_qprime": list(qprime),
        "lambda_mod_r": context["lambda"], "summands": 7,
        "source_mask_count": len(context["columns"]),
        "actual_factor_base_points_B": context["actual_factor_base_points_B"],
        "effective_folded_columns_K": context["folded_columns_K"],
        "rotations": list(ROTATIONS), "target_count": 1,
        "online_cap_seconds": 120, "solver_parent_wall_cap_seconds": 115,
        "rss_cap_bytes": 4*1024**3, "workers": 1,
        "solver_flags": ["--threads=1", "--xor=0", "--printsol=1",
                         "--random=20261009", "--maxconfl=2000000"],
        "input_law": "one frozen public subgroup point; no source selector pinned in the measured formula",
        "model_rule": "saved XCNF, seven distinct folded columns, raw seven-source group sum, cofactor-four target, independent Sage replay",
        "source_sha256": {name: sha(path) for name, path in frozen_files().items()},
    }
    save(PROTOCOL, protocol)
    print(json.dumps({"status": protocol["status"], "qprime": qprime,
                      "B": protocol["actual_factor_base_points_B"],
                      "K": protocol["effective_folded_columns_K"]}))


def verify_freeze():
    protocol = json.loads(PROTOCOL.read_text())
    if (protocol["status"] != "FROZEN_BEFORE_MEASUREMENT" or
            protocol["source_sha256"] != {name: sha(path) for name, path in frozen_files().items()} or
            json.loads(RUNTIME.read_text()).get("status") != "verified"):
        raise ValueError("source or runtime drift")
    return protocol


def build_formula(folder, context, qprime):
    began = time.monotonic()
    field, curve = context["field"], context["curve"]
    raw_targets = old.base.target_preimages(field, curve, qprime)
    target_us = [old.transformed(field, point) for point in raw_targets]
    preimages_seconds = time.monotonic() - began
    circuit = old.base.KaratsubaCircuit(41, [0, 3])
    meta = method.build(circuit, context["bases_u"],
                        [context["columns"]]*7, target_us)
    formula = folder / "system.xcnf"
    circuit.write(formula)
    stats = {"variables": circuit.next_var-1,
             "clauses": len(circuit.clauses), "xor_rows": len(circuit.xors),
             "and_gates": circuit.and_count,
             "duplicate_column_clauses": meta["duplicate_column_clauses"],
             "bytes": formula.stat().st_size, "sha256": sha(formula)}
    return circuit, meta, raw_targets, formula, stats, {
        "target_preimages_seconds": preimages_seconds,
        "target_formula_seconds": time.monotonic() - began - preimages_seconds}


def bits(model, row):
    return sum((int(wire == -1) if wire in (0, -1) else int(model[wire])) << bit
               for bit, wire in enumerate(row))


def decode(model, meta, context, qprime, raw_targets):
    masks = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
             for row in meta["masks"]]
    flags = [i for i, wire in enumerate(meta["flags"]) if model[wire]]
    if len(flags) != 1 or any(mask not in context["columns"] for mask in masks):
        return {"valid": False, "reason": "mask_or_target_flag", "masks": masks}
    columns = [context["columns"][mask] for mask in masks]
    if len(set(columns)) != 7:
        return {"valid": False, "reason": "folded_column_collision", "masks": masks}
    expected_leaves = [bits(model, row) for row in meta["leaves"]]
    expected_middle = [bits(model, row) for row in meta["middle"]]
    field, curve = context["field"], context["curve"]
    for signs in itertools.product((0, 1), repeat=7):
        rows, leaves, middle, total = source_chain(context, masks, signs)
        if ([old.transformed(field, point) for point in leaves] != expected_leaves or
                [old.transformed(field, point) for point in middle] != expected_middle or
                total != raw_targets[flags[0]] or curve.mul(4, total) != qprime):
            continue
        return {"valid": True, "masks": masks, "signs": list(signs),
                "folded_columns": columns, "target_preimage_index": flags[0],
                "raw_leaves": [list(point) for point in leaves],
                "raw_sum": list(total), "target_qprime": list(qprime)}
    return {"valid": False, "reason": "group_chain", "masks": masks,
            "target_preimage_index": flags[0]}


def preflight():
    verify_freeze()
    folder = HERE / "preflight"
    folder.mkdir(exist_ok=False)
    context = setup_base()
    qprime = transformed_target(context)
    control = json.loads(CONTROL.read_text())
    circuit, meta, raw_targets, formula, stats, phases = build_formula(folder, context, qprime)
    initial = {}
    for row, mask in zip(meta["masks"], control["masks"]):
        initial.update({wire: mask >> bit & 1 for bit, wire in enumerate(row)})
    for i, wire in enumerate(meta["flags"]):
        initial[wire] = int(i == control["target_preimage_index"])
    for row, value in zip(meta["middle"], control["middle_u"]):
        initial.update({wire: value >> bit & 1 for bit, wire in enumerate(row)})
    if len(initial) != meta["primary_variables"]:
        raise ValueError("control does not assign all primary variables")
    model = old.witness_tools.complete_assignment(circuit, initial)
    check = old.base.check_xcnf(formula, model)
    relation = decode(model, meta, context, qprime, raw_targets)
    if (not relation["valid"] or relation["masks"] != control["masks"] or
            relation["signs"] != control["signs"]):
        raise ValueError("control group replay mismatch")
    receipt = {"status": "PASS_FULL_FORMULA_AND_GROUP_CONTROL",
               "formula": stats, "phase_seconds": phases,
               "xcnf_check": check, "relation": relation,
               "protocol_sha256": sha(PROTOCOL), "control_sha256": sha(CONTROL)}
    save(folder / "receipt.json", receipt)
    print(json.dumps({"status": receipt["status"], "formula": stats}))


def query():
    protocol = verify_freeze()
    receipt = json.loads((HERE / "preflight/receipt.json").read_text())
    if receipt["status"] != "PASS_FULL_FORMULA_AND_GROUP_CONTROL":
        raise ValueError("control missing")
    folder = HERE / "public"
    folder.mkdir(exist_ok=False)
    context = setup_base()
    q = context["public_q"]
    online_start = time.monotonic()
    qprime = transformed_target(context)
    target_transport_seconds = time.monotonic() - online_start
    circuit, meta, raw_targets, formula, stats, phases = build_formula(folder, context, qprime)
    if stats["sha256"] != receipt["formula"]["sha256"]:
        raise ValueError("public formula changed from known-assignment control")
    build_wall = time.monotonic() - online_start
    remaining = protocol["online_cap_seconds"] - build_wall - 1
    if remaining <= 2:
        raise TimeoutError("formula construction exhausted online cap")
    solver_cap = min(protocol["solver_parent_wall_cap_seconds"], remaining)
    command = [str(SOLVER), *protocol["solver_flags"],
               f"--maxtime={max(1, int(solver_cap)-2)}", str(formula)]
    stdout_path, stderr_path = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
    parent = psutil.Process(os.getpid())
    peak_rss = peak_cpu = 0
    stop_reason = None
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        proc = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
        child = psutil.Process(proc.pid)
        save(folder / "process.json", {"pid": proc.pid,
             "create_time_epoch": child.create_time(), "command": command,
             "started_utc": datetime.now(timezone.utc).isoformat()})
        while proc.poll() is None:
            try:
                cpu = child.cpu_times()
                peak_cpu = max(peak_cpu, cpu.user + cpu.system)
                peak_rss = max(peak_rss, child.memory_info().rss + parent.memory_info().rss)
            except psutil.NoSuchProcess:
                pass
            if peak_rss > protocol["rss_cap_bytes"]:
                stop_reason = "RSS_CAP"
                proc.terminate()
                break
            if time.monotonic()-online_start >= protocol["online_cap_seconds"]:
                stop_reason = "ONLINE_WALL_CAP"
                proc.terminate()
                break
            if time.monotonic()-online_start-build_wall >= solver_cap:
                stop_reason = "SOLVER_WALL_CAP"
                proc.terminate()
                break
            time.sleep(.1)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            stop_reason = (stop_reason or "DRAIN_TIMEOUT") + "_KILLED"
    solver_wall = time.monotonic()-online_start-build_wall
    output = stdout_path.read_text(errors="replace")
    statuses = [line for line in output.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in output.splitlines())
    relation = check = None
    replay_seconds = 0.0
    if statuses == ["s SATISFIABLE"] and model_lines:
        began = time.monotonic()
        model = old.base.read_model(output, stats["variables"])
        check = old.base.check_xcnf(formula, model)
        relation = decode(model, meta, context, qprime, raw_targets)
        replay_seconds = time.monotonic()-began
        status = "SAT_MODEL_PENDING_INDEPENDENT_SAGE" if relation["valid"] else "INVALID_MODEL"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "UNSAT_FORMULA"
    elif stop_reason in ("ONLINE_WALL_CAP", "SOLVER_WALL_CAP") or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    elif stop_reason == "RSS_CAP":
        status = "OOM"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    result = {"kind": "n41_seven_linear_source_public_query", "status": status,
              "proposal_id": protocol["proposal_id"], "candidate_id": None, "run_id": None,
              "curve_id": protocol["curve_id"], "target_count": 1,
              "public_target_q": list(q), "transported_target_qprime": list(qprime),
              "formula": stats, "solver_status_lines": statuses, "model_lines": model_lines,
              "solver_command": command, "solver_exit_code": proc.returncode,
              "stop_reason": stop_reason,
              "phase_seconds": {"target_transport": target_transport_seconds,
                                **phases, "solver": solver_wall,
                                "producer_relation_check": replay_seconds,
                                "online_wall": time.monotonic()-online_start},
              "sampled_peak_combined_rss_bytes": peak_rss,
              "sampled_solver_cpu_seconds": peak_cpu,
              "producer_xcnf_check": check, "producer_relation": relation,
              "verified_relations": 0, "useful_rank": 0,
              "source_sha256": {"protocol": sha(PROTOCOL), "formula": sha(formula),
                                "stdout": sha(stdout_path), "stderr": sha(stderr_path),
                                "process": sha(folder / "process.json")}}
    save(folder / "result.json", result)
    print(json.dumps({"status": status,
                      "online_wall_seconds": result["phase_seconds"]["online_wall"],
                      "formula": stats}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "preflight", "query"))
    mode = parser.parse_args().mode
    {"freeze": freeze, "preflight": preflight, "query": query}[mode]()
