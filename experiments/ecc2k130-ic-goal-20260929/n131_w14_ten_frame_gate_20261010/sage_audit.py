#!/usr/bin/env sage -python
"""Independent Sage replay of the N131 ten-source frame control."""
import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w14_ten_source_gate_20261009"
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
control = json.loads((HERE / "control.json").read_text())
protocol = json.loads((HERE / "protocol.json").read_text())
profile = json.loads((HERE / "profile.json").read_text())
runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
assert protocol["status"] == "FROZEN_BEFORE_FULL_FORMULA"
assert profile["status"] == "PASS_FULL_FORMULA_CONSTRUCTED_GROUP_WITNESS"
assert runtime["status"] == "verified"
assert protocol["control_sha256"] == sha(HERE / "control.json")

F2 = GF(2)
ring = PolynomialRing(F2, "t")
t = ring.gen()
field = GF(2**131, name="t", modulus=t**131 + t**13 + t**2 + t + 1)
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


def point(pair):
    return curve(element(pair[0]), element(pair[1]))


def frame(value, shift):
    for _ in range(shift):
        value = value**2
    return value


def u_of(p):
    assert p != curve(0) and p[0] not in (0, 1)
    return 1 / (p[0] + 1)


def s3(a, b, z):
    A = lambda value: value**2 + value
    return A(a) * A(b) * A(z) == (a + b + z)**2


columns = {}
with (SUPPORT / "support_w14.tsv").open() as rows:
    for row in rows:
        mask, canonical = map(int, row.split())
        columns[mask] = canonical
assert len(columns) == 8220
assert len(set(columns[mask] for mask in control["masks"])) == 10
leaves = [point(pair) for pair in control["raw_leaves"]]
source_w = [field.gen()**i for i in range(1, 15)]
for mask, rotation, leaf in zip(control["masks"], protocol["rotations"], leaves):
    word = sum((source_w[i] for i in range(14) if mask >> i & 1),
               field.zero())
    assert u_of(leaf)**2 + u_of(leaf) == frame(word, rotation)
    assert r * (4 * leaf) == curve(0)

middle = [leaves[2*i] + leaves[2*i+1] for i in range(5)]
middle.extend((middle[0] + middle[1], middle[2] + middle[3]))
middle.append(middle[5] + middle[6])
total = middle[7] + middle[4]
assert [encoded(u_of(p)) for p in middle] == control["middle_u"]
assert [encoded(total[0]), encoded(total[1])] == control["raw_sum"]
assert [encoded(x) for x in (4*total)[:2]] == control["target_q"]
assert r * (4 * total) == curve(0)
for i in range(5):
    shift = (131 - protocol["rotations"][2*i]) % 131
    assert s3(frame(u_of(leaves[2*i]), shift),
              frame(u_of(leaves[2*i+1]), shift),
              frame(u_of(middle[i]), shift))
for a, b, output in ((5, 6, 7), (0, 1, 5), (2, 3, 6)):
    assert s3(u_of(middle[a]), u_of(middle[b]), u_of(middle[output]))
assert s3(u_of(middle[7]), u_of(middle[4]), u_of(total))

result = {"status": "PASS_INDEPENDENT_SAGE_N131_GROUP_AND_FRAME_REPLAY",
          "curve_id": protocol["curve_id"], "masks": control["masks"],
          "target_q": control["target_q"], "raw_sum": control["raw_sum"],
          "checked_frame_leaf_links": 5, "checked_upper_links": 4,
          "source_sha256": {"control": sha(HERE / "control.json"),
                            "protocol": sha(HERE / "protocol.json"),
                            "profile": sha(HERE / "profile.json"),
                            "runtime": sha(HERE / "sage_runtime_info.json"),
                            "script": sha(__file__)}}
with (HERE / "sage_audit.json").open("x") as out:
    json.dump(result, out, indent=2, sort_keys=True)
    out.write("\n")
print(json.dumps({"status": result["status"], "target_q": result["target_q"]}))
