#!/usr/bin/env python3
"""Frozen six-pair same-rotation N41 formula and bounded public query."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import check_n41_lowpower_w8_s6_witness as witness_tools
import run_n41_disjoint_s5_sat as base
import circuit as method

SCREEN = ROOT / "n131_w18_four_pairs/screen.json"
PUBLIC = ROOT / "n41_adjacent_pairpair/public_target.json"
RUNTIME = HERE / "sage_runtime_info.json"
PROTOCOL = HERE / "protocol.json"
PLANTED = HERE / "planted.json"
N = 41
ROTATIONS = [0, 7, 14, 21, 28, 35]
SEED = 202610091634
CAPS = {"control": 30, "public": 120}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def frob(field, value, rotation):
    for _ in range(rotation):
        value = field.mul(value, value)
    return value


def setup():
    screen = json.loads(SCREEN.read_text())["n41"]
    public = json.loads(PUBLIC.read_text())
    assert screen["curve_id"] == public["curve_id"]
    field = base.Field(N, [0, 3])
    curve = base.Curve(field, 0)
    basis0 = [int(v) for v in screen["window_basis_w"][0]]
    halves0 = [int(v) for v in screen["window_basis_halftrace"][0]]
    columns = {}
    for x, y, column, mask, branch, sign in screen["point_rows_by_unique_rotation"]["0"]:
        assert branch == 0 and sign in (0, 1)
        if mask in columns:
            assert columns[mask] == column
        columns[mask] = column
    assert len(columns) == 32
    bases = []
    halves = []
    maps = []
    for rotation in ROTATIONS:
        row_w = [frob(field, value, rotation) for value in basis0]
        row_h = [frob(field, value, rotation) for value in halves0]
        bases.extend((row_w, row_w))
        halves.extend((row_h, row_h))
        maps.extend((dict(columns), dict(columns)))
    return field, curve, bases, halves, maps, public


def transformed_u(field, point):
    if point is None or point[0] == 1:
        return None
    return field.inv(point[0] ^ 1)


def raw_options(field, curve, half_basis, mask):
    u = base.coordinate(half_basis, mask)
    if u in (0, 1):
        return []
    return [tuple(p) for p in base.points_with_x(curve, 1 ^ field.inv(u))]


def make_planted(context):
    field, curve, bases, halves, maps, public = context
    rng = random.Random(SEED)
    masks_by_column = {}
    for mask, column in maps[0].items():
        masks_by_column.setdefault(column, []).append(mask)
    assert len(masks_by_column) >= 12
    columns = list(masks_by_column)
    for attempt in range(10000):
        selected = rng.sample(columns, 12)
        masks = [rng.choice(masks_by_column[column]) for column in selected]
        options = [raw_options(field, curve, halves[i], mask)
                   for i, mask in enumerate(masks)]
        if any(len(row) != 2 for row in options):
            continue
        points = [rng.choice(row) for row in options]
        pair = [curve.add(points[2*i], points[2*i+1]) for i in range(6)]
        first = [curve.add(pair[2*i], pair[2*i+1]) for i in range(3)]
        second = curve.add(first[0], first[1])
        total = curve.add(second, first[2])
        chain = pair + first + [second, total]
        if any(transformed_u(field, point) in (None, 0, 1) for point in chain):
            continue
        q = curve.mul(4, total)
        if q is None:
            continue
        raw_targets = base.target_preimages(field, curve, q)
        return {"kind": "six_pair_planted_formula_control", "seed": SEED,
                "attempt": attempt, "curve_id": public["curve_id"],
                "seed_masks": masks, "folded_columns": selected,
                "raw_points": [list(point) for point in points],
                "pair_u": [transformed_u(field, point) for point in pair],
                "first_u": [transformed_u(field, point) for point in first],
                "second_u": transformed_u(field, second),
                "raw_sum": list(total), "target_q": list(q),
                "target_preimage_index": raw_targets.index(total)}
    raise RuntimeError("failed to construct a twelve-column control")


def freeze():
    if PROTOCOL.exists() or PLANTED.exists():
        raise FileExistsError("preserve frozen protocol and control")
    context = setup()
    planted = make_planted(context)
    runtime = json.loads(RUNTIME.read_text())
    assert runtime["status"] == "verified"
    write_json(PLANTED, planted)
    protocol = {"kind": "n41_six_pair_same_rotation_sat_protocol",
                "curve_id": planted["curve_id"],
                "public_target_q": context[-1]["target_q"],
                "rotations": ROTATIONS, "width": 6, "summands": 12,
                "cap_seconds": CAPS, "memory_cap_bytes": 4*1024**3,
                "solver": base.CMS, "threads": 1,
                "conflict_cap": {"control": 500000, "public": 2000000},
                "source_sha256": {"run": sha(__file__),
                                  "circuit": sha(method.__file__),
                                  "base": sha(base.__file__),
                                  "witness": sha(witness_tools.__file__),
                                  "screen": sha(SCREEN), "public": sha(PUBLIC),
                                  "runtime": sha(RUNTIME),
                                  "planted": sha(PLANTED)}}
    write_json(PROTOCOL, protocol)
    print(json.dumps({"status": "FROZEN", "planted_attempt": planted["attempt"]}))


def verify_freeze():
    protocol = json.loads(PROTOCOL.read_text())
    files = {"run": Path(__file__), "circuit": Path(method.__file__),
             "base": Path(base.__file__), "witness": Path(witness_tools.__file__),
             "screen": SCREEN, "public": PUBLIC, "runtime": RUNTIME,
             "planted": PLANTED}
    assert {name: sha(path) for name, path in files.items()} == protocol["source_sha256"]
    assert protocol["rotations"] == ROTATIONS and protocol["cap_seconds"] == CAPS
    return protocol


def build_formula(folder, context, q, pinned=None):
    field, curve, bases, halves, maps, _ = context
    start = time.perf_counter_ns()
    raw_targets = base.target_preimages(field, curve, q)
    target_us = [transformed_u(field, point) for point in raw_targets]
    query_ns = time.perf_counter_ns() - start
    circuit = base.KaratsubaCircuit(N, [0, 3])
    meta = method.build(circuit, field, bases, halves, target_us, maps)
    if pinned is not None:
        for row, mask in zip(meta["masks"], pinned["seed_masks"]):
            for bit, wire in enumerate(row):
                circuit.clauses.append(f"{wire if mask & (1 << bit) else -wire} 0")
        for i, wire in enumerate(meta["flags"]):
            circuit.clauses.append(
                f"{wire if i == pinned['target_preimage_index'] else -wire} 0")
    formula = folder / "system.xcnf"
    circuit.write(formula)
    stats = {"variables": circuit.next_var - 1,
             "clauses": len(circuit.clauses), "xor_rows": len(circuit.xors),
             "and_gates": circuit.and_count,
             "duplicate_column_clauses": meta["duplicate_column_clauses"],
             "bytes": formula.stat().st_size, "sha256": sha(formula)}
    return circuit, meta, raw_targets, formula, stats, query_ns


def decode(model, meta, context, q, raw_targets):
    field, curve, bases, halves, maps, _ = context
    masks = [sum((1 << bit) for bit, wire in enumerate(row) if model[wire])
             for row in meta["masks"]]
    flags = [i for i, wire in enumerate(meta["flags"]) if model[wire]]
    if len(flags) != 1 or any(mask not in maps[i] for i, mask in enumerate(masks)):
        return {"valid": False, "reason": "mask_or_flag", "masks": masks}
    columns = [maps[i][mask] for i, mask in enumerate(masks)]
    if len(set(columns)) != 12:
        return {"valid": False, "reason": "duplicate_column", "masks": masks}
    values = lambda rows: [sum(int(model[wire]) << bit
                               for bit, wire in enumerate(row)) for row in rows]
    pair_u = values(meta["pair_outputs"])
    first_u = values(meta["first_level"])
    second_u = values([meta["second_level"]])[0]
    choices = [raw_options(field, curve, halves[i], mask)
               for i, mask in enumerate(masks)]
    if any(len(row) != 2 for row in choices):
        return {"valid": False, "reason": "raw_seed", "masks": masks}
    pair_choices = []
    for i in range(6):
        candidates = []
        for points in itertools.product(choices[2*i], choices[2*i+1]):
            if transformed_u(field, curve.add(*points)) == pair_u[i]:
                candidates.append(points)
        if not candidates:
            return {"valid": False, "reason": "pair_output", "masks": masks}
        pair_choices.append(candidates)
    for pairs in itertools.product(*pair_choices):
        points = [point for pair in pairs for point in pair]
        sums = [curve.add(*pair) for pair in pairs]
        first = [curve.add(sums[2*i], sums[2*i+1]) for i in range(3)]
        second = curve.add(first[0], first[1])
        total = curve.add(second, first[2])
        if ([transformed_u(field, point) for point in first] != first_u or
                transformed_u(field, second) != second_u or
                total != raw_targets[flags[0]]):
            continue
        projected = [curve.mul(4, point) for point in points]
        projected_sum = None
        for point in projected:
            projected_sum = curve.add(projected_sum, point)
        if projected_sum != q:
            continue
        return {"valid": True, "seed_masks": masks, "folded_columns": columns,
                "raw_points": [list(point) for point in points],
                "projected_points": [list(point) for point in projected],
                "raw_sum": list(total), "target_q": list(q),
                "target_preimage_index": flags[0],
                "pair_u": pair_u, "first_u": first_u, "second_u": second_u}
    return {"valid": False, "reason": "group_chain", "masks": masks}


def preflight():
    verify_freeze()
    folder = HERE / "preflight"
    folder.mkdir(exist_ok=False)
    context = setup()
    control = json.loads(PLANTED.read_text())
    q = tuple(control["target_q"])
    circuit, meta, raw_targets, formula, stats, _ = build_formula(folder, context, q, control)
    initial = {}
    for row, mask in zip(meta["masks"], control["seed_masks"]):
        initial.update({wire: int(bool(mask & (1 << bit)))
                        for bit, wire in enumerate(row)})
    for i, wire in enumerate(meta["flags"]):
        initial[wire] = int(i == control["target_preimage_index"])
    for rows, values in ((meta["pair_outputs"], control["pair_u"]),
                         (meta["first_level"], control["first_u"]),
                         ([meta["second_level"]], [control["second_u"]])):
        for row, value in zip(rows, values):
            initial.update({wire: (value >> bit) & 1
                            for bit, wire in enumerate(row)})
    assert len(initial) == meta["primary_variables"]
    assignment = witness_tools.complete_assignment(circuit, initial)
    check = base.check_xcnf(formula, assignment)
    relation = decode(assignment, meta, context, q, raw_targets)
    assert relation["valid"] and relation["raw_points"] == control["raw_points"]
    write_json(folder / "receipt.json", {"status": "PASS", "formula": stats,
               "xcnf_check": check, "relation": relation,
               "source_protocol_sha256": sha(PROTOCOL)})
    print(json.dumps({"status": "PASS", "formula": stats}))


def measured(mode):
    protocol = verify_freeze()
    assert json.loads((HERE / "preflight/receipt.json").read_text())["status"] == "PASS"
    if mode == "public":
        assert json.loads((HERE / "control/receipt.json").read_text())["status"] == "VERIFIED_PINNED_CONTROL"
    folder = HERE / mode
    folder.mkdir(exist_ok=False)
    context = setup()
    control = json.loads(PLANTED.read_text())
    q = tuple(control["target_q"] if mode == "control" else context[-1]["target_q"])
    pinned = control if mode == "control" else None
    online_start = time.perf_counter_ns()
    circuit, meta, raw_targets, formula, stats, query_ns = build_formula(
        folder, context, q, pinned)
    base.ONLINE_CAP_SECONDS = CAPS[mode]
    base.CONFLICT_CAP = protocol["conflict_cap"][mode]
    base.RSS_CAP = protocol["memory_cap_bytes"]
    solver = base.run_solver(formula, folder, stats["variables"], online_start)
    model = solver.pop("model")
    check_start = time.perf_counter_ns()
    xcnf = base.check_xcnf(formula, model) if model else None
    relation = decode(model, meta, context, q, raw_targets) if model else None
    check_ns = time.perf_counter_ns() - check_start
    online_ns = time.perf_counter_ns() - online_start
    status = ("VERIFIED_PINNED_CONTROL" if mode == "control" else
              "VERIFIED_PUBLIC_RELATION") if relation and relation["valid"] else solver["status"]
    if mode == "control" and relation and relation["valid"]:
        assert relation["seed_masks"] == control["seed_masks"]
    receipt = {"status": status, "mode": mode, "curve_id": protocol["curve_id"],
               "target_q": list(q), "formula": stats, "solver": solver,
               "xcnf_check": xcnf, "relation": relation,
               "online_ns": online_ns,
               "phase_ns": {"target_query": query_ns,
                            "target_PDP": online_ns - query_ns - check_ns,
                            "target_relation_check": check_ns,
                            "target_descent": None,
                            "target_recovery_check": None},
               "protocol_sha256": sha(PROTOCOL)}
    assert receipt["phase_ns"]["target_PDP"] >= 0
    write_json(folder / "receipt.json", receipt)
    print(json.dumps({"status": status, "online_seconds": online_ns / 1e9,
                      "formula": stats, "peak_rss": solver["peak_group_rss_bytes"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "preflight", "control", "public"))
    args = parser.parse_args()
    if args.mode == "freeze":
        freeze()
    elif args.mode == "preflight":
        preflight()
    else:
        measured(args.mode)
