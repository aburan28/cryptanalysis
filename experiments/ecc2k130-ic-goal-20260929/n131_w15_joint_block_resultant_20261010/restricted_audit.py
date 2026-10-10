#!/usr/bin/env sage -python
"""Independently replay the saved N131 offset-three witness and joint roots."""

import hashlib
import importlib.util
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
OLD=BASE/"n131_w15_coupled_sixpair_20261010"
LIFT=OLD/"w15_lift.py"
SUPPORT=OLD/"support_w15.tsv"
ROTATED=BASE/"n131_w15_rotated_fouratom_inverse_20261010/resultant.json"
FREEZE=HERE/"restricted_audit_protocol.json"


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


freeze=json.loads(FREEZE.read_text())
assert freeze["status"]=="FROZEN_BEFORE_N131_EIGHT_OFFSET_REPLAY"
assert freeze["sha256"]=={"restricted_audit.py":sha(Path(__file__)),
    "restricted_result.json":sha(HERE/"restricted_result.json"),
    "w15_lift.py":sha(LIFT),"support_w15.tsv":sha(SUPPORT),
    "rotated_resultant":sha(ROTATED),
    "sage_runtime_info":sha(HERE/"sage_runtime_info.json")}
assert not (HERE/"restricted_audit_result.json").exists()
record=json.loads((HERE/"restricted_result.json").read_text())
spec=importlib.util.spec_from_file_location("w15_replay_lift",LIFT)
lift=importlib.util.module_from_spec(spec)
spec.loader.exec_module(lift)
columns,source_field,source_curve,basis_w,basis_u=lift.source()
ring=PolynomialRing(GF(2),"t")
t=ring.gen()
F=GF(2**131,"t",modulus=t**131+t**13+t**2+t+1)
E=EllipticCurve(F,[1,0,0,0,1])
zero=E(0)


def decode(value):return F(ring([(int(value)>>i)&1 for i in range(131)]))


def encode(value):return sum(int(bit)<<i for i,bit in enumerate(value.polynomial().list()))


def point(pair):return E(decode(pair[0]),decode(pair[1]))


def source_w(mask):
    return sum((F.gen()**(i+1) for i in range(15) if mask>>i&1),F.zero())


masks=record["masks"]
assert len(masks)==12
assert [columns[mask] for mask in masks]==record["folded_columns"]
assert len(set(record["folded_columns"]))==12
assert masks[4]^masks[5]==masks[6]^masks[7]==record["seed_a"]
assert masks[8]^masks[9]==masks[10]^masks[11]==record["seed_b"]
assert record["seed_a"]^record["seed_b"]==3
saved=[point(pair) for pair in record["raw_leaves"]]
for i in range(8,12):
    raw=lift.atom(source_field,source_curve,basis_w,basis_u,masks[i])
    rotated=lift.frobenius(source_field,raw,13*(i//2))
    assert saved[i]==E(decode(rotated[0]),decode(rotated[1]))
assert sum(saved,zero)==point(record["raw_total"])
public=point(record["public_target"])
order=int(record["subgroup_order"])
assert public==4*sum(saved,zero) and order*public==zero
t4=E(F.one(),F.zero())
assert 4*t4==zero and 2*t4!=zero
branches=[pow(4,-1,order)*public+i*t4 for i in range(4)]
assert branches[record["matching_branch"]]==sum(saved,zero)
free_sum=sum(saved[:4],zero)
block_a=sum(saved[4:8],zero)
block_b=sum(saved[8:12],zero)
za,zb=1/block_a[0],1/block_b[0]
assert [encode(za),encode(zb)]==record["known_block_output_z"]
terms=json.loads(ROTATED.read_text())["terms"]
poly=PolynomialRing(F,"z")
z=poly.gen()


def h(part,rotations):
    s0,s1=part[0]^part[1],part[2]^part[3]
    assert s0==s1
    a,b=(source_w(s0)**(2**r) for r in rotations)
    p=(source_w(part[0])*source_w(part[1]))**(2**rotations[0])
    q=(source_w(part[2])*source_w(part[3]))**(2**rotations[1])
    powers=([v**i for i in range(9)] for v in (a,b,p,q))
    aa,bb,pp,qq=powers
    coeff=[F.zero() for _ in range(9)]
    for ea,eb,ep,eq,ez in terms:coeff[ez]+=aa[ea]*bb[eb]*pp[ep]*qq[eq]
    return poly(coeff),(encode(p),encode(q))


ha,products_a=h(masks[4:8],(26,39))
hb,products_b=h(masks[8:12],(52,65))
assert list(products_a+products_b)==record["known_products"]
assert ha(za)==0 and hb(zb)==0
dpoly=PolynomialRing(poly,"d")
d=dpoly.gen()
hbd=dpoly([poly(v) for v in hb.list()])
branch_degrees=[]
for row,branch in zip(record["branches"],branches):
    assert row["branch"]==len(branch_degrees)
    residual=branch-free_sum
    r=1/residual[0]
    assert encode(r)==row["residual_z"]
    u=(1+z**2*r**2)*d**2+z*r*d+(r**2+z**2)
    k=poly(hbd.resultant(u))
    degree=int(ha.gcd(k).degree())
    assert degree==row["joint_gcd_degree"]
    if row["matches_witness"]:
        assert k(za)==0 and degree>0
        assert (1+za**2*zb**2)*r**2+za*zb*r+(za+zb)**2==0
    branch_degrees.append(degree)
assert branch_degrees==[0,0,1,0]
out={"status":"PASS_N131_EIGHT_OFFSET_INDEPENDENT_REPLAY",
    "public_target":record["public_target"],
    "matching_branch":record["matching_branch"],
    "joint_gcd_degrees":branch_degrees,
    "distinct_folded_columns":len(set(record["folded_columns"])),
    "protocol_sha256":sha(FREEZE)}
with (HERE/"restricted_audit_result.json").open("x") as output:
    json.dump(out,output,sort_keys=True,indent=2);output.write("\n")
print(out)
