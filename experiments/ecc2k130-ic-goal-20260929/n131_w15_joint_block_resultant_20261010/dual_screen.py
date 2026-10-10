#!/usr/bin/env sage -python
"""Enumerate both N41 block-product domains and join their exact output roots."""

import hashlib
import json
import time
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
ROTATED=BASE/"n131_w15_rotated_fouratom_inverse_20261010/resultant.json"
FREEZE=HERE/"dual_protocol.json"


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


freeze=json.loads(FREEZE.read_text())
assert freeze["status"]=="FROZEN_BEFORE_N41_DUAL_PRODUCT_SCREEN"
assert freeze["sha256"]=={"dual_screen.py":sha(Path(__file__)),
    "result.json":sha(HERE/"result.json"),
    "rotated_resultant":sha(ROTATED),
    "sage_runtime_info":sha(HERE/"sage_runtime_info.json")}
assert not (HERE/"dual_result.json").exists()
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


def family_roots(seed,rotations):
    s=source_w(seed)
    a,b=(s**(2**r) for r in rotations)
    products={source_w(mask)*source_w(mask^seed) for mask in range(64)}
    assert len(products)==32
    first=sorted((value**(2**rotations[0]) for value in products),key=encode)
    second=sorted((value**(2**rotations[1]) for value in products),key=encode)
    started=time.perf_counter_ns()
    roots={}
    root_entries=0
    zero_polynomials=0
    zero_reciprocal_roots=0
    for p in first:
        for q in second:
            f=h(a,b,p,q)
            if f.is_zero():
                zero_polynomials+=1
                continue
            for root,multiplicity in f.roots():
                if root==0:
                    zero_reciprocal_roots+=1
                    continue
                roots.setdefault(encode(root),[]).append((encode(p),encode(q),int(multiplicity)))
                root_entries+=1
    return roots,{"families":len(first)*len(second),"root_entries":root_entries,
        "distinct_outputs":len(roots),"zero_polynomials":zero_polynomials,
        "zero_reciprocal_roots":zero_reciprocal_roots,
        "build_and_factor_ns":time.perf_counter_ns()-started}


roots_a,summary_a=family_roots(control["seed_a"],(10,15))
roots_b,summary_b=family_roots(control["seed_b"],(20,25))
known_products=control["known_products"]
known_za,known_zb=control["known_block_output_z"]
assert (known_products[0],known_products[1],1) in roots_a[known_za]
assert (known_products[2],known_products[3],1) in roots_b[known_zb]
rows=[]
for branch in control["branches"]:
    r=decode(branch["residual_z"])
    started=time.perf_counter_ns()
    output_pairs=[]
    product_family_pairs=0
    known_survives=False
    for za_encoded,families_a in roots_a.items():
        za=decode(za_encoded)
        u=(1+za**2*r**2)*z**2+za*r*z+(r**2+za**2)
        for zb,multiplicity in u.roots():
            if zb==0:continue
            zb_encoded=encode(zb)
            families_b=roots_b.get(zb_encoded)
            if families_b is None:continue
            product_family_pairs+=len(families_a)*len(families_b)
            is_known=(za_encoded==known_za and zb_encoded==known_zb and
                (known_products[0],known_products[1],1) in families_a and
                (known_products[2],known_products[3],1) in families_b)
            known_survives|=is_known
            output_pairs.append({"za":za_encoded,"zb":zb_encoded,
                "a_families":families_a,"b_families":families_b,
                "u_root_multiplicity":int(multiplicity),"known_witness":is_known})
    output_pairs.sort(key=lambda item:(item["za"],item["zb"]))
    assert not branch["matches_witness"] or known_survives
    rows.append({"branch":branch["branch"],"matches_witness":branch["matches_witness"],
        "output_pairs":output_pairs,"output_pair_count":len(output_pairs),
        "product_family_pair_count":product_family_pairs,
        "known_witness_survives":known_survives,
        "upper_join_ns":time.perf_counter_ns()-started})
record={"status":"COMPLETE_N41_DUAL_PRODUCT_SCREEN",
    "first_block":summary_a,"second_block":summary_b,
    "rows":rows,"protocol_sha256":sha(FREEZE)}
with (HERE/"dual_result.json").open("x") as output:
    json.dump(record,output,sort_keys=True,indent=2);output.write("\n")
print({"status":record["status"],
    "root_entries":[summary_a["root_entries"],summary_b["root_entries"]],
    "output_pairs_by_branch":[row["output_pair_count"] for row in rows]})
