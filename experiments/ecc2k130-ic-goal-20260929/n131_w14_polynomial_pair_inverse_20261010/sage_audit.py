#!/usr/bin/env sage -python
"""Independent GF(2) rank and group replay of the W14 pair inverse."""
import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, matrix, vector

HERE = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
protocol = json.loads((HERE / "protocol.json").read_text())
inputs = json.loads((HERE / "inputs.json").read_text())
result = json.loads((HERE / "result.json").read_text())
runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
assert protocol["status"] == "FROZEN_BEFORE_PAIR_QUERIES"
assert result["status"] == "PASS_EXACT_W14_JOINT_PAIR_INVERSE_CONTROLS"
assert runtime["status"] == "verified"
assert protocol["inputs_sha256"] == sha(HERE / "inputs.json")

F2 = GF(2)
ring = PolynomialRing(F2, "t")
t = ring.gen()
field = GF(2**131, name="t", modulus=t**131+t**13+t**2+t+1)
curve = EllipticCurve(field, [1, 0, 0, 0, 1])
r = 680564733841876926932320129493409985129


def element(value):
    result = field.zero()
    power = field.one()
    while value:
        if value & 1:
            result += power
        value >>= 1
        power *= field.gen()
    return result


def encoded(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def bit_matrix(columns):
    words = [encoded(value) for value in columns]
    return matrix(F2, 131, len(words),
                  lambda row, col: (words[col] >> row) & 1)


def half_trace(value):
    out = field.zero()
    for _ in range(66):
        out += value
        value = value**4
    return out


def coordinate(basis, mask):
    return sum((basis[i] for i in range(14) if mask >> i & 1), field.zero())


basis_w = [field.gen()**i for i in range(1, 15)]
basis_u = [half_trace(w) for w in basis_w]
assert all(u**2+u == w for u, w in zip(basis_u, basis_w))
assert bit_matrix(basis_u).augment(bit_matrix([field.one()])).rank() == 15
product_same = [field.gen()**k for k in range(2, 29)]
product_mixed = [a*b**(2**13) for a in basis_w for b in basis_w]
assert bit_matrix(product_same).rank() == 27
assert bit_matrix(product_mixed).rank() == 131

checked_positive = checked_uniform = 0
for row in result["queries"]:
    kind = row["kind"]
    z = element(row["z"])
    if kind == "exceptional":
        assert row["pairs"] == []
        continue
    az = z**2 + z
    columns = [u**2 for u in basis_u] + [az*product for product in product_same]
    M = bit_matrix(columns)
    rhs = bit_matrix([z**2])
    assert M.rank() == 41
    if kind == "uniform_field":
        assert M.augment(rhs).rank() == 42
        assert row["pairs"] == [] and row["detail"]["status"] == "SPAN_REJECT"
        checked_uniform += 1
        continue
    assert M.augment(rhs).rank() == 41
    coefficients = M.solve_right(vector(F2, rhs.column(0)))
    seed_sum = sum(int(coefficients[i]) << i for i in range(14))
    fixture = inputs["positives"][row["input_index"]]
    a, b = fixture["masks"]
    assert seed_sum == a ^ b == row["detail"]["seed_sum"]
    assert row["pairs"] == [sorted((a, b))]
    leaves = [curve(element(pair[0]), element(pair[1]))
              for pair in fixture["raw_leaves"]]
    total = leaves[0] + leaves[1]
    assert (encoded(total[0]), encoded(total[1])) == tuple(fixture["raw_sum"])
    assert 1/(total[0]+1) == z
    for mask, point in zip((a, b), leaves):
        assert 1/(point[0]+1) == coordinate(basis_u, mask)
        assert r * (4*point) == curve(0)
    checked_positive += 1
assert checked_positive == checked_uniform == 32

audit = {"status": "PASS_INDEPENDENT_SAGE_W14_JOINT_RANK_AND_GROUP_REPLAY",
         "curve_id": protocol["curve_id"],
         "same_rotation_product_rank": 27,
         "adjacent_rotation_product_rank": 131,
         "checked_positive_outputs": checked_positive,
         "checked_uniform_span_rejects": checked_uniform,
         "source_sha256": {"script": sha(__file__),
                           "protocol": sha(HERE / "protocol.json"),
                           "inputs": sha(HERE / "inputs.json"),
                           "result": sha(HERE / "result.json"),
                           "runtime": sha(HERE / "sage_runtime_info.json")}}
with (HERE / "sage_audit.json").open("x") as out:
    json.dump(audit, out, indent=2, sort_keys=True)
    out.write("\n")
print(json.dumps({"status": audit["status"],
                  "positives": checked_positive,
                  "uniform_rejects": checked_uniform}))
