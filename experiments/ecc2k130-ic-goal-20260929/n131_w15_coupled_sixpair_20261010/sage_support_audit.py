#!/usr/bin/env sage -python
"""Independently audit every W15 mask, source alias, and rotated base point."""
import hashlib
import json
from pathlib import Path
from sage.all import GF, PolynomialRing, matrix

here = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
protocol = json.loads((here / "support_protocol.json").read_text())
receipt = json.loads((here / "support_receipt.json").read_text())
runtime = json.loads((here / "sage_runtime_info.json").read_text())
assert protocol["status"] == "FROZEN_BEFORE_W15_SIX_PAIR_SUPPORT_ENUMERATION"
assert receipt["status"] == "COMPLETE" and runtime["status"] == "verified"
assert sha(here / "export_w15_support.cpp") == protocol["source_sha256"]["source"]

F2 = GF(2)
ring = PolynomialRing(F2, "t")
t = ring.gen()
field = GF(2**131, name="t", modulus=t**131+t**13+t**2+t+1)
width = protocol["source_dimension"]
basis = [field.gen()**i for i in range(1,width+1)]
def integer(value):
    return sum(int(bit) << i for i,bit in enumerate(value.polynomial().list()))
def bit_matrix(columns):
    return matrix(F2,131,len(columns),lambda row,col:(columns[col]>>row)&1)
def member(value):
    encoded = integer(value)
    return encoded > 0 and encoded & 1 == 0 and encoded < (1 << (width+1))

export = {}
valid = set()
word = field.zero()
previous = 0
with (here / "support_w15.tsv").open() as lines:
    for ordinal in range(1,1<<width):
        mask = ordinal ^ (ordinal>>1)
        changed = mask ^ previous
        assert changed.bit_count() == 1
        word += basis[changed.bit_length()-1]
        previous = mask
        if int((1/word).trace()):
            continue
        line = lines.readline()
        if not line:
            raise ValueError("support file ended early")
        observed,canonical = map(int,line.split())
        if observed != mask or canonical > mask:
            raise ValueError("native rational mask or order mismatch")
        valid.add(mask)
        export[mask] = canonical
    if lines.readline():
        raise ValueError("support file has trailing masks")
assert len(valid) == receipt["rational_masks"]

parents = {mask:mask for mask in valid}
def find(mask):
    root = mask
    while parents[root] != root:
        root = parents[root]
    while parents[mask] != mask:
        parent = parents[mask]
        parents[mask] = root
        mask = parent
    return root
def union(a,b):
    pa,pb = find(a),find(b)
    if pa != pb:
        parents[max(pa,pb)] = min(pa,pb)

source_ints = [integer(value) for value in basis]
rotated = basis[:]
overlap = 0
max_source_intersection = 0
for shift in range(1,131):
    rotated = [value**2 for value in rotated]
    kernel = bit_matrix(source_ints + [integer(value) for value in rotated]).right_kernel().basis()
    d = len(kernel)
    max_source_intersection = max(max_source_intersection,d)
    for code in range(1,1<<d):
        combined = sum((kernel[i] for i in range(d) if code>>i&1),
                       kernel[0].parent().zero())
        a = sum(int(combined[i])<<i for i in range(width))
        b = sum(int(combined[width+i])<<i for i in range(width))
        if not a or not b:
            raise ValueError("zero mask in subspace intersection")
        if (a in valid) != (b in valid):
            raise ValueError("Frobenius changed rationality")
        if a in valid:
            overlap += 1
            union(a,b)
assert overlap == receipt["direct_overlap_incidence"]
minimum = {}
for mask in valid:
    root = find(mask)
    minimum[root] = min(minimum.get(root,mask),mask)
assert len(minimum) == receipt["folded_columns_K"]
for mask,canonical in export.items():
    if minimum[find(mask)] != canonical:
        raise ValueError("canonical source Frobenius alias mismatch")

reciprocal_overlap = 0
for mask in valid:
    value = sum((basis[i] for i in range(width) if mask>>i&1),field.zero())
    reciprocal = 1/value
    for _ in range(66):
        reciprocal_overlap += int(member(reciprocal))
        reciprocal = reciprocal**2
assert reciprocal_overlap == receipt["reciprocal_overlap"] == 0

rotations = protocol["rotations"]
rotated_by_shift = {}
current = basis[:]
for shift in range(max(rotations)+1):
    if shift in rotations:
        rotated_by_shift[shift] = current[:]
    current = [value**2 for value in current]
pair_ranks = {}
rational_pair_overlaps = 0
for i,a in enumerate(rotations):
    for b in rotations[i+1:]:
        left,right = rotated_by_shift[a],rotated_by_shift[b]
        kernel = bit_matrix([integer(value) for value in left+right]).right_kernel().basis()
        pair_ranks[f"{a}_{b}"] = 2*width-len(kernel)
        for code in range(1,1<<len(kernel)):
            combined = sum((kernel[j] for j in range(len(kernel)) if code>>j&1),
                           kernel[0].parent().zero())
            value = sum((left[j] for j in range(width) if int(combined[j])),field.zero())
            rational_pair_overlaps += int((1/value).trace() == 0)
assert rational_pair_overlaps == 0
actual_B = 2*len(valid)*len(rotations)
assert actual_B == receipt["actual_subgroup_factor_base_points_B"]
result = {
    "status":"PASS_FULL_MASKS_ORBITS_AND_SIX_WINDOW_BASE",
    "checked_masks":(1<<width)-1,"rational_masks":len(valid),
    "orbit_overlap_incidence":overlap,"folded_columns_K":len(minimum),
    "reciprocal_frobenius_overlap":reciprocal_overlap,
    "largest_pairwise_source_intersection_dimension":max_source_intersection,
    "rotated_window_pair_ranks":pair_ranks,
    "rational_rotated_window_overlaps":rational_pair_overlaps,
    "actual_subgroup_factor_base_points_B":actual_B,
    "source_sha256":{"protocol":sha(here/"support_protocol.json"),
                     "support":sha(here/"support_w15.tsv"),
                     "receipt":sha(here/"support_receipt.json"),
                     "runtime":sha(here/"sage_runtime_info.json"),
                     "audit_script":sha(Path(__file__))}}
with (here/"sage_support_audit.json").open("x") as out:
    json.dump(result,out,indent=2,sort_keys=True)
    out.write("\n")
print(json.dumps({"status":result["status"],"B":actual_B,"K":len(minimum)}))
