#!/usr/bin/env sage -python
"""Enumerate actual subgroup-projected W14 near-window factor-base points."""
import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
SUPPORT = PARENT / "n131_w14_ten_source_gate_20261009/support_w14.tsv"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


protocol = json.loads((HERE / "projected_audit_protocol.json").read_text())
for name, path in (("source", __file__), ("support", SUPPORT),
                   ("result", HERE / "result.json"),
                   ("runtime", HERE / "sage_runtime_info.json")):
    assert sha(path) == protocol["sha256"][name]
assert not (HERE / "sage_projected_audit.json").exists()

ring = PolynomialRing(GF(2), "t")
t = ring.gen()
F = GF(2**131, "t", modulus=t**131+t**13+t**2+t+1)
E = EllipticCurve(F, [1, 0, 0, 0, 1])
rotations = (0, 1, 26, 27, 52, 53, 78, 79, 104, 105)


def halftrace(value):
    answer = F.zero()
    for _ in range(66):
        answer += value
        value = value**4
    return answer


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


basis_u = [halftrace(F.gen()**i) for i in range(1, 15)]
masks = [int(line.split()[0]) for line in SUPPORT.read_text().splitlines()]
assert len(masks) == 8220
seen = set()
counts = [0]*len(rotations)
sample_checks = 0
for mask in masks:
    u = sum((basis_u[i] for i in range(14) if mask >> i & 1), F.zero())
    x = 1+1/u
    x2 = x**2+x**(-2)
    x4 = x2**2+x2**(-2)
    if sample_checks < 8:
        p = E.lift_x(x, all=True)[0]
        assert (4*p)[0] == x4
        assert 680564733841876926932320129493409985129*(4*p) == E(0)
        sample_checks += 1
    current = x4
    prior = 0
    for j, rotation in enumerate(rotations):
        for _ in range(rotation-prior):
            current = current**2
        prior = rotation
        key = encode(current)
        if key not in seen:
            seen.add(key)
            counts[j] += 1

result = json.loads((HERE / "result.json").read_text())
audit = {"status": "PASS_EXACT_PROJECTED_W14_UNION" if
         len(seen) == result["unique_x"] else "GEOMETRY_DISAGREEMENT",
         "source_sha256": protocol["sha256"],
         "protocol_sha256": sha(HERE / "projected_audit_protocol.json"),
         "rational_source_masks": len(masks),
         "projected_group_checks": sample_checks,
         "projected_new_x_by_rotation": dict(zip(map(str, rotations), counts)),
         "distinct_projected_x": len(seen),
         "actual_subgroup_usable_points_B": 2*len(seen),
         "raw_coordinate_union_x": result["unique_x"]}
with (HERE / "sage_projected_audit.json").open("x") as stream:
    json.dump(audit, stream, sort_keys=True, indent=2)
    stream.write("\n")
print(json.dumps({"status": audit["status"],
                  "B": audit["actual_subgroup_usable_points_B"],
                  "new_x": audit["projected_new_x_by_rotation"]}, sort_keys=True))
