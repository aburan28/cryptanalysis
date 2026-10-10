#!/usr/bin/env sage -python
"""Independently fold three public-point rows into subgroup relation columns."""
import hashlib
import json
from pathlib import Path
from sage.all import EllipticCurve, GF, PolynomialRing, matrix

here = Path(__file__).resolve().parent
screen_path = here.parent / "n131_w18_four_pairs/screen.json"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
screen = json.loads(screen_path.read_text())["n41"]
join = json.loads((here / "join_result.json").read_text())
audit = json.loads((here / "sage_join_audit.json").read_text())
assert join["status"] == "EXHAUSTIVE" and audit["status"] == "PASS_EXACT_SAGE_REPLAY"
assert join["distinct_column_hits"] == len(audit["witnesses"]) == 3
R = 549756390943
residues = GF(R)
roots = [(-residues(1) + root) / 2 for root in residues(-7).sqrt(all=True)]
assert len(roots) == 2
ring = PolynomialRing(GF(2), "t")
t = ring.gen()
field = GF(2**41, name="t", modulus=t**41 + t**3 + 1)
curve = EllipticCurve(field, [1, 0, 0, 0, 1])
zero = curve(0)
def decode(value):
    return field(ring([(int(value) >> bit) & 1 for bit in range(41)]))
def encode(value):
    return sum(int(coefficient) << bit for bit, coefficient in
               enumerate(value.polynomial().list()))
def point(values):
    return curve(decode(values[0]), decode(values[1]))
def key(p):
    return (encode(p[0]), encode(p[1]))
def frob(p):
    return curve(p[0]**2, p[1]**2)

source = {}
columns = {}
representatives = {}
for x, y, column, mask, branch, sign in screen["point_rows_by_unique_rotation"]["0"]:
    assert branch == 0
    p = point((x, y))
    assert R*p == zero
    source[(mask, sign)] = p
    columns[mask] = column
    if sign == 0 and column not in representatives:
        representatives[column] = p
assert len(representatives) == 26
sample = next(iter(representatives.values()))
matching_roots = [root for root in roots if int(root)*sample == frob(sample)]
if len(matching_roots) != 1:
    raise ValueError("Frobenius eigenvalue ambiguous")
lam = matching_roots[0]
orbit = {}
for column, rep in representatives.items():
    current = rep
    for exponent in range(41):
        for sign, p in ((1, current), (-1, -current)):
            k = key(p)
            if k in orbit and orbit[k] != (column, sign, exponent):
                raise ValueError("overlapping folded orbits")
            orbit[k] = (column, sign, exponent)
        current = frob(current)
    assert current == rep
for (mask, sign), p in source.items():
    assert orbit[key(p)][0] == columns[mask]

rotations = (0, 6, 12, 18, 24, 30, 36)
q = point(json.loads((here / "join_protocol.json").read_text())["target_q"])
rows = []
for witness in audit["witnesses"]:
    row = [residues(0)] * 26
    for i, (mask, sign) in enumerate(zip(witness["masks"], witness["signs"])):
        column, orientation, exponent = orbit[key(source[(mask, sign)])]
        row[column] += orientation * lam**(exponent + rotations[i]) * (1 + lam)
    replay = sum((int(coefficient)*representatives[i] for i, coefficient in enumerate(row)), zero)
    if replay != q:
        raise ValueError("folded row fails independent Sage group replay")
    rows.append(row)
row_rank = int(matrix(residues, [row + [-residues(1)] for row in rows]).rank())
base_only_rank = int(matrix(residues, [[a-b for a,b in zip(row, rows[0])]
                                       for row in rows[1:]]).rank())
result = {
    "status": "PASS_FOLDED_RELATION_RANK_AND_GROUP_REPLAY",
    "frobenius_eigenvalue_mod_r": int(lam),
    "full_rows_with_target_column_rank": row_rank,
    "factor_base_only_difference_rank": base_only_rank,
    "folded_columns_K": 26,
    "verified_public_relation_rows": len(rows),
    "rows_mod_r": [[int(value) for value in row] for row in rows],
    "source_sha256": {"screen": sha(screen_path),
                      "join_protocol": sha(here / "join_protocol.json"),
                      "sage_join_audit": sha(here / "sage_join_audit.json"),
                      "audit_script": sha(Path(__file__))},
}
path = here / "sage_rank_audit.json"
with path.open("x") as out:
    json.dump(result, out, indent=2, sort_keys=True)
    out.write("\n")
print(json.dumps({"status": result["status"], "row_rank": row_rank,
                  "base_only_rank": base_only_rank}))
