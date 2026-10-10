#!/usr/bin/env sage -python
"""One-sided W15 product enumeration with exact Artin-Schreier bucket joins."""
import hashlib
import json
import time
from pathlib import Path

from sage.all import EllipticCurve,GF,PolynomialRing

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
RESTRICTED=BASE/"n131_w15_joint_block_resultant_20261010/restricted_result.json"
SUPPORT=BASE/"n131_w15_coupled_sixpair_20261010/support_w15.tsv"
SPARSE=BASE/"n131_w15_pair_bucket_polynomial_20261010/polynomial_sparse_v3.json"


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


protocol=json.loads((HERE/"protocol_as.json").read_text())
assert protocol["status"]=="FROZEN_BEFORE_N131_W15_AS_JOIN"
assert protocol["source_sha256"]=={
    "n131_as_join.py":digest(Path(__file__)),
    "run_as.py":digest(HERE/"run_as.py"),
    "restricted_result.json":digest(RESTRICTED),
    "support_w15.tsv":digest(SUPPORT),
    "polynomial_sparse_v3.json":digest(SPARSE),
    "sage_runtime_info.json":digest(HERE/"sage_runtime_info.json")}
assert not (HERE/"as_result.json").exists()
started=time.perf_counter_ns()

base=PolynomialRing(GF(2),"t")
t=base.gen()
F=GF(2**131,"t",modulus=t**131+t**13+t**2+t+1)
E=EllipticCurve(F,[1,0,0,0,1])


def decode(bits):return F(base([(int(bits)>>i)&1 for i in range(131)]))


def encode(value):return sum(int(bit)<<i for i,bit in enumerate(value.polynomial().list()))


def since():return (time.perf_counter_ns()-started)/1e9


def batch_inverse(values):
    assert all(value!=0 for value in values)
    prefix=[]
    product=F.one()
    for value in values:
        prefix.append(product)
        product*=value
    inverse=1/product
    result={}
    for value,head in zip(reversed(values),reversed(prefix)):
        result[value]=inverse*head
        inverse*=value
    assert inverse==1
    return result


def halftrace(value):
    acc=F.zero()
    power=value
    for _ in range(66):
        acc+=power
        power=power**4
    return acc if acc*acc+acc==value else None


def quadratic_outputs(b,c,inv_b,inv_one_plus_b):
    # Solve (1+b^2)x^2+b*x+c=0 in GF(2^131).
    if b==0:return [c.sqrt()]
    if b==1:return [c]
    aa=1+b*b
    value=aa*c*inv_b*inv_b
    h=halftrace(value)
    if h is None:return []
    scale=b*inv_one_plus_b*inv_one_plus_b
    return [scale*h,scale*(h+1)]


control=json.loads(RESTRICTED.read_text())
assert control["status"]=="PASS_N131_OFFSET_THREE_CONSTRUCTED_JOINT_BLOCK_CONTROL"
assert control["seed_a"]==13686
support={int(mask):int(column) for mask,column in
         (line.split() for line in SUPPORT.read_text().splitlines())}
assert len(support)==16441
points=[E(decode(x),decode(y)) for x,y in control["raw_leaves"][4:8]]
known_ca=1/(points[0]+points[1])[0]
known_cb=1/(points[2]+points[3])[0]
known_r=decode(control["known_block_output_z"][0])
assert (1+known_ca**2*known_cb**2)*known_r**2+known_ca*known_cb*known_r+(known_ca+known_cb)**2==0
print({"phase":"control_ready","elapsed_s":since()},flush=True)

seed=13686
source_basis=[F.gen()**(i+1) for i in range(15)]
w=[F.zero() for _ in range(1<<15)]
for mask in range(1,1<<15):
    lsb=mask&-mask
    w[mask]=w[mask^lsb]+source_basis[lsb.bit_length()-1]
assert w[seed]!=0
source_products=[]
for mask in range(1<<15):
    partner=mask^seed
    if mask>=partner:continue
    if mask not in support or partner not in support:continue
    if support[mask]==support[partner]:continue
    source_products.append((w[mask]*w[partner],mask,partner))
assert any({m,n}==set(control["masks"][4:6]) for _,m,n in source_products)
assert any({m,n}==set(control["masks"][6:8]) for _,m,n in source_products)
left_map={p**(2**26):(m,n) for p,m,n in source_products}
right_map={p**(2**39):(m,n) for p,m,n in source_products}
assert len(left_map)==len(right_map)==len(source_products)
left_seed=w[seed]**(2**26)
right_seed=w[seed]**(2**39)
print({"phase":"product_maps_ready","usable_product_pairs":len(source_products),
       "elapsed_s":since()},flush=True)

right_b=list(right_map)
invert_values=list({v for b in right_b for v in (b,1+b) if v!=0})
inverses=batch_inverse(invert_values)
right_outputs={}
for b in right_b:
    for d in quadratic_outputs(b,right_seed*right_seed,
                               inverses.get(b),inverses.get(1+b)):
        if d!=0:right_outputs.setdefault(d,[]).append(b)
assert known_cb in right_outputs
print({"phase":"right_outputs_ready","distinct_outputs":len(right_outputs),
       "elapsed_s":since()},flush=True)


def join(residual,label):
    stage=time.perf_counter_ns()
    d_values=list(right_outputs)
    inv_values=list({v for d in d_values for v in (d*residual,1+d*residual) if v!=0})
    inv_b=batch_inverse(inv_values)
    upper_candidates=[]
    for d in d_values:
        b=d*residual
        c0=(d+residual)**2
        for c in quadratic_outputs(b,c0,inv_b.get(b),inv_b.get(1+b)):
            if c!=0:upper_candidates.append((c,d))
    c_values=list({c for c,_ in upper_candidates})
    inv_c=batch_inverse(c_values)
    hits=[]
    left_checked={}
    for c,d in upper_candidates:
        if c not in left_checked:
            h=halftrace(c*c+left_seed*left_seed)
            matches=[]
            if h is not None:
                for z in (h,h+1):
                    p=z*inv_c[c]
                    if p in left_map:matches.append(p)
            left_checked[c]=matches
        for p_left in left_checked[c]:
            for p_right in right_outputs[d]:
                hits.append({"left_output":encode(c),"right_output":encode(d),
                             "left_masks":list(left_map[p_left]),
                             "right_masks":list(right_map[p_right]),
                             "left_product":encode(p_left),
                             "right_product":encode(p_right)})
    known=[hit for hit in hits if hit["left_output"]==encode(known_ca)
           and hit["right_output"]==encode(known_cb)
           and set(hit["left_masks"])==set(control["masks"][4:6])
           and set(hit["right_masks"])==set(control["masks"][6:8])]
    row={"upper_candidates":len(upper_candidates),"distinct_left_outputs":len(c_values),
         "bucket_hits":hits,"bucket_hit_count":len(hits),
         "known_witness_count":len(known),
         "elapsed_ns":time.perf_counter_ns()-stage}
    print({"phase":label+"_complete","upper_candidates":len(upper_candidates),
           "bucket_hits":len(hits),"elapsed_s":since()},flush=True)
    return row


positive=join(known_r,"positive")
assert positive["known_witness_count"]>=1
negative_r=F.gen()+1
assert (1+known_ca**2*known_cb**2)*negative_r**2+known_ca*known_cb*negative_r+(known_ca+known_cb)**2!=0
negative=join(negative_r,"negative")
result={"status":"PASS_N131_W15_ONE_SIDED_AS_JOIN_CONTROLS",
        "field_degree":131,"source_dimension":15,"seed":seed,
        "actual_source_support_masks":len(support),
        "usable_product_pairs":len(source_products),
        "right_output_count":len(right_outputs),
        "positive_residual":encode(known_r),"negative_residual":encode(negative_r),
        "positive":positive,"negative":negative,
        "elapsed_ns":time.perf_counter_ns()-started,
        "source_sha256":protocol["source_sha256"],
        "protocol_sha256":digest(HERE/"protocol_as.json"),"candidate_id":None}
with (HERE/"as_result.json").open("x") as stream:
    json.dump(result,stream,sort_keys=True,indent=2)
    stream.write("\n")
print({"status":result["status"],"positive_hits":positive["bucket_hit_count"],
       "negative_hits":negative["bucket_hit_count"],
       "elapsed_s":result["elapsed_ns"]/1e9},flush=True)
