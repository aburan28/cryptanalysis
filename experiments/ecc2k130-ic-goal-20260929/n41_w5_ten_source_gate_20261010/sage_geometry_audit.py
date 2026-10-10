#!/usr/bin/env sage -python
"""Independent Sage replay of N41 W5 rational masks and projected base."""
import hashlib
import json
from pathlib import Path
from sage.all import EllipticCurve, GF, PolynomialRing

here = Path(__file__).resolve().parent
sha = lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p = json.loads((here/"geometry_protocol_v2.json").read_text())
g = json.loads((here/"geometry_result.json").read_text())
runtime = json.loads((here/"sage_runtime_info.json").read_text())
assert p["status"] == "FROZEN_BEFORE_ENUMERATION"
assert runtime["status"] == "verified"
F2=GF(2)
ring=PolynomialRing(F2,"t")
t=ring.gen()
field=GF(2**41,name="t",modulus=t**41+t**3+1)
curve=EllipticCurve(field,[1,0,0,0,1])
zero=curve(0)
R=int(g["subgroup_order_r"])
def encode(v):
    return sum(int(bit)<<i for i,bit in enumerate(v.polynomial().list()))
def decode(v):
    return field(ring([(int(v)>>i)&1 for i in range(41)]))
def point(v):
    return curve(decode(v[0]),decode(v[1]))
def key(v):
    return [encode(v[0]),encode(v[1])]
def frob(v):
    return curve(v[0]**2,v[1]**2)
def column(v):
    projected=4*v
    assert projected != zero
    entries=[]
    for _ in range(41):
        entries.extend((tuple(key(projected)),tuple(key(-projected))))
        projected=frob(projected)
    return list(min(entries))
source=[field.gen()**i for i in range(1,6)]
halves=[]
for w in source:
    acc,term=field.zero(),w
    for _ in range(21):
        acc += term
        term=term**4
    assert acc**2+acc == w
    halves.append(acc)
assert [encode(v) for v in halves] == g["source_basis_u"]
q=point(g["public_target_q"])
assert q!=zero and R*q==zero
raw={}
columns={}
projected_points=set()
for mask in range(1,32):
    w=sum((source[i] for i in range(5) if mask>>i&1),field.zero())
    if int((1/w).trace()):
        continue
    u=sum((halves[i] for i in range(5) if mask>>i&1),field.zero())
    assert u**2+u==w and u not in (0,1)
    choices=sorted(curve.lift_x(1+1/u,all=True),key=lambda v:tuple(key(v)))
    assert len(choices)==2
    raw[str(mask)]=[key(v) for v in choices]
    assert column(choices[0])==column(choices[1])
    columns[str(mask)]=column(choices[0])
    for v in choices:
        base=4*v
        shift=0
        for rotation in p["rotations"]:
            while shift<rotation:
                base=frob(base)
                shift+=1
            projected_points.add(tuple(key(base)))
assert raw==g["raw_points"]
assert columns==g["mask_columns"]
assert len(raw)==g["rational_source_masks"]==17
assert len({tuple(v) for v in columns.values()})==g["folded_columns_K"]==14
assert len(projected_points)==g["actual_subgroup_factor_base_points_B"]==340
result={"status":"PASS_EXACT_SAGE_GEOMETRY_AND_GROUP_BASE",
        "rational_masks":len(raw),"folded_columns_K":g["folded_columns_K"],
        "actual_subgroup_factor_base_points_B":len(projected_points),
        "public_target_q":key(q),
        "source_sha256":{"geometry":sha(here/"geometry_result.json"),
                         "protocol":sha(here/"geometry_protocol_v2.json"),
                         "runtime":sha(here/"sage_runtime_info.json"),
                         "script":sha(Path(__file__))}}
with (here/"sage_geometry_audit.json").open("x") as f:
    json.dump(result,f,indent=2,sort_keys=True);f.write("\n")
print(json.dumps({"status":result["status"],"B":len(projected_points),"K":g["folded_columns_K"]}))
