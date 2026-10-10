#!/usr/bin/env sage -python
"""Target-conditioned W15 pair-bucket intersection in the second-bucket quotient."""
import hashlib
import json
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
RESTRICTED=BASE/"n131_w15_joint_block_resultant_20261010/restricted_result.json"
SPARSE=BASE/"n131_w15_pair_bucket_polynomial_20261010/polynomial_sparse_v3.json"


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


protocol=json.loads((HERE/"protocol_n131_v3.json").read_text())
assert protocol["status"]=="FROZEN_BEFORE_N131_W15_QUOTIENT_JOIN_V3"
assert protocol["source_sha256"]=={
    "n131_quotient_v3.py":digest(Path(__file__)),
    "run_n131_v3.py":digest(HERE/"run_n131_v3.py"),
    "restricted_result.json":digest(RESTRICTED),
    "polynomial_sparse_v3.json":digest(SPARSE),
    "sage_runtime_info.json":digest(HERE/"sage_runtime_info.json")}
assert not (HERE/"n131_result_v3.json").exists()

started=time.perf_counter_ns()
base=PolynomialRing(GF(2),"t")
t=base.gen()
F=GF(2**131,"t",modulus=t**131+t**13+t**2+t+1)
E=EllipticCurve(F,[1,0,0,0,1])


def decode(bits):return F(base([(int(bits)>>i)&1 for i in range(131)]))


def encode(value):return sum(int(bit)<<i for i,bit in enumerate(value.polynomial().list()))


def w(mask):return sum((F.gen()**(i+1) for i in range(15) if mask>>i&1),F.zero())


def basis(values):
    pivots={}
    out=[]
    for value in values:
        bits=encode(value)
        while bits:
            top=bits.bit_length()-1
            if top in pivots:bits^=pivots[top]
            else:pivots[top]=bits;out.append(value);break
    return out


control=json.loads(RESTRICTED.read_text())
saved=json.loads(SPARSE.read_text())
assert control["status"]=="PASS_N131_OFFSET_THREE_CONSTRUCTED_JOINT_BLOCK_CONTROL"
assert control["seed_a"]==saved["seed"]==13686
assert control["masks"][4]^control["masks"][5]==13686
assert control["masks"][6]^control["masks"][7]==13686
points=[E(decode(x),decode(y)) for x,y in control["raw_leaves"][4:8]]
left_pair=points[0]+points[1]
right_pair=points[2]+points[3]
assert left_pair!=E(0) and right_pair!=E(0)
ca,cb=1/left_pair[0],1/right_pair[0]
residual=decode(control["known_block_output_z"][0])
assert (1+ca*ca*cb*cb)*residual*residual+ca*cb*residual+(ca+cb)**2==0
negative=F.gen()+1
assert (1+ca*ca*cb*cb)*negative*negative+ca*cb*negative+(ca+cb)**2!=0
print({"phase":"inputs_verified","elapsed_s":(time.perf_counter_ns()-started)/1e9},flush=True)

D=PolynomialRing(F,"d")
d=D.gen()
right=D({int(exponent):decode(coefficient)**(2**39)
         for exponent,coefficient in saved["terms"]})
assert right.degree()==32768 and right(cb)==0
p_basis=basis([w(1<<i)**2+w(13686)*w(1<<i) for i in range(15)])
assert len(p_basis)==14
print({"phase":"right_bucket_ready","degree":int(right.degree()),
       "terms":len(right.dict()),"elapsed_s":(time.perf_counter_ns()-started)/1e9},flush=True)


def join(rr,label):
    stage=time.perf_counter_ns()
    aa=D.one()+D(rr*rr)*d*d
    bb=D(rr)*d
    cc0=D(rr*rr)+d*d
    print({"phase":label,"step":"linear_inverse_start",
           "elapsed_s":(time.perf_counter_ns()-stage)/1e9},flush=True)
    root=1/rr
    coefficients=right.list()
    n=len(coefficients)-1
    q=[F.zero() for _ in range(n)]
    q[-1]=coefficients[-1]
    for i in range(n-2,-1,-1):q[i]=coefficients[i+1]+root*q[i+1]
    remainder=coefficients[0]+root*q[0]
    assert remainder!=0
    quotient=D(q)
    print({"phase":label,"step":"synthetic_quotient_done",
           "elapsed_s":(time.perf_counter_ns()-stage)/1e9},flush=True)
    inv_linear=quotient/(rr*remainder)
    inv=(inv_linear*inv_linear)%right
    print({"phase":label,"step":"inverse_square_done",
           "elapsed_s":(time.perf_counter_ns()-stage)/1e9},flush=True)
    assert (aa*inv)%right==1
    bz=(bb*inv)%right
    cz=(cc0*inv)%right
    print({"phase":label,"step":"linear_inverse_done",
           "elapsed_s":(time.perf_counter_ns()-stage)/1e9},flush=True)
    zero=(D.zero(),D.zero())
    one=(D.zero(),D.one())

    def add(a,b):return a[0]+b[0],a[1]+b[1]

    def mul(a,b):
        uu=(a[0]*b[0])%right
        return ((a[0]*b[1]+a[1]*b[0]+uu*bz)%right,
                (a[1]*b[1]+uu*cz)%right)

    def square(a):
        uu=(a[0]*a[0])%right
        return ((uu*bz)%right,(a[1]*a[1]+uu*cz)%right)

    coeff=[one]
    for i,p in enumerate(p_basis):
        p=p**(2**26)
        v=(D(p*p)*bz+D(p),D(p*p)*cz)
        power=v
        value=zero
        for a in coeff:
            value=add(value,mul(a,power))
            power=square(power)
        nxt=[zero for _ in range(len(coeff)+1)]
        for j,a in enumerate(coeff):
            nxt[j]=add(nxt[j],mul(a,value))
            nxt[j+1]=add(nxt[j+1],square(a))
        coeff=nxt
        if i in (2,5,8,11,13):
            print({"phase":label,"round":i+1,"elapsed_s":(time.perf_counter_ns()-stage)/1e9},flush=True)
    ss=w(13686)**(2**26)
    y=(bz,cz+D(ss*ss))
    value=zero
    for a in coeff:
        value=add(value,mul(a,y))
        y=square(y)
    u,v=value
    norm=(v*v+bz*u*v+cz*u*u)%right
    intersection=norm.gcd(right)
    return {"intersection_degree":int(intersection.degree()),
            "known_right_root_in_intersection":bool(intersection(cb)==0),
            "norm_degree":int(norm.degree()),
            "elapsed_ns":time.perf_counter_ns()-stage}


positive=join(residual,"positive")
assert positive["known_right_root_in_intersection"]
print({"phase":"positive_complete","degree":positive["intersection_degree"],
       "elapsed_s":(time.perf_counter_ns()-started)/1e9},flush=True)
negative_row=join(negative,"negative")
result={"status":"PASS_N131_W15_QUOTIENT_PAIR_BUCKET_CONTROLS_V3",
        "field_degree":131,"seed":13686,"bucket_degree":int(right.degree()),
        "product_basis_dimension":len(p_basis),"left_rotation":26,"right_rotation":39,
        "left_pair_output":encode(ca),"right_pair_output":encode(cb),
        "positive_residual":encode(residual),"negative_residual":encode(negative),
        "positive":positive,"negative":negative_row,
        "elapsed_ns":time.perf_counter_ns()-started,
        "source_sha256":protocol["source_sha256"],
        "protocol_sha256":digest(HERE/"protocol_n131_v3.json"),"candidate_id":None}
with (HERE/"n131_result_v3.json").open("x") as stream:
    json.dump(result,stream,sort_keys=True,indent=2)
    stream.write("\n")
print({"status":result["status"],"positive":positive,"negative":negative_row,
       "elapsed_s":result["elapsed_ns"]/1e9},flush=True)
