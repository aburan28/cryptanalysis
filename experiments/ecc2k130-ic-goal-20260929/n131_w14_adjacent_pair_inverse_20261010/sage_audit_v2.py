#!/usr/bin/env sage -python
"""Independent field-rank and raw-group audit for the adjacent W14 inverse."""
import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, matrix, vector

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


freeze = json.loads((HERE / "audit_protocol_v2.json").read_text())
for name, path in (("source", __file__), ("run_result", HERE / "result.json"),
                   ("runtime", HERE / "sage_runtime_info.json")):
    assert sha(path) == freeze["sha256"][name]
assert not (HERE / "sage_audit.json").exists()
result = json.loads((HERE / "result.json").read_text())
assert result["status"] == "COMPLETE_EXACT_STAGE"

F2 = GF(2)
ring = PolynomialRing(F2, "t")
t = ring.gen()
F = GF(2**131, "t", modulus=t**131+t**13+t**2+t+1)
E = EllipticCurve(F, [1, 0, 0, 0, 1])
order = 680564733841876926932320129493409985129


def elem(value):
    answer, power = F.zero(), F.one()
    while value:
        if value & 1:
            answer += power
        power *= F.gen()
        value >>= 1
    return answer


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def bit_matrix(columns):
    words = [encode(value) for value in columns]
    return matrix(F2, 131, len(words), lambda row, col: (words[col] >> row) & 1)


def halftrace(value):
    out = F.zero()
    for _ in range(66):
        out += value
        value = value**4
    return out


def mask_w(mask):
    return sum((F.gen()**i for i in range(1, 15) if mask >> (i-1) & 1), F.zero())


left = [F.gen()**i for i in range(1, 15)]
right = [w**2 for w in left]
sum_basis = left + [w for w in right if w not in left]
product_basis = [F.gen()**i for i in range(3, 43)]
assert len(sum_basis) == 21 and len(product_basis) == 40
assert bit_matrix(left+right).rank() == 21
assert bit_matrix([a*b for a in left for b in right]).rank() == 40
assert bit_matrix(sum_basis).rank() == 21
assert bit_matrix(product_basis).rank() == 40
sum_u = [halftrace(w) for w in sum_basis]
assert all(u**2+u == w for u, w in zip(sum_u, sum_basis))

positive = uniform = checked_raw = 0
for row in result["records"]:
    z = elem(row["z"])
    az = z**2+z
    assert az != 0
    columns = [u**2 for u in sum_u] + [az*p for p in product_basis]
    M = bit_matrix(columns)
    rhs = bit_matrix([z**2])
    assert M.rank() == 61 == row["detail"]["rank"]
    if row["kind"] == "uniform_field":
        assert M.augment(rhs).rank() == 62
        assert row["pairs"] == [] and row["detail"]["status"] == "SPAN_REJECT"
        uniform += 1
        continue
    assert M.augment(rhs).rank() == 61
    coefficients = M.solve_right(vector(F2, rhs.column(0)))
    s = sum((sum_basis[i] for i in range(21) if coefficients[i]), F.zero())
    p = sum((product_basis[i] for i in range(40) if coefficients[21+i]), F.zero())
    a, b = row["masks"]
    wa, wb = mask_w(a), mask_w(b)**2
    assert s == wa+wb and p == wa*wb
    assert encode(s) == row["detail"]["seed_sum"]
    assert encode(p) == row["detail"]["product"]
    assert z**2 == halftrace(s)**2+(z**2+z)*p
    assert row["pairs"] == [[a, b]]
    assert row["detail"]["seed_representations"] == 128
    ua, ub = halftrace(wa), halftrace(wb)
    options_a = E.lift_x(1+1/ua, all=True)
    options_b = E.lift_x(1+1/ub, all=True)
    assert len(options_a) == len(options_b) == 2
    found = False
    for pa in options_a:
        for pb in options_b:
            total = pa+pb
            if not total.is_zero() and total[0] != 1 and 1/(total[0]+1) == z:
                assert order*(4*pa) == E(0)
                assert order*(4*pb) == E(0)
                found = True
    assert found
    positive += 1
    checked_raw += 1

assert positive == uniform == checked_raw == 16
audit = {"status": "PASS_INDEPENDENT_SAGE_ADJACENT_W14_RANK_AND_GROUP",
         "source_sha256": freeze["sha256"], "audit_protocol_sha256": sha(HERE / "audit_protocol_v2.json"),
         "curve_id": result["curve_id"], "sum_rank": 21, "product_rank": 40,
         "positive_rank_consistent": positive, "uniform_rank_rejected": uniform,
         "raw_group_replayed": checked_raw}
with (HERE / "sage_audit.json").open("x") as stream:
    json.dump(audit, stream, sort_keys=True, indent=2)
    stream.write("\n")
print(json.dumps(audit, sort_keys=True))
