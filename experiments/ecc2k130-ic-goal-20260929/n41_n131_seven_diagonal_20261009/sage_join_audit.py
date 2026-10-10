#!/usr/bin/env sage -python
"""Independently replay native public-point join witnesses in installed Sage."""
import hashlib
import json
from pathlib import Path
from sage.all import EllipticCurve, GF, PolynomialRing

here = Path(__file__).resolve().parent
screen_path = here.parent / "n131_w18_four_pairs/screen.json"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
protocol = json.loads((here / "join_protocol.json").read_text())
join = json.loads((here / "join_result.json").read_text())
screen = json.loads(screen_path.read_text())["n41"]
assert protocol["status"] == "FROZEN_BEFORE_QUERY"
assert protocol["source_sha256"]["input"] == sha(here / "join_input.txt")
assert protocol["source_sha256"]["source"] == sha(here / "native_join.cpp")
assert join["probes"] == join["completed_outer"] * 4096
assert join["outer_total"] == 4096 and join["completed_outer"] <= 4096
assert join["distinct_column_hits"] == sum(1 for _ in (here / "join_hits.jsonl").open())
if join["status"] == "EXHAUSTIVE":
    assert join["completed_outer"] == 4096

ring = PolynomialRing(GF(2), "t")
t = ring.gen()
field = GF(2**41, name="t", modulus=t**41 + t**3 + 1)
curve = EllipticCurve(field, [1, 0, 0, 0, 1])
zero = curve(0)
R = 549756390943
def decode(value):
    return field(ring([(int(value) >> bit) & 1 for bit in range(41)]))
def point(values):
    return curve(decode(values[0]), decode(values[1]))
def encode(value):
    return sum(int(coefficient) << bit for bit, coefficient in
               enumerate(value.polynomial().list()))
def phi(p):
    if p == zero or p[0] == 1:
        return None
    value = 1 / (p[0] + 1)
    return value if value not in (0, 1) else None
def frob(p, count):
    for _ in range(count):
        p = curve(p[0]**2, p[1]**2)
    return p

source = {}
columns = {}
for x, y, column, mask, branch, sign in screen["point_rows_by_unique_rotation"]["0"]:
    assert branch == 0
    source[(mask, sign)] = point((x, y))
    columns[mask] = column
halves = [decode(v) for v in screen["window_basis_halftrace"][0]]
source_raw = {}
for mask, sign in {(m, s) for line in (here / "join_hits.jsonl").open()
                   for m, s in zip(json.loads(line)["masks"], json.loads(line)["signs"])}:
    u = sum((halves[bit] for bit in range(6) if mask >> bit & 1), field.zero())
    assert u not in (0, 1)
    candidates = curve.lift_x(1 + 1/u, all=True)
    matches = [p for p in candidates if 4*p == source[(mask, sign)]]
    if len(matches) != 1:
        raise ValueError("raw source lift mismatch")
    source_raw[(mask, sign)] = matches[0]

q = point(protocol["target_q"])
assert q != zero and R*q == zero
rotations = (0, 6, 12, 18, 24, 30, 36)
raw_group_hits = 0
formula_compatible = 0
saved = []
for line in (here / "join_hits.jsonl").open():
    hit = json.loads(line)
    masks, signs = hit["masks"], hit["signs"]
    assert len(masks) == len(signs) == 7
    cols = [columns[mask] for mask in masks]
    assert len(set(cols)) == 7
    diagonal = []
    for i, (mask, sign) in enumerate(zip(masks, signs)):
        p = frob(source_raw[(mask, sign)], rotations[i])
        fp = frob(p, 1)
        d = p + fp
        assert 4*d == frob(source[(mask, sign)], rotations[i]) + frob(source[(mask, sign)], rotations[i]+1)
        diagonal.append(d)
    middle = [diagonal[0]+diagonal[1], diagonal[2]+diagonal[3],
              diagonal[4]+diagonal[5]]
    middle += [middle[0]+middle[1]]
    middle += [middle[3]+middle[2]]
    total = middle[4]+diagonal[6]
    assert 4*total == q
    raw_group_hits += 1
    if all(phi(p) is not None for p in [*diagonal, *middle, total]):
        formula_compatible += 1
        saved.append({"masks": masks, "signs": signs, "columns": cols,
                      "raw_sum": [encode(total[0]), encode(total[1])]})

result = {
    "status": "PASS_EXACT_SAGE_REPLAY" if join["status"] == "EXHAUSTIVE" else "PASS_CENSORED_PREFIX_REPLAY",
    "join_status": join["status"], "native_distinct_column_hits": join["distinct_column_hits"],
    "sage_raw_group_hits": raw_group_hits,
    "formula_compatible_hits": formula_compatible,
    "witnesses": saved[:16],
    "source_sha256": {"join_protocol": sha(here / "join_protocol.json"),
                      "join_result": sha(here / "join_result.json"),
                      "join_hits": sha(here / "join_hits.jsonl"),
                      "screen": sha(screen_path),
                      "audit_script": sha(Path(__file__))},
}
path = here / "sage_join_audit.json"
with path.open("x") as out:
    json.dump(result, out, indent=2, sort_keys=True)
    out.write("\n")
print(json.dumps({"status": result["status"], "formula_compatible_hits": formula_compatible}))
