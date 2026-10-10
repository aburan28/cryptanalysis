#!/usr/bin/env python3
"""Frozen N41 control for seven rational Frobenius-diagonal pair blocks."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import check_n41_lowpower_w8_s6_witness as witness_tools
import run_n41_disjoint_s5_sat as base
import circuit as method

SCREEN = ROOT / "n131_w18_four_pairs/screen.json"
PUBLIC = ROOT / "n41_adjacent_pairpair/public_target.json"
RUNTIME = HERE / "sage_runtime_info.json"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
PROTOCOL = HERE / "protocol.json"
PLANTED = HERE / "planted.json"
ROTATIONS = (0, 6, 12, 18, 24, 30, 36)
SEED = 20261009172341
R = 549756390943


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def save(path, value):
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def frob(field, value, rotation):
    for _ in range(rotation):
        value = field.mul(value, value)
    return value


def point_frob(field, point, rotation):
    return tuple(frob(field, value, rotation) for value in point)


def transformed(field, point):
    if point is None or point[0] == 1:
        return None
    return field.inv(point[0] ^ 1)


def setup():
    screen = json.loads(SCREEN.read_text())["n41"]
    public = json.loads(PUBLIC.read_text())
    if (screen["curve_id"] != public["curve_id"] or
            screen["subgroup_order"] != R or
            screen["public_target_q"] != public["target_q"]):
        raise ValueError("frozen N41 curve or public target mismatch")
    field = base.Field(41, [0, 3])
    curve = base.Curve(field, 0)
    basis = [int(value) for value in screen["window_basis_w"][0]]
    halves = [int(value) for value in screen["window_basis_halftrace"][0]]
    rows = screen["point_rows_by_unique_rotation"]["0"]
    columns = {}
    source = {}
    for x, y, column, mask, branch, sign in rows:
        if branch != 0 or sign not in (0, 1):
            raise ValueError("unexpected base-point branch")
        if mask in columns and columns[mask] != column:
            raise ValueError("mask column changed")
        columns[mask] = column
        u = base.coordinate(halves, mask)
        if u in (0, 1):
            raise ValueError("exceptional raw source coordinate")
        raw_x = 1 ^ field.inv(u)
        raw_options = base.points_with_x(curve, raw_x)
        matching = [tuple(point) for point in raw_options
                    if curve.mul(4, tuple(point)) == (int(x), int(y))]
        if len(matching) != 1:
            raise ValueError("projected screen point lacks one raw lift")
        source.setdefault(mask, {})[sign] = matching[0]
    if len(columns) != 32 or len(set(columns.values())) != 26 or any(
            set(row) != {0, 1} for row in source.values()):
        raise ValueError("source mask or sign geometry changed")
    bases_w = [[frob(field, value, rotation) for value in basis]
               for rotation in ROTATIONS]
    states = []
    usable_points = set()
    for block, rotation in enumerate(ROTATIONS):
        by_mask = {}
        for mask in sorted(columns):
            row = []
            w = base.coordinate(bases_w[block], mask)
            if w in (0, 1):
                raise ValueError("exceptional diagonal w")
            for sign in (0, 1):
                p = point_frob(field, source[mask][sign], rotation)
                fp = point_frob(field, p, 1)
                if not curve.on_curve(p) or not curve.on_curve(fp):
                    raise ValueError("Frobenius source point off curve")
                total = curve.add(p, fp)
                if total is None or total[0] != field.inv(w):
                    raise ValueError("diagonal rational identity failed")
                z = transformed(field, total)
                if z is None or field.mul(z, w ^ 1) != w:
                    raise ValueError("transformed diagonal identity failed")
                projected = curve.mul(4, total)
                if projected is None or curve.mul(R, projected) is not None:
                    raise ValueError("diagonal output outside prime subgroup")
                usable_points.add(curve.mul(4, p))
                usable_points.add(curve.mul(4, fp))
                row.append({"point": total, "raw_leaves": (p, fp),
                            "projected": projected, "z": z,
                            "mask": mask, "sign": sign,
                            "column": columns[mask]})
            if row[0]["point"] != curve.neg(row[1]["point"]):
                raise ValueError("source sign branches are not negatives")
            by_mask[mask] = row
        states.append(by_mask)
    return {"field": field, "curve": curve, "screen": screen,
            "public_q": tuple(public["target_q"]), "bases_w": bases_w,
            "columns": columns, "states": states,
            "actual_factor_base_points_B": len(usable_points),
            "folded_columns_K": len(set(columns.values()))}


def chain(curve, points):
    middle = [curve.add(points[0], points[1]),
              curve.add(points[2], points[3]),
              curve.add(points[4], points[5])]
    middle.append(curve.add(middle[0], middle[1]))
    middle.append(curve.add(middle[3], middle[2]))
    total = curve.add(middle[4], points[6])
    return middle, total


def make_planted(context):
    rng = random.Random(SEED)
    by_column = {}
    for mask, column in context["columns"].items():
        by_column.setdefault(column, []).append(mask)
    field, curve = context["field"], context["curve"]
    for attempt in range(10000):
        selected_columns = rng.sample(sorted(by_column), method.BLOCKS)
        masks = [rng.choice(by_column[column]) for column in selected_columns]
        signs = [rng.randrange(2) for _ in masks]
        states = [context["states"][i][mask][sign]
                  for i, (mask, sign) in enumerate(zip(masks, signs))]
        middle, total = chain(curve, [row["point"] for row in states])
        if any(transformed(field, point) in (None, 0, 1)
               for point in [*middle, total]):
            continue
        q = curve.mul(4, total)
        if q is None:
            continue
        raw_targets = base.target_preimages(field, curve, q)
        return {"kind": "n41_seven_diagonal_planted_formula_control",
                "attempt": attempt, "seed": SEED, "masks": masks,
                "signs": signs, "folded_columns": selected_columns,
                "raw_leaves": [[list(p) for p in row["raw_leaves"]] for row in states],
                "diagonal_points": [list(row["point"]) for row in states],
                "leaf_u": [row["z"] for row in states],
                "middle_u": [transformed(field, point) for point in middle],
                "raw_sum": list(total), "target_q": list(q),
                "target_preimage_index": raw_targets.index(total)}
    raise RuntimeError("could not construct nonexceptional diagonal control")


def freeze():
    if PROTOCOL.exists() or PLANTED.exists():
        raise FileExistsError("preserve first protocol and control")
    runtime = json.loads(RUNTIME.read_text())
    if runtime.get("status") != "verified":
        raise ValueError("checked Sage runtime missing")
    context = setup()
    planted = make_planted(context)
    save(PLANTED, planted)
    protocol = {
        "kind": "n41_seven_frobenius_diagonal_public_query_protocol",
        "status": "FROZEN_BEFORE_MEASUREMENT",
        "proposal_id": "Q20261009172341", "candidate_id": None, "run_id": None,
        "curve_id": context["screen"]["curve_id"],
        "public_target_q": list(context["public_q"]),
        "target_count": 1, "summands": 14, "diagonal_blocks": 7,
        "source_mask_count": len(context["columns"]),
        "actual_factor_base_points_B": context["actual_factor_base_points_B"],
        "effective_folded_columns_K": context["folded_columns_K"],
        "rotations": list(ROTATIONS), "same_sign_only": True,
        "online_cap_seconds": 120, "solver_parent_wall_cap_seconds": 115,
        "rss_cap_bytes": 4 * 1024**3, "workers": 1,
        "solver_flags": ["--threads=1", "--xor=0", "--printsol=1",
                         "--random=20261009172341", "--maxconfl=2000000"],
        "input_law": "one frozen public subgroup point, unrelated to the planted control",
        "model_rule": "saved XCNF, seven distinct folded columns, fourteen raw leaves, cofactor-four target sum and independent Sage replay",
        "source_sha256": {"run": sha(Path(__file__)), "circuit": sha(method.__file__),
                          "base": sha(base.__file__), "witness": sha(witness_tools.__file__),
                          "screen": sha(SCREEN), "public": sha(PUBLIC),
                          "runtime": sha(RUNTIME), "solver": sha(SOLVER),
                          "planted": sha(PLANTED)},
    }
    save(PROTOCOL, protocol)
    print(json.dumps({"status": protocol["status"],
                      "B": protocol["actual_factor_base_points_B"],
                      "K": protocol["effective_folded_columns_K"],
                      "planted_attempt": planted["attempt"]}))


def verify_freeze():
    protocol = json.loads(PROTOCOL.read_text())
    files = {"run": Path(__file__), "circuit": Path(method.__file__),
             "base": Path(base.__file__), "witness": Path(witness_tools.__file__),
             "screen": SCREEN, "public": PUBLIC, "runtime": RUNTIME,
             "solver": SOLVER, "planted": PLANTED}
    if (protocol["status"] != "FROZEN_BEFORE_MEASUREMENT" or
            {name: sha(path) for name, path in files.items()} != protocol["source_sha256"] or
            json.loads(RUNTIME.read_text()).get("status") != "verified"):
        raise ValueError("source, runtime, or protocol drift")
    return protocol


def build_formula(folder, context, q):
    field, curve = context["field"], context["curve"]
    began = time.monotonic()
    raw_targets = base.target_preimages(field, curve, q)
    target_us = [transformed(field, point) for point in raw_targets]
    target_seconds = time.monotonic() - began
    circuit = base.KaratsubaCircuit(41, [0, 3])
    meta = method.build(circuit, context["bases_w"],
                        [context["columns"]] * method.BLOCKS, target_us)
    formula = folder / "system.xcnf"
    circuit.write(formula)
    total_seconds = time.monotonic() - began
    stats = {"variables": circuit.next_var - 1,
             "clauses": len(circuit.clauses), "xor_rows": len(circuit.xors),
             "and_gates": circuit.and_count,
             "duplicate_column_clauses": meta["duplicate_column_clauses"],
             "bytes": formula.stat().st_size, "sha256": sha(formula)}
    return circuit, meta, raw_targets, formula, stats, {
        "target_preimages_seconds": target_seconds,
        "target_formula_seconds": total_seconds - target_seconds}


def decode(model, meta, context, q, raw_targets):
    masks = [sum(1 << bit for bit, wire in enumerate(row) if model[wire])
             for row in meta["masks"]]
    flags = [i for i, wire in enumerate(meta["flags"]) if model[wire]]
    if len(flags) != 1 or any(mask not in context["columns"] for mask in masks):
        return {"valid": False, "reason": "mask_or_endpoint", "masks": masks}
    columns = [context["columns"][mask] for mask in masks]
    if len(set(columns)) != method.BLOCKS:
        return {"valid": False, "reason": "folded_column_collision", "masks": masks}
    bit_values = lambda rows: [sum(int(model[wire]) << bit
                                   for bit, wire in enumerate(row)) for row in rows]
    expected_leaves = bit_values(meta["leaves"])
    expected_middle = bit_values(meta["middle"])
    field, curve = context["field"], context["curve"]
    for signs in itertools.product((0, 1), repeat=method.BLOCKS):
        states = [context["states"][i][masks[i]][signs[i]]
                  for i in range(method.BLOCKS)]
        if [row["z"] for row in states] != expected_leaves:
            continue
        middle, total = chain(curve, [row["point"] for row in states])
        if (total != raw_targets[flags[0]] or
                [transformed(field, point) for point in middle] != expected_middle or
                curve.mul(4, total) != q):
            continue
        return {"valid": True, "masks": masks, "signs": list(signs),
                "folded_columns": columns, "target_preimage_index": flags[0],
                "diagonal_points": [list(row["point"]) for row in states],
                "raw_leaves": [[list(p) for p in row["raw_leaves"]] for row in states],
                "raw_sum": list(total), "target_q": list(q),
                "leaf_u": expected_leaves, "middle_u": expected_middle}
    return {"valid": False, "reason": "group_chain", "masks": masks,
            "target_preimage_index": flags[0]}


def preflight():
    verify_freeze()
    folder = HERE / "preflight"
    folder.mkdir(exist_ok=False)
    context = setup()
    planted = json.loads(PLANTED.read_text())
    q = tuple(planted["target_q"])
    circuit, meta, raw_targets, formula, stats, phases = build_formula(folder, context, q)
    initial = {}
    for row, mask in zip(meta["masks"], planted["masks"]):
        initial.update({wire: mask >> bit & 1 for bit, wire in enumerate(row)})
    for index, wire in enumerate(meta["flags"]):
        initial[wire] = int(index == planted["target_preimage_index"])
    for rows, values in ((meta["leaves"], planted["leaf_u"]),
                         (meta["middle"], planted["middle_u"])):
        for row, value in zip(rows, values):
            initial.update({wire: value >> bit & 1 for bit, wire in enumerate(row)})
    if len(initial) != meta["primary_variables"]:
        raise ValueError("planted control did not assign all primary wires")
    assignment = witness_tools.complete_assignment(circuit, initial)
    xcnf_check = base.check_xcnf(formula, assignment)
    relation = decode(assignment, meta, context, q, raw_targets)
    if (not relation["valid"] or relation["raw_leaves"] != planted["raw_leaves"] or
            relation["raw_sum"] != planted["raw_sum"]):
        raise ValueError("planted relation replay mismatch")
    receipt = {"status": "PASS_FULL_FORMULA_AND_GROUP_CONTROL",
               "formula": stats, "phase_seconds": phases,
               "xcnf_check": xcnf_check, "relation": relation,
               "protocol_sha256": sha(PROTOCOL), "planted_sha256": sha(PLANTED)}
    save(folder / "receipt.json", receipt)
    print(json.dumps({"status": receipt["status"], "formula": stats}))


def query():
    protocol = verify_freeze()
    if json.loads((HERE / "preflight/receipt.json").read_text())["status"] != "PASS_FULL_FORMULA_AND_GROUP_CONTROL":
        raise ValueError("full planted control has not passed")
    folder = HERE / "public"
    folder.mkdir(exist_ok=False)
    context = setup()
    q = context["public_q"]
    online_start = time.monotonic()
    circuit, meta, raw_targets, formula, stats, build_phases = build_formula(folder, context, q)
    build_wall = time.monotonic() - online_start
    remaining = protocol["online_cap_seconds"] - build_wall - 1
    if remaining <= 2:
        raise TimeoutError("formula construction exhausted public online cap")
    solver_cap = min(protocol["solver_parent_wall_cap_seconds"], remaining)
    command = [str(SOLVER), *protocol["solver_flags"],
               f"--maxtime={max(1, int(solver_cap)-2)}", str(formula)]
    stdout_path = folder / "solver.stdout.txt"
    stderr_path = folder / "solver.stderr.txt"
    parent = psutil.Process(os.getpid())
    peak_rss = peak_cpu = 0
    stop_reason = None
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        proc = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                start_new_session=True)
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
            if time.monotonic() - online_start >= protocol["online_cap_seconds"]:
                stop_reason = "ONLINE_WALL_CAP"
                proc.terminate()
                break
            if time.monotonic() - online_start - build_wall >= solver_cap:
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
    solver_wall = time.monotonic() - online_start - build_wall
    text = stdout_path.read_text(errors="replace")
    statuses = [line for line in text.splitlines() if line.startswith("s ")]
    model_lines = sum(line.startswith("v ") for line in text.splitlines())
    relation = None
    check = None
    replay_seconds = 0.0
    if statuses == ["s SATISFIABLE"] and model_lines:
        began = time.monotonic()
        model = base.read_model(text, stats["variables"])
        check = base.check_xcnf(formula, model)
        relation = decode(model, meta, context, q, raw_targets)
        replay_seconds = time.monotonic() - began
        status = "SAT_MODEL_PENDING_INDEPENDENT_SAGE" if relation["valid"] else "INVALID_MODEL"
    elif statuses == ["s UNSATISFIABLE"]:
        status = "UNSAT_FORMULA"
    elif stop_reason in ("ONLINE_WALL_CAP", "SOLVER_WALL_CAP") or "s INDETERMINATE" in statuses:
        status = "CENSORED_TIME"
    elif stop_reason == "RSS_CAP":
        status = "OOM"
    else:
        status = "PRODUCER_OR_SOLVER_FAILURE"
    total_online = time.monotonic() - online_start
    result = {"kind": "n41_seven_frobenius_diagonal_public_query",
              "status": status, "proposal_id": protocol["proposal_id"],
              "candidate_id": None, "run_id": None,
              "curve_id": protocol["curve_id"], "target_count": 1,
              "public_target_q": list(q), "formula": stats,
              "solver_status_lines": statuses, "model_lines": model_lines,
              "solver_command": command, "solver_exit_code": proc.returncode,
              "stop_reason": stop_reason, "phase_seconds": {
                  **build_phases, "solver": solver_wall,
                  "producer_relation_check": replay_seconds,
                  "online_wall": total_online},
              "sampled_peak_combined_rss_bytes": peak_rss,
              "sampled_solver_cpu_seconds": peak_cpu,
              "producer_xcnf_check": check, "producer_relation": relation,
              "verified_relations": 0, "useful_rank": 0,
              "source_sha256": {"protocol": sha(PROTOCOL),
                                "formula": sha(formula), "stdout": sha(stdout_path),
                                "stderr": sha(stderr_path),
                                "process": sha(folder / "process.json")}}
    save(folder / "result.json", result)
    print(json.dumps({"status": status, "online_wall_seconds": total_online,
                      "formula": stats}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "preflight", "query"))
    args = parser.parse_args()
    {"freeze": freeze, "preflight": preflight, "query": query}[args.mode]()


if __name__ == "__main__":
    main()
