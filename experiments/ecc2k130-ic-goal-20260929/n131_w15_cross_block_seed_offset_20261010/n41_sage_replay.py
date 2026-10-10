#!/usr/bin/env sage -python
"""Independent public-row and normalized seed-offset identity replay."""
import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SCREEN = BASE / "n41_n131_diagonal_atom_20261010/screen.json"
INPUT = BASE / "n41_coupled_sixpair_full_ic_20261010/heldout_input.txt"
ORDER = 549756390943


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


freeze_path = HERE / "n41_sage_protocol.json"
freeze = json.loads(freeze_path.read_text())
sources = {"audit": Path(__file__), "screen": SCREEN, "input": INPUT,
           "native": HERE / "n41_native.json", "hit": HERE / "n41_hit.json",
           "query_receipt": HERE / "n41_query_receipt.json",
           "runtime": HERE / "sage_runtime_info.json"}
assert freeze["status"] == "FROZEN_BEFORE_N41_SAGE_REPLAY"
assert freeze["source_sha256"] == {name: sha(path) for name, path in sources.items()}
assert not (HERE / "n41_sage_replay.json").exists()
screen = json.loads(SCREEN.read_text())
hit = json.loads((HERE / "n41_hit.json").read_text())
native = json.loads((HERE / "n41_native.json").read_text())
assert native["status"] == "FOUND_PENDING_SAGE_REPLAY"
assert hit["status"] == "NATIVE_RELATION_PENDING_SAGE"
assert len(hit["masks"]) == len(hit["signs"]) == len(hit["columns"]) == 12
assert len(set(hit["columns"])) == 12

ring = PolynomialRing(GF(2), "t")
t = ring.gen()
F = GF(2**41, "t", modulus=t**41+t**3+1)
E = EllipticCurve(F, [1, 0, 0, 0, 1])
zero = E(0)


def decode(value):
    return F(ring([(int(value) >> i) & 1 for i in range(41)]))


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def key(point):
    return [encode(point[0]), encode(point[1])]


def frob(point):
    return E(point[0]**2, point[1]**2)


def orbit_key(point):
    reps = []
    for _ in range(41):
        reps.extend((tuple(key(point)), tuple(key(-point))))
        point = frob(point)
    return min(reps)


def field_mask(mask):
    return sum((F.gen()**(i+1) for i in range(6) if mask >> i & 1), F.zero())


qx, qy, order, blocks = map(int, INPUT.read_text().splitlines()[0].split())
assert order == ORDER and blocks == 6 and [qx, qy] == hit["raw_sum"]
q = E(decode(qx), decode(qy))
assert q != zero and ORDER*q == zero
raw_by_mask = {row["mask"]: row for row in screen["raw_audit"]}
rotations = [0, 5, 10, 15, 20, 25]
projected_points = []
raw_points = []
canonical = []
for block, rotation in enumerate(rotations):
    for local in range(2):
        i = 2*block+local
        mask, sign, column = hit["masks"][i], hit["signs"][i], hit["columns"][i]
        choices = [row for row in screen["slots"][block]
                   if row["mask"] == mask and row["sign"] == sign]
        assert len(choices) == 1
        slot = choices[0]
        assert slot["rotation"] == rotation and slot["source_column"] == column
        leaf = E(decode(slot["point"][0]), decode(slot["point"][1]))
        assert leaf != zero and ORDER*leaf == zero
        source = raw_by_mask[mask]
        w = decode(source["w"])
        assert w == field_mask(mask)
        source_raw = E(decode(source["raw_pair_point"][0]),
                       decode(source["raw_pair_point"][1]))
        assert source_raw[0] == 1/w
        rotated_raw = source_raw
        for _ in range(rotation):
            rotated_raw = frob(rotated_raw)
        if 4*rotated_raw == leaf:
            selected_raw = rotated_raw
        elif 4*(-rotated_raw) == leaf:
            selected_raw = -rotated_raw
        else:
            raise AssertionError("raw source point does not project to leaf")
        assert 4*selected_raw == leaf
        projected_points.append(leaf)
        raw_points.append(selected_raw)
        canonical.append(orbit_key(leaf))
assert len(set(canonical)) == 12
assert sum(projected_points, zero) == q
assert 4*sum(raw_points, zero) == q

pair_equations = []
for block, rotation in enumerate(rotations):
    a, b = hit["masks"][2*block:2*block+2]
    seed = a ^ b
    assert seed == hit["seed_sums"][block]
    wa, wb = field_mask(a), field_mask(b)
    s, p = wa+wb, wa*wb
    raw_sum = raw_points[2*block]+raw_points[2*block+1]
    assert raw_sum != zero and raw_sum[0] != 0
    c = 1/raw_sum[0]
    base_c = c**(2**((41-rotation) % 41))
    lhs = (1+p**2)*base_c**2+p*base_c
    assert lhs == s**2
    pair_equations.append({"block": block, "rotation": rotation,
                           "seed": seed, "normalized_c": encode(base_c),
                           "product": encode(p), "lhs": encode(lhs)})
assert hit["seed_sums"][2] == hit["seed_sums"][3]
assert hit["seed_sums"][4] == hit["seed_sums"][5]
delta = hit["seed_sums"][2] ^ hit["seed_sums"][4]
assert delta in range(8) and delta == 3
delta_w = field_mask(delta)
for left, right in ((2, 4), (2, 5), (3, 4), (3, 5)):
    assert decode(pair_equations[left]["lhs"]) + decode(pair_equations[right]["lhs"]) == delta_w**2
assert sum(projected_points, zero) == q

audit = {"status": "PASS_N41_PUBLIC_RELATION_AND_OFFSET_IDENTITY_SAGE",
         "candidate_id": None, "curve_id": freeze["curve_id"],
         "public_target": key(q), "summands": 12,
         "distinct_folded_columns": len(set(hit["columns"])),
         "seed_sums": hit["seed_sums"], "cross_block_offset": delta,
         "normalized_pair_equations": pair_equations,
         "projected_sum": key(sum(projected_points, zero)),
         "raw_sum_after_cofactor_four": key(4*sum(raw_points, zero)),
         "source_sha256": freeze["source_sha256"],
         "protocol_sha256": sha(freeze_path)}
with (HERE / "n41_sage_replay.json").open("x") as stream:
    json.dump(audit, stream, sort_keys=True, indent=2)
    stream.write("\n")
print(json.dumps({"status": audit["status"], "offset": delta,
                  "columns": audit["distinct_folded_columns"]}))
