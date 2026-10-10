#!/usr/bin/env sage -python
"""Independently audit the complete W5 unordered pair-output index."""

import hashlib
import json
from pathlib import Path
from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
GEOMETRY = ROOT / "n41_w5_ten_source_gate_20261010" / "geometry_result.json"
HIT = ROOT / "n41_w5_samepair_hybrid_20261010" / "run/hits.jsonl"
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
record = json.loads((HERE / "pair_index.json").read_text())
geometry = json.loads(GEOMETRY.read_text())
runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
assert runtime["status"] == "verified"
assert record["status"] == "PASS_EXACT_W5_UNORDERED_PAIR_INDEX"
F2 = GF(2)
ring = PolynomialRing(F2, "t")
t = ring.gen()
field = GF(2**41, name="t", modulus=t**41 + t**3 + 1)
curve = EllipticCurve(field, [1, 0, 0, 0, 1])
order = int(geometry["subgroup_order_r"])


def decode(value):
    return field(ring([(int(value) >> i) & 1 for i in range(41)]))


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def point(value):
    return curve(decode(value[0]), decode(value[1]))


def key(value):
    return [encode(value[0]), encode(value[1])]


def frob(value):
    return curve(value[0]**2, value[1]**2)


columns = {int(mask): tuple(value) for mask, value in
           geometry["mask_columns"].items()}
raw = {}
for mask_text, values in geometry["raw_points"].items():
    mask = int(mask_text)
    w = sum((field.gen()**(i+1) for i in range(5) if mask >> i & 1), field.zero())
    u = sum((decode(geometry["source_basis_u"][i]) for i in range(5)
             if mask >> i & 1), field.zero())
    assert u**2 + u == w and int((1 / w).trace()) == 0
    choices = sorted(curve.lift_x(1 + 1/u, all=True),
                     key=lambda value: tuple(key(value)))
    assert [key(value) for value in choices] == values
    assert all(order * (4 * value) == curve(0) for value in choices)
    raw[mask] = choices

indexed = {}
for entry in record["entries"]:
    mask_a, mask_b, z = (entry[name] for name in
                         ("mask_a", "mask_b", "z_local"))
    assert mask_a < mask_b and columns[mask_a] != columns[mask_b]
    assert len(entry["sign_options"]) == len(entry["raw_output_points"]) == 2
    for signs, reported in zip(entry["sign_options"], entry["raw_output_points"]):
        total = raw[mask_a][signs[0]] + raw[mask_b][signs[1]]
        assert key(total) == reported
        assert total[0] not in (0, 1)
        assert encode(1 / (total[0] + 1)) == z
    signature = (mask_a, mask_b, z)
    assert signature not in indexed
    indexed[signature] = entry

all_rows = 0
for mask_a in sorted(raw):
    for mask_b in sorted(raw):
        if mask_a >= mask_b or columns[mask_a] == columns[mask_b]:
            continue
        for sign_a in (0, 1):
            for sign_b in (0, 1):
                total = raw[mask_a][sign_a] + raw[mask_b][sign_b]
                assert total[0] not in (0, 1)
                z = encode(1 / (total[0] + 1))
                signature = (mask_a, mask_b, z)
                assert signature in indexed
                assert [sign_a, sign_b] in indexed[signature]["sign_options"]
                all_rows += 1
assert all_rows == 528 and len(indexed) == 264

hit = json.loads(HIT.read_text().strip())
mask_a, mask_b = hit["masks"][8:10]
sign_a, sign_b = hit["signs"][8:10]
assert mask_a < mask_b
rotated_a, rotated_b = raw[mask_a][sign_a], raw[mask_b][sign_b]
for _ in range(32):
    rotated_a, rotated_b = frob(rotated_a), frob(rotated_b)
rotated_sum = rotated_a + rotated_b
local_z = 1 / (rotated_sum[0] + 1)
for _ in range(9):
    local_z = local_z**2
assert encode(local_z) == encode(1 / ((raw[mask_a][sign_a] + raw[mask_b][sign_b])[0] + 1))
assert (mask_a, mask_b, encode(local_z)) in indexed

receipt = {"status": "PASS_INDEPENDENT_SAGE_COMPLETE_W5_PAIR_INDEX",
           "curve_id": record["curve_id"],
           "enumerated_unordered_signed_rows": all_rows,
           "exact_signatures": len(indexed),
           "known_public_relation_signature": [mask_a, mask_b, encode(local_z)],
           "source_sha256": {"script": sha(Path(__file__)),
                             "index": sha(HERE / "pair_index.json"),
                             "geometry": sha(GEOMETRY),
                             "public_hit": sha(HIT),
                             "runtime": sha(HERE / "sage_runtime_info.json")}}
with (HERE / "sage_index_audit.json").open("x") as out:
    json.dump(receipt, out, indent=2, sort_keys=True)
    out.write("\n")
print(json.dumps({"status": receipt["status"],
                  "signatures": len(indexed)}))
