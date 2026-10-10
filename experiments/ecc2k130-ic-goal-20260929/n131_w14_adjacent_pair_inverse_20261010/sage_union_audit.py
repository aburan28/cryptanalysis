#!/usr/bin/env sage -python
"""Independent subspace-intersection proof of the ten-window W14 union."""
import hashlib
import json
from pathlib import Path

from sage.all import GF, PolynomialRing, matrix

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
SUPPORT = PARENT / "n131_w14_ten_source_gate_20261009/support_w14.tsv"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


protocol = json.loads((HERE / "union_audit_protocol.json").read_text())
for name, path in (("source", __file__), ("support", SUPPORT),
                   ("result", HERE / "result.json"),
                   ("runtime", HERE / "sage_runtime_info.json")):
    assert sha(path) == protocol["sha256"][name]
assert not (HERE / "sage_union_audit.json").exists()

F2 = GF(2)
ring = PolynomialRing(F2, "t")
t = ring.gen()
F = GF(2**131, "t", modulus=t**131+t**13+t**2+t+1)
rotations = (0, 1, 26, 27, 52, 53, 78, 79, 104, 105)
base = [F.gen()**i for i in range(1, 15)]


def bits(value):
    return sum(int(c) << i for i, c in enumerate(value.polynomial().list()))


def rank(values):
    words = [bits(v) for v in values]
    M = matrix(F2, 131, len(words), lambda i, j: (words[j] >> i) & 1)
    return int(M.rank())


spaces = {k: [w**(2**k) for w in base] for k in rotations}
near = []
far = []
for i, a in enumerate(rotations):
    for b in rotations[i+1:]:
        combined = rank(spaces[a]+spaces[b])
        if b == a+1:
            assert combined == 21
            near.append([a, b])
        else:
            assert combined == 28
            far.append([a, b])
assert len(near) == 5 and len(far) == 40
masks = []
for line in SUPPORT.read_text().splitlines():
    mask, _column = map(int, line.split())
    masks.append(mask)
assert len(masks) == 8220
intersection = sum(all(not(mask >> (i-1) & 1) for i in range(1, 15, 2))
                   for mask in masks)
assert intersection == 60
union_x = 10*len(masks)-5*intersection
result = json.loads((HERE / "result.json").read_text())
assert union_x == result["unique_x"] == 81900
assert 2*union_x == result["actual_base_points_B"] == 163800

audit = {"status": "PASS_INDEPENDENT_SAGE_W14_UNION_GEOMETRY",
         "source_sha256": protocol["sha256"],
         "protocol_sha256": sha(HERE / "union_audit_protocol.json"),
         "source_masks_per_rotation": len(masks),
         "adjacent_rank21_pairs": near,
         "disjoint_rank28_pairs": len(far),
         "rational_x_intersection_per_adjacent_pair": intersection,
         "union_x": union_x, "actual_base_points_B": 2*union_x}
with (HERE / "sage_union_audit.json").open("x") as stream:
    json.dump(audit, stream, indent=2, sort_keys=True)
    stream.write("\n")
print(json.dumps(audit, sort_keys=True))
