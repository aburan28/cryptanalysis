#!/usr/bin/env sage -python
"""Exact offset-three W15 witness and joint-output eliminant control."""

import hashlib
import importlib.util
import json
import time
from pathlib import Path

from sage.all import EllipticCurve,GF,PolynomialRing

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
OLD=BASE/"n131_w15_coupled_sixpair_20261010"
LIFT=OLD/"w15_lift.py"
SUPPORT=OLD/"support_w15.tsv"
CONTROL=OLD/"control_group_lift.json"
ROTATED=BASE/"n131_w15_rotated_fouratom_inverse_20261010/resultant.json"
FREEZE=HERE/"restricted_protocol.json"


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


freeze=json.loads(FREEZE.read_text())
assert freeze["status"]=="FROZEN_BEFORE_N131_EIGHT_OFFSET_CONSTRUCTED_CONTROL"
assert freeze["sha256"]=={"restricted_control.py":sha(Path(__file__)),
    "w15_lift.py":sha(LIFT),"support_w15.tsv":sha(SUPPORT),
    "control_group_lift.json":sha(CONTROL),"rotated_resultant":sha(ROTATED),
    "sage_runtime_info":sha(HERE/"sage_runtime_info.json")}
assert not (HERE/"restricted_result.json").exists()
spec=importlib.util.spec_from_file_location("w15_restricted_lift",LIFT)
lift=importlib.util.module_from_spec(spec)
spec.loader.exec_module(lift)
columns,source_field,source_curve,basis_w,basis_u=lift.source()
old=json.loads(CONTROL.read_text())["solutions"][0]
old_masks=old["masks"]
assert len(old_masks)==12
seed_a=old_masks[4]^old_masks[5]
assert seed_a==old_masks[6]^old_masks[7]
seed_b=seed_a^3
used_columns={columns[mask] for mask in old_masks[:8]}
options=[]
for a in sorted(columns):
    b=a^seed_b
    if a>=b or b not in columns:continue
    ca,cb=columns[a],columns[b]
    if ca==cb or ca in used_columns or cb in used_columns:continue
    options.append((a,b,ca,cb))
first=options[0]
second=next(row for row in options[1:] if {row[2],row[3]}.isdisjoint({first[2],first[3]}))
masks=old_masks[:8]+[first[0],first[1],second[0],second[1]]
assert len({columns[mask] for mask in masks})==12
assert masks[8]^masks[9]==masks[10]^masks[11]==seed_b
assert (seed_a^seed_b)==3

ring=PolynomialRing(GF(2),"t")
t=ring.gen()
F=GF(2**131,"t",modulus=t**131+t**13+t**2+t+1)
E=EllipticCurve(F,[1,0,0,0,1])


def decode(value):return F(ring([(int(value)>>i)&1 for i in range(131)]))


def encode(value):return sum(int(bit)<<i for i,bit in enumerate(value.polynomial().list()))


def source_w(mask):return sum((F.gen()**(i+1) for i in range(15) if mask>>i&1),F.zero())


points=[E(decode(x),decode(y)) for x,y in old["raw_leaves"][:8]]
for block in (4,5):
    for mask in masks[2*block:2*block+2]:
        raw=lift.atom(source_field,source_curve,basis_w,basis_u,mask)
        rotated=lift.frobenius(source_field,raw,block*13)
        points.append(E(decode(rotated[0]),decode(rotated[1])))
assert len(points)==12 and all(point!=E(0) for point in points)
order=680564733841876926932320129493409985129
raw_total=sum(points,E(0))
public=4*raw_total
assert public!=E(0) and order*public==E(0)
t4=E(F.one(),F.zero())
assert 4*t4==E(0) and 2*t4!=E(0)
branches=[pow(4,-1,order)*public+i*t4 for i in range(4)]
matching=[i for i,branch in enumerate(branches) if branch==raw_total]
assert len(matching)==1
free_sum=sum(points[:4],E(0))
block_a=sum(points[4:8],E(0))
block_b=sum(points[8:12],E(0))
assert block_a+block_b==raw_total-free_sum
assert block_a[0]!=0 and block_b[0]!=0
za,zb=1/block_a[0],1/block_b[0]


def parameters(r0,r1,part):
    s=part[0]^part[1]
    assert s==part[2]^part[3]
    sf=source_w(s)
    a,b=sf**(2**r0),sf**(2**r1)
    p=(source_w(part[0])*source_w(part[1]))**(2**r0)
    q=(source_w(part[2])*source_w(part[3]))**(2**r1)
    return a,b,p,q


a0,a1,pa,qa=parameters(26,39,masks[4:8])
b0,b1,pb,qb=parameters(52,65,masks[8:12])
terms=json.loads(ROTATED.read_text())["terms"]
poly=PolynomialRing(F,"z")
z=poly.gen()


def h(a,b,p,q):
    ap,bp,pp,qp=([v**i for i in range(9)] for v in (a,b,p,q))
    coeff=[F.zero() for _ in range(9)]
    for ea,eb,ep,eq,ez in terms:coeff[ez]+=ap[ea]*bp[eb]*pp[ep]*qp[eq]
    return poly(coeff)


ha=h(a0,a1,pa,qa)
hb=h(b0,b1,pb,qb)
assert ha(za)==0 and hb(zb)==0
ring_d=PolynomialRing(poly,"d")
d=ring_d.gen()
hbd=ring_d([poly(v) for v in hb.list()])
rows=[]
for i,branch in enumerate(branches):
    residual=branch-free_sum
    assert residual!=E(0) and residual[0]!=0
    zr=1/residual[0]
    u=(1+z**2*zr**2)*d**2+z*zr*d+(zr**2+z**2)
    started=time.perf_counter_ns()
    k=poly(hbd.resultant(u))
    elapsed=time.perf_counter_ns()-started
    g=ha.gcd(k)
    if i==matching[0]:
        assert k(za)==0 and g.degree()>0
        assert (1+za**2*zb**2)*zr**2+za*zb*zr+(za+zb)**2==0
    rows.append({"branch":i,"matches_witness":i==matching[0],
                 "residual_z":encode(zr),"joint_eliminant_degree":int(k.degree()),
                 "joint_gcd_degree":int(g.degree()),"eliminant_ns":elapsed})
record={"status":"PASS_N131_OFFSET_THREE_CONSTRUCTED_JOINT_BLOCK_CONTROL",
        "field_degree":131,"source_dimension":15,"subgroup_order":str(order),
        "masks":masks,"folded_columns":[columns[mask] for mask in masks],
        "signs":old["signs"][:8]+[0,0,0,0],"seed_a":seed_a,"seed_b":seed_b,
        "cross_block_seed_offset":seed_a^seed_b,
        "raw_leaves":[[encode(point[0]),encode(point[1])] for point in points],
        "public_target":[encode(public[0]),encode(public[1])],
        "raw_total":[encode(raw_total[0]),encode(raw_total[1])],
        "known_block_output_z":[encode(za),encode(zb)],
        "known_products":[encode(pa),encode(qa),encode(pb),encode(qb)],
        "matching_branch":matching[0],"branches":rows,
        "protocol_sha256":sha(FREEZE),"source_sha256":freeze["sha256"]}
with (HERE/"restricted_result.json").open("x") as output:
    json.dump(record,output,sort_keys=True,indent=2);output.write("\n")
print({"status":record["status"],"masks":masks,
       "branches":[(row["branch"],row["joint_gcd_degree"]) for row in rows]})
