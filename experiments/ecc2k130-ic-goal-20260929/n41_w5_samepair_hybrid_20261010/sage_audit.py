#!/usr/bin/env sage -python
"""Independent finite-field and group replay of the repeated-pair public hit."""

import hashlib
import json
from pathlib import Path
from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
GEOMETRY = ROOT / "n41_w5_ten_source_gate_20261010" / "geometry_result.json"
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
protocol = json.loads((HERE / "protocol.json").read_text())
geometry = json.loads(GEOMETRY.read_text())
runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
native = json.loads((HERE / "run/result.json").read_text())
hits = (HERE / "run/hits.jsonl").read_text().splitlines()
assert runtime["status"] == "verified"
assert protocol["status"] == "FROZEN_BEFORE_NATIVE_SEARCH"
assert protocol["source_sha256"]["input"] == sha(HERE / "input.txt")
assert native["status"] == "FOUND_PENDING_SAGE_REPLAY" and len(hits) == 1
hit = json.loads(hits[0])
assert len(set(hit["columns"])) == 10

F2 = GF(2)
ring = PolynomialRing(F2, "t")
t = ring.gen()
field = GF(2**41, name="t", modulus=t**41 + t**3 + 1)
curve = EllipticCurve(field, [1, 0, 0, 0, 1])
zero = curve(0)
order = int(protocol["subgroup_order_r"])


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


def column(value):
    projected = 4 * value
    orbit = []
    for _ in range(41):
        orbit.extend((tuple(key(projected)), tuple(key(-projected))))
        projected = frob(projected)
    return min(orbit)


q = point(protocol["public_q"])
qprime = point([1496345304064, 1421510518509])
assert q != zero and order * q == order * qprime == zero
assert qprime + frob(qprime) == q
raw_targets = [point(list(map(int, line.split()))) for line in
               (HERE / "input.txt").read_text().splitlines()[1:5]]
assert len(set(raw_targets)) == 4
assert all(4 * value == qprime for value in raw_targets)
columns = sorted({tuple(value) for value in geometry["mask_columns"].values()})
assert len(columns) == 14
leaves = []
for slot, (mask, sign, column_id) in enumerate(zip(
        hit["masks"], hit["signs"], hit["columns"])):
    w = sum((field.gen()**(i+1) for i in range(5) if mask >> i & 1), field.zero())
    assert int((1 / w).trace()) == 0
    half = sum((decode(geometry["source_basis_u"][i])
                for i in range(5) if mask >> i & 1), field.zero())
    assert half**2 + half == w
    options = sorted(curve.lift_x(1 + 1 / half, all=True),
                     key=lambda item: tuple(key(item)))
    assert key(options[sign]) == geometry["raw_points"][str(mask)][sign]
    selected = options[sign]
    for _ in range(protocol["rotation_slots"][slot]):
        selected = frob(selected)
    assert column(selected) == columns[column_id]
    leaves.append(selected)
assert len({column(value) for value in leaves}) == 10
summed = sum(leaves, zero)
assert key(summed) == hit["raw_sum"]
assert summed == raw_targets[hit["target_preimage_index"]]
assert 4 * summed == qprime and 4 * summed + frob(4 * summed) == q
receipt = {
    "status": "PASS_INDEPENDENT_SAGE_SAMEPAIR_PUBLIC_RELATION",
    "curve_id": protocol["curve_id"],
    "public_q": key(q),
    "raw_sum": key(summed),
    "target_preimage_index": hit["target_preimage_index"],
    "masks": hit["masks"],
    "signs": hit["signs"],
    "folded_columns": hit["columns"],
    "actual_factor_base_points_B": protocol["actual_factor_base_points_B"],
    "folded_columns_K": protocol["folded_columns_K"],
    "source_sha256": {name: sha(path) for name, path in {
        "script": Path(__file__), "protocol": HERE / "protocol.json",
        "input": HERE / "input.txt", "geometry": GEOMETRY,
        "native_result": HERE / "run/result.json",
        "native_hit": HERE / "run/hits.jsonl",
        "runtime": HERE / "sage_runtime_info.json",
    }.items()},
}
with (HERE / "sage_audit.json").open("x") as out:
    json.dump(receipt, out, indent=2, sort_keys=True)
    out.write("\n")
print(json.dumps({"status": receipt["status"],
                  "target_preimage_index": receipt["target_preimage_index"]}))
