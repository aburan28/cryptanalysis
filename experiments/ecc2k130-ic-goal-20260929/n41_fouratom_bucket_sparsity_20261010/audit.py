"""Independent integer-field census and dense-polynomial replay."""
import hashlib
import json
import time
from pathlib import Path

HERE=Path(__file__).resolve().parent
RESULT=HERE/"result.json"
MODULUS=(1<<41)|(1<<3)|1
FIELD_MASK=(1<<41)-1


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


freeze=json.loads((HERE/"audit_protocol.json").read_text())
assert freeze["status"]=="FROZEN_BEFORE_N41_INTEGER_FIELD_REPLAY"
assert freeze["source_sha256"]=={
    "audit.py":digest(Path(__file__)),
    "run_audit.py":digest(HERE/"run_audit.py"),
    "result.json":digest(RESULT)}
assert not (HERE/"audit_result.json").exists()


def mul(a,b):
    out=0
    while b:
        if b&1:out^=a
        b>>=1
        a<<=1
        if a&(1<<41):a^=MODULUS
    return out&FIELD_MASK


def square(a):return mul(a,a)


def power(a,e):
    out=1
    while e:
        if e&1:out=mul(out,a)
        e>>=1
        if e:a=square(a)
    return out


def inverse(a):
    assert a
    return power(a,(1<<41)-2)


def frobenius(a,k):
    for _ in range(k):a=square(a)
    return a


def halftrace(value):
    acc=0
    p=value
    for _ in range(21):
        acc^=p
        p=square(square(p))
    return acc if square(acc)^acc==value else None


def roots(b,c):
    if b==0:return [frobenius(c,40)]
    if b==1:return [c]
    aa=1^square(b)
    ib=inverse(b)
    value=mul(mul(aa,c),square(ib))
    h=halftrace(value)
    if h is None:return []
    scale=mul(b,inverse(aa))
    return [mul(scale,h),mul(scale,h^1)]


def pair_outputs(d,rotation):
    s=frobenius(4,rotation)
    products={square(mask<<1)^mul(4,mask<<1) for mask in range(1<<d)}
    assert len(products)==1<<(d-1)
    outputs=set()
    root_count=0
    for p in products:
        pp=frobenius(p,rotation)
        found=roots(pp,square(s))
        root_count+=len(found)
        outputs.update(found)
    outputs.discard(0)
    return outputs,len(products),root_count


def coefficient_digest(output_roots):
    coeff=[1]
    for root in sorted(output_roots):
        next_coeff=[0]*(len(coeff)+1)
        for i,value in enumerate(coeff):
            next_coeff[i]^=mul(value,root)
            next_coeff[i+1]^=value
        coeff=next_coeff
    sha=hashlib.sha256()
    for value in coeff:sha.update(value.to_bytes(6,"little"))
    return sha.hexdigest(),sum(value!=0 for value in coeff)


started=time.perf_counter()
source=json.loads(RESULT.read_text())
assert source["status"]=="PASS_N41_FOURATOM_BUCKET_POLYNOMIAL_CENSUS"
checks=[]
for row in source["rows"]:
    d=row["source_dimension"]
    left,p_count,left_raw=pair_outputs(d,20)
    right,p_count2,right_raw=pair_outputs(d,25)
    assert p_count==p_count2==row["product_image_count"]
    assert [left_raw,right_raw]==row["pair_output_raw_root_count"]
    assert [len(left),len(right)]==row["pair_output_distinct_count"]
    outputs=set()
    raw=0
    zero=0
    for c in left:
        for e in right:
            found=roots(mul(c,e),square(c^e))
            raw+=len(found)
            for value in found:
                if value==0:zero+=1
                else:outputs.add(value)
    assert raw==row["upper_raw_root_count"]
    assert zero==row["upper_zero_root_count"]
    assert len(outputs)==row["polynomial_degree"]
    sha,nonzero=coefficient_digest(outputs)
    assert sha==row["polynomial_dense_coefficient_sha256"]
    assert nonzero==row["polynomial_nonzero_coefficients"]
    checks.append({"source_dimension":d,"product_image_count":p_count,
                   "left_output_count":len(left),"right_output_count":len(right),
                   "block_output_count":len(outputs),
                   "polynomial_nonzero_coefficients":nonzero,
                   "dense_coefficient_sha256":sha})
    print({"dimension":d,"block_outputs":len(outputs),
           "elapsed_s":time.perf_counter()-started},flush=True)
record={"status":"PASS_N41_FOURATOM_BUCKET_INDEPENDENT_INTEGER_FIELD_REPLAY",
        "rows":checks,"elapsed_s":time.perf_counter()-started,
        "source_sha256":freeze["source_sha256"],
        "protocol_sha256":digest(HERE/"audit_protocol.json")}
with (HERE/"audit_result.json").open("x") as stream:
    json.dump(record,stream,sort_keys=True,indent=2)
    stream.write("\n")
print(record["status"],flush=True)
