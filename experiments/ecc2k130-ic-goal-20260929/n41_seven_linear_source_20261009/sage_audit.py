#!/usr/bin/env sage -python
"""Independent checked-Sage proof of the linear-source target transport."""
import hashlib
import json
from pathlib import Path
from sage.all import EllipticCurve, GF, PolynomialRing

here = Path(__file__).resolve().parent
root = here.parent
old = root / "n41_n131_seven_diagonal_20261009"
screen_path = root / "n131_w18_four_pairs/screen.json"
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
protocol = json.loads((here / "protocol.json").read_text())
receipt = json.loads((here / "preflight/receipt.json").read_text())
control = json.loads((here / "control.json").read_text())
screen = json.loads(screen_path.read_text())["n41"]
runtime = json.loads((here / "sage_runtime_info.json").read_text())
assert runtime["status"] == "verified"
assert protocol["status"] == "FROZEN_BEFORE_MEASUREMENT"
assert receipt["status"] == "PASS_FULL_FORMULA_AND_GROUP_CONTROL"
assert protocol["source_sha256"]["screen"] == sha(screen_path)
assert protocol["source_sha256"]["control"] == sha(here / "control.json")
assert receipt["protocol_sha256"] == sha(here / "protocol.json")
assert receipt["formula"]["sha256"] == sha(here / "preflight/system.xcnf")

ring = PolynomialRing(GF(2), "t")
t = ring.gen()
field = GF(2**41, name="t", modulus=t**41+t**3+1)
curve = EllipticCurve(field, [1, 0, 0, 0, 1])
zero = curve(0)
R = 549756390943
def decode(value):
    return field(ring([(int(value) >> bit) & 1 for bit in range(41)]))
def encode(value):
    return sum(int(coefficient) << bit for bit, coefficient in
               enumerate(value.polynomial().list()))
def point(values):
    return curve(decode(values[0]), decode(values[1]))
def key(p):
    return (encode(p[0]), encode(p[1]))
def frob(p, count):
    for _ in range(count):
        p = curve(p[0]**2, p[1]**2)
    return p
def phi(p):
    if p == zero or p[0] == 1:
        raise ValueError("undefined transformed coordinate")
    return 1/(p[0]+1)

source = {}
columns = {}
for x,y,column,mask,branch,sign in screen["point_rows_by_unique_rotation"]["0"]:
    assert branch == 0
    source[(mask,sign)] = point((x,y))
    columns[mask] = column
halves = [decode(value) for value in screen["window_basis_halftrace"][0]]
raw = {}
for mask, sign in {(m,s) for line in (old / "join_hits.jsonl").open()
                   for m,s in zip(json.loads(line)["masks"],json.loads(line)["signs"])}:
    u = sum((halves[i] for i in range(6) if mask >> i & 1),field.zero())
    assert u not in (0,1)
    choices = curve.lift_x(1+1/u,all=True)
    matches = [p for p in choices if 4*p == source[(mask,sign)]]
    if len(matches) != 1:
        raise ValueError("raw lift mismatch")
    raw[(mask,sign)] = matches[0]

q = point(protocol["public_target_q"])
qprime = point(protocol["transported_target_qprime"])
lam = int(protocol["lambda_mod_r"])
assert q != zero and qprime != zero and R*q == R*qprime == zero
assert (lam*lam+lam+2)%R == 0
assert qprime + frob(qprime,1) == q
assert (1+lam)*qprime == q
rotations = protocol["rotations"]
verified = 0
for line in (old / "join_hits.jsonl").open():
    hit = json.loads(line)
    assert len(set(columns[m] for m in hit["masks"])) == 7
    leaves = []
    for i,(mask,sign) in enumerate(zip(hit["masks"],hit["signs"])):
        p = frob(raw[(mask,sign)],rotations[i])
        u = sum((halves[j] for j in range(6) if mask >> j & 1),field.zero())**(2**rotations[i])
        assert phi(p) == u
        assert 4*p == frob(source[(mask,sign)],rotations[i])
        assert frob(4*p,1) == lam*(4*p)
        leaves.append(p)
    total = sum(leaves,zero)
    assert 4*total == qprime
    assert 4*sum((p+frob(p,1) for p in leaves),zero) == q
    if verified == 0:
        assert key(total) == tuple(control["raw_sum"])
        assert [key(p) for p in leaves] == [tuple(p) for p in control["raw_leaves"]]
    verified += 1
assert verified == 3
result = {"status":"PASS_EXACT_TARGET_TRANSPORT_AND_THREE_SOURCE_ROWS",
          "verified_public_rows":verified,
          "public_target_q":protocol["public_target_q"],
          "transported_target_qprime":protocol["transported_target_qprime"],
          "preflight_formula":receipt["formula"],
          "source_sha256":{"protocol":sha(here/"protocol.json"),
                           "control":sha(here/"control.json"),
                           "preflight":sha(here/"preflight/receipt.json"),
                           "old_hits":sha(old/"join_hits.jsonl"),
                           "screen":sha(screen_path),
                           "audit_script":sha(Path(__file__))}}
path=here/"sage_audit.json"
with path.open("x") as out:
    json.dump(result,out,indent=2,sort_keys=True)
    out.write("\n")
print(json.dumps({"status":result["status"],"rows":verified}))
