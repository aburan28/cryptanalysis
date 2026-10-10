#!/usr/bin/env sage -python
"""Independent exact W19 rational masks, orbit aliases, and seven-window union."""
import hashlib
import json
from pathlib import Path
from sage.all import GF, PolynomialRing, matrix

here = Path(__file__).resolve().parent
root_dir = here.parent
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
protocol = json.loads((here / "support_protocol.json").read_text())
receipt = json.loads((here / "support_receipt.json").read_text())
prior = json.loads((root_dir / "n131_w19_near_pair_geometry/result.json").read_text())
runtime = json.loads((here / "sage_runtime_info.json").read_text())
assert protocol["status"] == "FROZEN_BEFORE_ENUMERATION"
assert receipt["status"] == "COMPLETE" and runtime["status"] == "verified"
assert protocol["source_sha256"]["w19_result"] == sha(root_dir / "n131_w19_near_pair_geometry/result.json")
assert receipt["rational_masks"] == prior["rational_source_masks"] == 262390
assert receipt["folded_columns_K"] == prior["signed_frobenius_columns_K"] == 262151
assert receipt["reciprocal_overlap"] == prior["reciprocal_frobenius_hits"] == 0

F2 = GF(2)
ring = PolynomialRing(F2, "t")
t = ring.gen()
field = GF(2**131,name="t",modulus=t**131+t**13+t**2+t+1)
basis = [field.gen()**i for i in range(1,20)]
def integer(value):
    return sum(int(bit) << i for i,bit in enumerate(value.polynomial().list()))
def bit_matrix(columns):
    return matrix(F2,131,len(columns),lambda row,col:(columns[col]>>row)&1)

export = {}
valid = set()
word = field.zero()
previous = 0
lines = (here / "support_w19.tsv").open()
for ordinal in range(1,1<<19):
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
    observed, canonical = map(int,line.split())
    if observed != mask or canonical > mask:
        raise ValueError("native rational mask/order mismatch")
    valid.add(mask)
    export[mask] = canonical
if lines.readline():
    raise ValueError("support file has trailing masks")
lines.close()
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
largest_intersection_dimension = 0
for shift in range(1,131):
    rotated = [value**2 for value in rotated]
    columns = source_ints + [integer(value) for value in rotated]
    kernel = bit_matrix(columns).right_kernel().basis()
    d = len(kernel)
    largest_intersection_dimension = max(largest_intersection_dimension,d)
    if d > 12:
        raise ValueError("unexpectedly large W19 intersection")
    for code in range(1,1<<d):
        combined = sum((kernel[i] for i in range(d) if code>>i&1),
                       kernel[0].parent().zero())
        a = sum(int(combined[i])<<i for i in range(19))
        b = sum(int(combined[19+i])<<i for i in range(19))
        if not a or not b:
            raise ValueError("zero mask in subspace intersection")
        if (a in valid) != (b in valid):
            raise ValueError("rationality is not Frobenius invariant")
        if a in valid:
            overlap += 1
            union(a,b)
assert overlap == receipt["direct_overlap_incidence"] == 486
minimum = {}
for mask in valid:
    root = find(mask)
    minimum[root] = min(minimum.get(root,mask),mask)
if len(minimum) != receipt["folded_columns_K"]:
    raise ValueError("independent orbit count mismatch")
for mask,canonical in export.items():
    if minimum[find(mask)] != canonical:
        raise ValueError("canonical orbit alias mismatch")

rotations = protocol["rotations"]
rotated_by_shift = {}
current = basis[:]
for shift in range(max(rotations)+1):
    if shift in rotations:
        rotated_by_shift[shift] = [integer(value) for value in current]
    current = [value**2 for value in current]
pair_ranks = {}
for i,a in enumerate(rotations):
    for b in rotations[i+1:]:
        rank = int(bit_matrix(rotated_by_shift[a]+rotated_by_shift[b]).rank())
        pair_ranks[f"{a}_{b}"] = rank
if set(pair_ranks.values()) != {38}:
    raise ValueError("seven rotated W19 windows overlap")
actual_B = 2*len(valid)*len(rotations)
assert actual_B == receipt["actual_subgroup_factor_base_points_B"] == 3673460
result = {
    "status":"PASS_FULL_MASKS_ORBITS_AND_DISJOINT_WINDOWS",
    "checked_masks":(1<<19)-1,"rational_masks":len(valid),
    "orbit_overlap_incidence":overlap,"folded_columns_K":len(minimum),
    "largest_pairwise_source_intersection_dimension":largest_intersection_dimension,
    "rotated_window_pair_ranks":pair_ranks,
    "actual_subgroup_factor_base_points_B":actual_B,
    "source_sha256":{"protocol":sha(here/"support_protocol.json"),
                     "support":sha(here/"support_w19.tsv"),
                     "receipt":sha(here/"support_receipt.json"),
                     "prior_geometry":sha(root_dir/"n131_w19_near_pair_geometry/result.json"),
                     "audit_script":sha(Path(__file__))}}
with (here/"sage_support_audit.json").open("x") as out:
    json.dump(result,out,indent=2,sort_keys=True)
    out.write("\n")
print(json.dumps({"status":result["status"],"B":actual_B,"K":len(minimum)}))
