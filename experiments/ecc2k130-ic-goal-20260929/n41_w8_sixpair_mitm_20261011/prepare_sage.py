#!/usr/bin/env sage -python
"""Freeze and enumerate six rotated fixed-seed pair lists on N41 W8."""

import hashlib
import json
import random
import sys
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_w7_entropy_cubic_20261011/w8"
GEOMETRY = SOURCE / "geometry.json"
FIXTURE = SOURCE / "fixture.json"
RUNTIME = HERE / "sage_runtime_info.json"
SEED = 184
ROTATIONS = [0, 7, 14, 21, 28, 35]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paths():
    return {"source": Path(__file__), "geometry": GEOMETRY,
            "fixture": FIXTURE, "runtime": RUNTIME}


def save(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")


def freeze():
    geometry = json.loads(GEOMETRY.read_text())
    fixture = json.loads(FIXTURE.read_text())
    assert geometry["counts"]["rational_masks"] == 125
    assert fixture["public_target_transported"] == [920359962848, 755404565011]
    assert json.loads(RUNTIME.read_text())["status"] == "verified"
    record = {"status": "FROZEN_N41_W8_SIX_PAIR_MITM_PREPARATION",
              "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
              "field": "GF(2)[t]/(t^41+t^3+1)",
              "curve": "y^2+xy=x^3+1", "subgroup_order": 549756390943,
              "cofactor": 4, "seed_mask": SEED, "rotations": ROTATIONS,
              "public_target_original": fixture["public_target_original"],
              "public_target_transported": fixture["public_target_transported"],
              "raw_target_preimages": fixture["raw_target_preimages"],
              "workers": 1, "join_wall_cap_seconds": 120,
              "combined_rss_cap_bytes": 4*1024**3,
              "source_sha256": {name: sha(path) for name, path in paths().items()}}
    save(HERE / "prepare_protocol.json", record)
    print(record["status"])


def produce():
    protocol = json.loads((HERE / "prepare_protocol.json").read_text())
    assert protocol["source_sha256"] == {name: sha(path) for name, path in paths().items()}
    geometry = json.loads(GEOMETRY.read_text())
    fixture = json.loads(FIXTURE.read_text())
    rows = {int(row["mask"]): row for row in geometry["rows"]}
    edges = [(a, a ^ SEED) for a in sorted(rows)
             if a < (a ^ SEED) and a ^ SEED in rows
             and rows[a]["column"] != rows[a ^ SEED]["column"]]
    assert len(edges) == 35
    assert len({rows[mask]["column"] for edge in edges for mask in edge}) == 70
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**41, name="t", modulus=t**41+t**3+1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])

    def dec(value):
        return field(ring([(int(value) >> i) & 1 for i in range(41)]))

    def enc(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    raw = {mask: curve(*map(dec, row["raw_point"])) for mask, row in rows.items()}
    for mask, point in raw.items():
        assert [enc(point[0]), enc(point[1])] == rows[mask]["raw_point"]
    target = [curve(*map(dec, xy)) for xy in fixture["raw_target_preimages"]]
    assert all(4*point == curve(*map(dec, fixture["public_target_transported"]))
               for point in target)
    states = []
    lines = ["ECC2K41 6 140 4"]
    for index, point in enumerate(target):
        lines.append(f"T {index} {enc(point[0])} {enc(point[1])}")
    for slot, rotation in enumerate(ROTATIONS):
        one = []
        for edge_id, (a, b) in enumerate(edges):
            for sign_a in (0, 1):
                for sign_b in (0, 1):
                    first = -raw[a] if sign_a else raw[a]
                    second = -raw[b] if sign_b else raw[b]
                    pair = first + second
                    assert pair != curve(0)
                    rotated = curve(pair[0]**(1 << rotation),
                                    pair[1]**(1 << rotation))
                    state_id = len(one)
                    one.append(rotated)
                    lines.append(f"S {slot} {state_id} {edge_id} {a} {b} "
                                 f"{sign_a} {sign_b} {enc(rotated[0])} {enc(rotated[1])}")
        assert len(one) == 140
        states.append(one)
    rng = random.Random(20261011)
    for _ in range(128):
        left = states[rng.randrange(6)][rng.randrange(140)]
        right = states[rng.randrange(6)][rng.randrange(140)]
        total = left + right
        if total == curve(0):
            lines.append(f"C {enc(left[0])} {enc(left[1])} "
                         f"{enc(right[0])} {enc(right[1])} -1 -1")
        else:
            lines.append(f"C {enc(left[0])} {enc(left[1])} "
                         f"{enc(right[0])} {enc(right[1])} {enc(total[0])} {enc(total[1])}")
    input_path = HERE / "join_input.tsv"
    with input_path.open("x") as stream:
        stream.write("\n".join(lines) + "\n")
    result = {"status": "PASS_N41_W8_SIX_PAIR_LIST_PREPARATION",
              "edge_count": len(edges), "state_count_per_slot": 140,
              "distinct_folded_columns_selected": 70,
              "raw_preimage_count": len(target), "group_addition_checks": 128,
              "input_sha256": sha(input_path),
              "input_bytes": input_path.stat().st_size,
              "protocol_sha256": sha(HERE / "prepare_protocol.json")}
    save(HERE / "prepare_result.json", result)
    print(result["status"], result["input_sha256"])


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("freeze", "produce"):
        raise SystemExit("usage: prepare_sage.py freeze|produce")
    {"freeze": freeze, "produce": produce}[sys.argv[1]]()
