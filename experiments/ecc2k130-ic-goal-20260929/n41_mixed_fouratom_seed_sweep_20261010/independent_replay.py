#!/usr/bin/env python3
"""Replay N41 mixed-rotation seed decisions with independent bit-field code."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ARITH = ROOT / "n41_two_free_pair_occupancy_20261009/arithmetic_snapshot.py"
SCREEN = ROOT / "n41_n131_diagonal_atom_20261010/screen.json"
MIXED = ROOT / "n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json"

spec = importlib.util.spec_from_file_location("n41_independent_arithmetic", ARITH)
arith = importlib.util.module_from_spec(spec)
spec.loader.exec_module(arith)
f = arith.Field(41, [0, 3])
curve = arith.Curve(f, 0)
screen = json.loads(SCREEN.read_text())
panel = json.loads(MIXED.read_text())["panels"]["41"]
result = json.loads((HERE / "result.json").read_text())


def frob(point, steps):
    x, y = point
    for _ in range(steps):
        x, y = f.mul(x, x), f.mul(y, y)
    return x, y


def s3(a, b, z):
    product = f.mul(f.mul(a, b), z)
    total = a ^ b ^ z
    return f.mul(total, total) ^ product ^ f.mul(product, product)


columns = {}
for row in screen["slots"][0]:
    columns[row["mask"]] = row["source_column"]
points = {}
for row in screen["raw_audit"]:
    point = tuple(row["raw_pair_point"])
    assert curve.on_curve(point)
    points[row["mask"]] = (point, curve.neg(point))

tables = [{s: {} for s in range(1, 64)} for _ in range(2)]
masks = sorted(points)
for i, a in enumerate(masks):
    for b in masks[i+1:]:
        if columns[a] == columns[b]:
            continue
        seed = a ^ b
        for sign_a, pa in enumerate(points[a]):
            for sign_b, pb in enumerate(points[b]):
                pair = curve.add(pa, pb)
                if pair is None or pair[0] == 0:
                    continue
                for side, rotation in enumerate(panel["rotations"]):
                    rotated = frob(pair, rotation)
                    coordinate = f.inv(rotated[0])
                    tables[side][seed].setdefault(coordinate, []).append(
                        (a, b, sign_a, sign_b, rotated))

cases = {}
for case in ("positive", "trace_zero_control"):
    z = panel["positive_z" if case == "positive" else "trace_zero_control_z"]
    algebraic_seeds = []
    hits = []
    checked_coordinate_pairs = 0
    for seed in range(1, 64):
        found = False
        for c, left_states in tables[0][seed].items():
            for d, right_states in tables[1][seed].items():
                checked_coordinate_pairs += 1
                if s3(c, d, z):
                    continue
                found = True
                for la, lb, lsa, lsb, left_point in left_states:
                    for ra, rb, rsa, rsb, right_point in right_states:
                        masks4 = [la, lb, ra, rb]
                        if len({columns[v] for v in masks4}) != 4:
                            continue
                        total = curve.add(left_point, right_point)
                        if total is None or total[0] == 0 or f.inv(total[0]) != z:
                            continue
                        hits.append({"seed": seed, "masks": masks4,
                                     "signs": [lsa, lsb, rsa, rsb],
                                     "raw_sum": list(total),
                                     "projected_sum": list(curve.mul(4, total))})
        if found:
            algebraic_seeds.append(seed)
    expected = result["cases"][case]
    assert algebraic_seeds == expected["algebraic_hit_seeds"]
    assert sorted(hits, key=lambda h: (h["masks"], h["signs"])) == sorted(
        expected["group_hits"], key=lambda h: (h["masks"], h["signs"]))
    cases[case] = {"algebraic_hit_seeds": algebraic_seeds,
                   "group_hits": len(hits),
                   "checked_coordinate_pairs": checked_coordinate_pairs}

receipt = {"status": "PASS_INDEPENDENT_DIRECT_PAIR_REPLAY",
           "source_sha256": {
               "independent_replay.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "arithmetic_snapshot.py": hashlib.sha256(ARITH.read_bytes()).hexdigest(),
               "screen.json": hashlib.sha256(SCREEN.read_bytes()).hexdigest(),
               "mixed_inputs.json": hashlib.sha256(MIXED.read_bytes()).hexdigest(),
               "result.json": hashlib.sha256((HERE / "result.json").read_bytes()).hexdigest()},
           "cases": cases}
(HERE / "independent_replay.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
print(json.dumps({"status": receipt["status"], "cases": cases}, sort_keys=True))
