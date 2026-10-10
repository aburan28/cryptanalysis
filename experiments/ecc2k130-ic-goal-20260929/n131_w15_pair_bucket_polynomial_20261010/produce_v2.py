#!/usr/bin/env sage -python
"""Build a whole-seed pair-output polynomial by a linearized norm."""

import hashlib
import json
import time
from pathlib import Path

from sage.all import EllipticCurve,GF,PolynomialRing

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
RESTRICTED=BASE/"n131_w15_joint_block_resultant_20261010/restricted_result.json"
SUPPORT=BASE/"n131_w15_coupled_sixpair_20261010/support_w15.tsv"
FREEZE=HERE/"protocol_v2.json"


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


freeze=json.loads(FREEZE.read_text())
assert freeze["status"]=="FROZEN_BEFORE_W15_PAIR_BUCKET_POLYNOMIAL_V2"
assert freeze["sha256"]=={"produce_v2.py":sha(Path(__file__)),
    "run_v2.py":sha(HERE/"run_v2.py"),
    "restricted_result.json":sha(RESTRICTED),
    "support_w15.tsv":sha(SUPPORT),
    "sage_runtime_info":sha(HERE/"sage_runtime_info.json")}
assert not (HERE/"result_v2.json").exists()


def field(n):
    base=PolynomialRing(GF(2),"t")
    t=base.gen()
    modulus=t**41+t**3+1 if n==41 else t**131+t**13+t**2+t+1
    return base,GF(2**n,"t",modulus=modulus)


def encode(value):
    return sum(int(bit)<<i for i,bit in enumerate(value.polynomial().list()))


def decode(base,F,n,value):
    return F(base([(int(value)>>i)&1 for i in range(n)]))


def w(F,d,mask):
    return sum((F.gen()**(i+1) for i in range(d) if mask>>i&1),F.zero())


def independent_basis(values):
    pivots={}
    basis=[]
    for value in values:
        bits=encode(value)
        while bits:
            top=bits.bit_length()-1
            if top in pivots:bits^=pivots[top]
            else:pivots[top]=bits;basis.append(value);break
    return basis


def construct(F,d,seed):
    s=w(F,d,seed)
    basis=independent_basis([w(F,d,1<<i)**2+s*w(F,d,1<<i) for i in range(d)])
    assert len(basis)==d-1
    ring=PolynomialRing(F,"c")
    c=ring.gen()
    coeff=[ring.one()]
    round_rows=[]
    for vector in basis:
        cp=c*vector
        power=cp
        value=ring.zero()
        for a in coeff:
            value+=a*(power*power+power)
            power=power*power
        next_coeff=[ring.zero() for _ in range(len(coeff)+1)]
        for i,a in enumerate(coeff):
            next_coeff[i]+=a*value
            next_coeff[i+1]+=a*a
        coeff=next_coeff
        round_rows.append({"dimension":len(coeff)-1,
            "coefficient_max_degree":max(int(a.degree()) for a in coeff)})
    h=c*c+s*s
    power=h
    out=ring.zero()
    for a in coeff:
        out+=a*power
        power=power*power
    return out,basis,round_rows


started=time.perf_counter_ns()
base41,F41=field(41)
p41,b41,round41=construct(F41,6,4)
s41=w(F41,6,4)
products41={w(F41,6,m)**2+s41*w(F41,6,m) for m in range(64)}
direct=p41.parent().one()
c41=p41.parent().gen()
for p in products41:
    direct*=c41*c41+(p*c41)**2+p*c41+s41*s41
assert p41==direct and len(products41)==32
n41={"seed":4,"product_basis_dimension":len(b41),
    "degree":int(p41.degree()),"nonzero_coefficients":len(p41.dict()),
    "direct_product_equal":True,"rounds":round41,
    "elapsed_ns":time.perf_counter_ns()-started}
with (HERE/"control_n41_v2.json").open("x") as output:
    json.dump(n41,output,sort_keys=True,indent=2);output.write("\n")
print({"n41_degree":n41["degree"],"n41_terms":n41["nonzero_coefficients"]},flush=True)

started=time.perf_counter_ns()
base131,F131=field(131)
control=json.loads(RESTRICTED.read_text())
assert control["seed_a"]==13686
p131,b131,round131=construct(F131,15,control["seed_a"])
E=EllipticCurve(F131,[1,0,0,0,1])
points=[E(decode(base131,F131,131,x),decode(base131,F131,131,y))
        for x,y in control["raw_leaves"][4:6]]
pair=points[0]+points[1]
assert pair!=E(0) and pair[0]!=0
known=1/pair[0]
known=known**(2**(131-26))
assert p131(known)==0
controls=[F131.gen()+1,F131.gen()**2+F131.gen()+1]
control_values=[int(p131(value)==0) for value in controls]
digest=hashlib.sha256()
for coefficient in p131.list():
    digest.update(encode(coefficient).to_bytes(17,"little"))
n131={"seed":control["seed_a"],"product_basis_dimension":len(b131),
    "degree":int(p131.degree()),"nonzero_coefficients":len(p131.dict()),
    "coefficient_sha256":digest.hexdigest(),
    "known_normalized_pair_output":encode(known),
    "known_output_polynomial_zero":True,
    "field_control_polynomial_zero":control_values,
    "rounds":round131,"elapsed_ns":time.perf_counter_ns()-started}
record={"status":"PASS_N41_N131_PAIR_BUCKET_POLYNOMIAL_CONTROLS",
    "n41":n41,"n131":n131,
    "protocol_sha256":sha(FREEZE),"source_sha256":freeze["sha256"],
    "candidate_id":None}
with (HERE/"result_v2.json").open("x") as output:
    json.dump(record,output,sort_keys=True,indent=2);output.write("\n")
print({"status":record["status"],"n131_degree":n131["degree"],
       "n131_terms":n131["nonzero_coefficients"],
       "n131_elapsed_s":n131["elapsed_ns"]/1e9},flush=True)
