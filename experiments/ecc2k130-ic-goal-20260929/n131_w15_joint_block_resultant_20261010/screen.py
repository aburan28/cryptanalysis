#!/usr/bin/env sage -python
"""Exact N41 target-residual screen of all first-block product families."""

import hashlib
import json
import time
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
ROTATED=BASE/"n131_w15_rotated_fouratom_inverse_20261010/resultant.json"
FREEZE=HERE/"screen_protocol.json"


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


freeze=json.loads(FREEZE.read_text())
assert freeze["status"]=="FROZEN_BEFORE_N41_JOINT_PRODUCT_FAMILY_SCREEN"
assert freeze["sha256"]=={"screen.py":sha(Path(__file__)),
                           "result.json":sha(HERE/"result.json"),
                           "rotated_resultant":sha(ROTATED),
                           "sage_runtime_info":sha(HERE/"sage_runtime_info.json")}
assert not (HERE/"screen_result.json").exists()
terms=json.loads(ROTATED.read_text())["terms"]
control=json.loads((HERE/"result.json").read_text())["n41"]
ring=PolynomialRing(GF(2),"t")
t=ring.gen()
F=GF(2**41,"t",modulus=t**41+t**3+1)
poly=PolynomialRing(F,"z")
z=poly.gen()


def decode(value):
    return F(ring([(int(value)>>i)&1 for i in range(41)]))


def encode(value):
    return sum(int(bit)<<i for i,bit in enumerate(value.polynomial().list()))


def source_w(mask):
    return sum((F.gen()**(i+1) for i in range(6) if mask>>i&1),F.zero())


def h(a,b,p,q):
    ap,bp,pp,qp=([v**i for i in range(9)] for v in (a,b,p,q))
    coeff=[F.zero() for _ in range(9)]
    for ea,eb,ep,eq,ez in terms:coeff[ez]+=ap[ea]*bp[eb]*pp[ep]*qp[eq]
    return poly(coeff)


def eliminant(hb,residual_z):
    ring_d=PolynomialRing(poly,"d")
    d=ring_d.gen()
    u=(1+z**2*residual_z**2)*d**2+z*residual_z*d+(residual_z**2+z**2)
    return poly(ring_d([poly(v) for v in hb.list()]).resultant(u))


seed_a=source_w(control["seed_a"])
seed_b=source_w(control["seed_b"])
a,b=seed_a**(2**10),seed_a**(2**15)
c,d=seed_b**(2**20),seed_b**(2**25)
pa,qa,pb,qb=map(decode,control["known_products"])
hb=h(c,d,pb,qb)
base_products={w*(w+seed_a) for w in (source_w(mask) for mask in range(64))}
assert len(base_products)==32
left=sorted((v**(2**10) for v in base_products),key=encode)
right=sorted((v**(2**15) for v in base_products),key=encode)
all_families=[(p,q) for p in left for q in right]
assert len(all_families)==1024 and (pa,qa) in all_families
start=time.perf_counter_ns()
family_polynomials=[h(a,b,p,q) for p,q in all_families]
build_ns=time.perf_counter_ns()-start
rows=[]
for branch in control["branches"]:
    residual_z=decode(branch["residual_z"])
    start=time.perf_counter_ns()
    k=eliminant(hb,residual_z)
    setup_ns=time.perf_counter_ns()-start
    assert int(k.degree())==branch["joint_eliminant_degree"]
    start=time.perf_counter_ns()
    survivors=[]
    zero_h=0
    for (p,q),ha in zip(all_families,family_polynomials):
        if ha.is_zero():zero_h+=1
        if ha.gcd(k).degree()>0:survivors.append([encode(p),encode(q)])
    screen_ns=time.perf_counter_ns()-start
    known=[encode(pa),encode(qa)] in survivors
    if branch["matches_witness"]:assert known
    rows.append({"branch":branch["branch"],"matches_witness":branch["matches_witness"],
                 "families_checked":len(all_families),"survivors":len(survivors),
                 "known_family_survives":known,"zero_h_families":zero_h,
                 "surviving_product_pairs":survivors,
                 "joint_eliminant_degree":int(k.degree()),
                 "eliminant_ns":setup_ns,"screen_ns":screen_ns})
record={"status":"COMPLETE_N41_JOINT_PRODUCT_FAMILY_SCREEN",
        "fixed_second_block_products":list(map(encode,(pb,qb))),
        "total_first_block_product_families":1024,"first_block_poly_build_ns":build_ns,
        "rows":rows,"protocol_sha256":sha(FREEZE)}
with (HERE/"screen_result.json").open("x") as output:
    json.dump(record,output,sort_keys=True,indent=2);output.write("\n")
print({"status":record["status"],"survivors_by_branch":[(x["branch"],x["survivors"]) for x in rows]})
