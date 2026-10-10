#!/usr/bin/env python3
"""Exact N41 mixed-rotation sweep over the archived raw diagonal atoms."""

import hashlib
import json
import resource
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCREEN = ROOT / "n41_n131_diagonal_atom_20261010/screen.json"
MIXED = ROOT / "n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json"
PROTOCOL = HERE / "protocol.json"
protocol = json.loads(PROTOCOL.read_text())
sources = {"sweep.py": Path(__file__), "screen.json": SCREEN,
           "mixed_inputs.json": MIXED,
           "sage_runtime_info.json": HERE / "sage_runtime_info.json"}
assert protocol["source_sha256"] == {
    name: hashlib.sha256(path.read_bytes()).hexdigest()
    for name, path in sources.items()}

started = time.monotonic_ns()
ring = PolynomialRing(GF(2), "t")
t = ring.gen()
F = GF(2**41, name="t", modulus=t**41+t**3+1)


def decode(value):
    return F(ring([(int(value) >> i) & 1 for i in range(41)]))


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


E = EllipticCurve(F, [1, 0, 0, 0, 1])
screen = json.loads(SCREEN.read_text())
panel = json.loads(MIXED.read_text())["panels"]["41"]
assert panel["rotations"] == [10, 15]
screen_points = {}
columns = {}
for row in screen["slots"][0]:
    mask = row["mask"]
    point = E(decode(row["point"][0]), decode(row["point"][1]))
    screen_points.setdefault(mask, set()).add(point)
    if mask in columns:
        assert columns[mask] == row["source_column"]
    columns[mask] = row["source_column"]
assert len(screen_points) == 32 and len(set(columns.values())) == 26

points = {}
for row in screen["raw_audit"]:
    mask = row["mask"]
    raw = E(decode(row["raw_pair_point"][0]),
            decode(row["raw_pair_point"][1]))
    signed = (raw, -raw)
    assert {4 * p for p in signed} == screen_points[mask]
    assert encode(~raw[0]) == row["w"]
    points[mask] = dict(enumerate(signed))
assert len(points) == 32 and all(len(v) == 2 for v in points.values())


def rotate(point, steps):
    x, y = point.xy()
    for _ in range(steps):
        x, y = x*x, y*y
    return E(x, y)


rotations = panel["rotations"]
buckets = [{s: {} for s in range(1, 64)} for _ in range(2)]
signed_pairs = 0
masks = sorted(points)
for i, a in enumerate(masks):
    for b in masks[i+1:]:
        if columns[a] == columns[b]:
            continue
        seed = a ^ b
        for sign_a, pa in points[a].items():
            for sign_b, pb in points[b].items():
                pair = pa + pb
                if pair == E(0) or pair[0] == 0:
                    continue
                signed_pairs += 1
                for side, rotation in enumerate(rotations):
                    rotated = rotate(pair, rotation)
                    coordinate = encode(~rotated[0])
                    buckets[side][seed].setdefault(coordinate, []).append(
                        (a, b, sign_a, sign_b, rotated))
setup_ns = time.monotonic_ns() - started
assert signed_pairs == 1956

P = PolynomialRing(F, "D")
D = P.gen()
cases = {}
for case in protocol["case_order"]:
    z = decode(panel["positive_z" if case == "positive"
                     else "trace_zero_control_z"])
    query_start = time.monotonic_ns()
    algebraic_seeds = []
    hits = []
    pair_coordinate_probes = 0
    product_matches = 0
    for seed in range(1, 64):
        if time.monotonic_ns() - query_start >= protocol["cap_seconds_per_case"] * 10**9:
            raise TimeoutError("all-seed query cap reached")
        found = False
        for c_int, left_states in buckets[0][seed].items():
            pair_coordinate_probes += 1
            c = decode(c_int)
            equation = (1 + z*z*c*c)*D*D + z*c*D + z*z + c*c
            for d, _ in equation.roots():
                right_states = buckets[1][seed].get(encode(d), ())
                if not right_states:
                    continue
                product_matches += 1
                found = True
                for la, lb, lsa, lsb, left_point in left_states:
                    for ra, rb, rsa, rsb, right_point in right_states:
                        if len({columns[v] for v in (la, lb, ra, rb)}) != 4:
                            continue
                        total = left_point + right_point
                        if total != E(0) and total[0] != 0 and ~total[0] == z:
                            hits.append({"seed": seed,
                                         "masks": [la, lb, ra, rb],
                                         "signs": [lsa, lsb, rsa, rsb],
                                         "raw_sum": [encode(v) for v in total.xy()],
                                         "projected_sum": [encode(v) for v in (4*total).xy()]})
        if found:
            algebraic_seeds.append(seed)
    query_ns = time.monotonic_ns() - query_start
    cases[case] = {"status": "COMPLETE_EXACT_SEED_SWEEP",
                   "target_z": encode(z), "tested_seeds": 63,
                   "pair_coordinate_probes": pair_coordinate_probes,
                   "product_matches": product_matches,
                   "algebraic_hit_seeds": algebraic_seeds,
                   "group_hits": hits, "query_ns": query_ns}
    print(json.dumps({"case": case, "hit_seeds": algebraic_seeds,
                      "group_hits": len(hits), "query_s": query_ns/1e9},
                     sort_keys=True), flush=True)

positive = cases["positive"]["group_hits"]
assert any(hit["seed"] == 1 and hit["masks"] == [2, 3, 6, 7]
           and hit["raw_sum"] == panel["raw_sum"]
           and hit["projected_sum"] == panel["projected_sum"]
           for hit in positive)
rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
assert 0 < rss < protocol["rss_cap_bytes"]
result = {"status": "PASS_EXACT_N41_RAW_ATOM_SEED_SWEEP",
          "source_sha256": protocol["source_sha256"],
          "signed_pair_states_per_rotation": signed_pairs,
          "pair_output_coordinates_per_rotation": [
              sum(len(v) for v in side.values()) for side in buckets],
          "setup_ns": setup_ns, "cases": cases,
          "peak_process_rss_bytes": rss,
          "protocol_sha256": hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()}
(HERE / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
