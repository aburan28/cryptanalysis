#!/usr/bin/env sage -python
"""Enumerate algebraic mixed-rotation four-atom outputs and their exact polynomial."""
import hashlib
import json
import time
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
REPLAY=BASE/"n41_seed_partition_indexless_20261010/replay_result.json"


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


freeze=json.loads((HERE/"protocol.json").read_text())
assert freeze["status"]=="FROZEN_BEFORE_N41_FOURATOM_BUCKET_CENSUS"
assert freeze["source_sha256"]=={
    "produce.py":digest(Path(__file__)),
    "run.py":digest(HERE/"run.py"),
    "replay_result.json":digest(REPLAY),
    "sage_runtime_info.json":digest(HERE/"sage_runtime_info.json")}
assert not (HERE/"result.json").exists()

base=PolynomialRing(GF(2),"t")
t=base.gen()
F=GF(2**41,"t",modulus=t**41+t**3+1)
R=PolynomialRing(F,"z")
z=R.gen()
seed=2
rotations=(20,25)


def encode(value):return sum(int(bit)<<i for i,bit in enumerate(value.polynomial().list()))


def decode(bits):return F(base([(int(bits)>>i)&1 for i in range(41)]))


def w(mask,d):return sum((F.gen()**(i+1) for i in range(d) if mask>>i&1),F.zero())


def halftrace(value):
    acc=F.zero()
    power=value
    for _ in range(21):
        acc+=power
        power=power**4
    return acc if acc*acc+acc==value else None


def roots(b,c):
    # (1+b²)X²+bX+c=0.
    if b==0:return [c.sqrt()]
    if b==1:return [c]
    aa=1+b*b
    h=halftrace(aa*c/(b*b))
    if h is None:return []
    scale=b/aa
    return [scale*h,scale*(h+1)]


def output_domain(d,rotation):
    s=w(seed,d)**(2**rotation)
    products={w(mask,d)**2+w(seed,d)*w(mask,d) for mask in range(1<<d)}
    assert len(products)==1<<(d-1)
    values=set()
    raw_count=0
    for p in products:
        p=p**(2**rotation)
        options=roots(p,s*s)
        raw_count+=len(options)
        values.update(options)
    values.discard(F.zero())
    return values,len(products),raw_count


def product_polynomial(values):
    layer=[z+value for value in sorted(values,key=encode)]
    if not layer:return R.one(),0
    levels=0
    while len(layer)>1:
        layer=[layer[i]*layer[i+1] if i+1<len(layer) else layer[i]
               for i in range(0,len(layer),2)]
        levels+=1
    return layer[0],levels


replay=json.loads(REPLAY.read_text())
assert replay["status"]=="PASS_N41_SEED_PARTITION_PUBLIC_RELATION_SAGE"
rows=replay["normalized_pair_equations"][4:6]
assert [(row["seed"],row["rotation"]) for row in rows]==[(2,20),(2,25)]
known_c,known_d=[decode(row["normalized_c"])**(2**row["rotation"]) for row in rows]
known_outputs=set(roots(known_c*known_d,(known_c+known_d)**2))
known_outputs.discard(F.zero())
assert known_outputs
results=[]
for d in freeze["source_dimensions"]:
    started=time.perf_counter_ns()
    left,p_count,left_raw=output_domain(d,rotations[0])
    right,p_count_2,right_raw=output_domain(d,rotations[1])
    assert p_count==p_count_2
    pair_count=len(left)*len(right)
    outputs=set()
    root_count=0
    zero_count=0
    for c in left:
        for e in right:
            zz=roots(c*e,(c+e)**2)
            root_count+=len(zz)
            for candidate in zz:
                if candidate==0:zero_count+=1
                else:outputs.add(candidate)
    enumerated_ns=time.perf_counter_ns()-started
    poly,levels=product_polynomial(outputs)
    assert poly.degree()==len(outputs)
    assert all(poly(value)==0 for value in list(outputs)[:min(32,len(outputs))])
    digest_coeff=hashlib.sha256()
    for coefficient in poly.list():
        digest_coeff.update(encode(coefficient).to_bytes(6,"little"))
    row={"source_dimension":d,"seed":seed,"rotations":list(rotations),
         "product_image_count":p_count,
         "pair_output_raw_root_count":[left_raw,right_raw],
         "pair_output_distinct_count":[len(left),len(right)],
         "cross_output_pairs":pair_count,"upper_raw_root_count":root_count,
         "upper_zero_root_count":zero_count,
         "distinct_nonzero_block_outputs":len(outputs),
         "polynomial_degree":int(poly.degree()),
         "polynomial_nonzero_coefficients":len(poly.dict()),
         "polynomial_coefficient_density_num":len(poly.dict()),
         "polynomial_coefficient_density_den":int(poly.degree())+1,
         "polynomial_dense_coefficient_sha256":digest_coeff.hexdigest(),
         "balanced_product_levels":levels,
         "known_n41_public_witness_output_root":
             any(poly(value)==0 for value in known_outputs) if d==6 else None,
         "enumeration_ns":enumerated_ns,
         "elapsed_ns":time.perf_counter_ns()-started}
    if d==6:assert row["known_n41_public_witness_output_root"]
    results.append(row)
    print({"dimension":d,"block_outputs":row["distinct_nonzero_block_outputs"],
           "nonzero_coefficients":row["polynomial_nonzero_coefficients"],
           "elapsed_s":row["elapsed_ns"]/1e9},flush=True)

result={"status":"PASS_N41_FOURATOM_BUCKET_POLYNOMIAL_CENSUS",
        "field_degree":41,"field_modulus":"t^41+t^3+1",
        "curve_model":"y^2+x*y=x^3+1",
        "seed":seed,"rotations":list(rotations),"rows":results,
        "source_sha256":freeze["source_sha256"],
        "protocol_sha256":digest(HERE/"protocol.json"),
        "candidate_id":None}
with (HERE/"result.json").open("x") as stream:
    json.dump(result,stream,sort_keys=True,indent=2)
    stream.write("\n")
print(result["status"],flush=True)
