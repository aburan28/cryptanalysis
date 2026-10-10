#!/usr/bin/env sage -python
"""Enumerate projected x coordinates with the exact binary-curve doubling law."""
import hashlib
import json
from pathlib import Path
from sage.all import EllipticCurve, GF, PolynomialRing

here = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
protocol = json.loads((here / "support_protocol.json").read_text())
support_audit = json.loads((here / "sage_support_audit.json").read_text())
receipt = json.loads((here / "support_receipt.json").read_text())
runtime = json.loads((here / "sage_runtime_info.json").read_text())
params_path = Path("/Volumes/SSD990/crypto/docs/ic/params/ecc2k130-fixed.json")
params = json.loads(params_path.read_text())
assert support_audit["status"] == "PASS_FULL_MASKS_ORBITS_AND_SIX_WINDOW_BASE"
assert protocol["source_sha256"]["official_params"] == sha(params_path)
assert runtime["status"] == "verified"

ring = PolynomialRing(GF(2),"t")
t = ring.gen()
field = GF(2**131,name="t",modulus=t**131+t**13+t**2+t+1)
curve = EllipticCurve(field,[1,0,0,0,1])
zero = curve(0)
R = int(params["curve"]["subgroup_order"])
width = protocol["source_dimension"]
source = [field.gen()**i for i in range(1,width+1)]
def encode(value):
    return sum(int(bit)<<i for i,bit in enumerate(value.polynomial().list()))
def halftrace(value):
    acc,term = field.zero(),value
    for _ in range(66):
        acc += term
        term = term**4
    assert acc**2+acc == value
    return acc
base_u = [halftrace(value) for value in source]
rotations = protocol["rotations"]
valid = {int(line.split()[0]) for line in (here/"support_w15.tsv").read_text().splitlines()}
assert len(valid) == receipt["rational_masks"]

seen_x = set()
source_u = field.zero()
previous = 0
checked = 0
for ordinal in range(1,1<<width):
    mask = ordinal ^ (ordinal>>1)
    changed = mask ^ previous
    assert changed.bit_count() == 1
    source_u += base_u[changed.bit_length()-1]
    previous = mask
    if mask not in valid:
        continue
    x_raw = 1+1/source_u
    # On y^2+xy=x^3+x^2+1, x(2P)=x(P)^2+x(P)^(-2).
    x_double = x_raw**2 + x_raw**(-2)
    assert x_double != 0
    px = x_double**2 + x_double**(-2)
    if checked < 8:
        lifts = curve.lift_x(x_raw,all=True)
        assert len(lifts) == 2
        projected = 4*lifts[0]
        assert projected != zero
        assert projected == -(4*lifts[1])
        assert projected[0] == px
        assert R*projected == zero
    checked += 1
    shift = 0
    for rotation in rotations:
        while shift < rotation:
            px = px**2
            shift += 1
        key = encode(px)
        if key in seen_x:
            raise ValueError("cofactor-projected signed point collision")
        seen_x.add(key)
assert checked == receipt["rational_masks"]
assert 2*len(seen_x) == receipt["actual_subgroup_factor_base_points_B"]
result = {
    "status":"PASS_EXACT_PROJECTED_GROUP_BASE",
    "curve_id":protocol["curve_id"],
    "raw_rational_source_masks":checked,
    "distinct_projected_x_coordinates":len(seen_x),
    "actual_subgroup_factor_base_points_B":2*len(seen_x),
    "subgroup_order_r":str(R),
    "checked_subgroup_order_on_first_points":min(checked,8),
    "projected_x_rule":"x2=x^2+x^(-2); x4=x2^2+x2^(-2), checked against eight Sage group multiplications",
    "source_sha256":{"support":sha(here/"support_w15.tsv"),
                     "support_audit":sha(here/"sage_support_audit.json"),
                     "params":sha(params_path),
                     "runtime":sha(here/"sage_runtime_info.json"),
                     "script":sha(Path(__file__))}}
with (here/"sage_group_audit.json").open("x") as out:
    json.dump(result,out,indent=2,sort_keys=True)
    out.write("\n")
print(json.dumps({"status":result["status"],"B":result["actual_subgroup_factor_base_points_B"]}))
