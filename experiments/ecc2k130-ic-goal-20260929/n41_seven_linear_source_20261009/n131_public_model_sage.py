#!/usr/bin/env sage -python
"""Independently replay a public N131 SAT model as a seven-point relation."""
import hashlib
import itertools
import json
import sys
from pathlib import Path
from sage.all import EllipticCurve, GF, PolynomialRing

here=Path(__file__).resolve().parent
root=here.parent
sys.path.insert(0,str(root))
import run_n41_disjoint_s5_sat as base
folder=here/"n131_public"
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
protocol=json.loads((here/"n131_public_protocol.json").read_text())
result=json.loads((folder/"result.json").read_text())
prep=json.loads((here/"n131_preparation.json").read_text())
if result["status"]!="SAT_MODEL_PENDING_INDEPENDENT_SAGE":
    raise ValueError("public solver has no SAT model to replay")
output=(folder/"solver.stdout.txt").read_text()
model=base.read_model(output,result["formula"]["variables"])
assert result["formula"]["compressed_sha256"]==sha(folder/"system.xcnf.gz")
masks=[sum(int(model[1+i*19+bit])<<bit for bit in range(19)) for i in range(7)]
flags=[i for i in range(4) if model[134+i]]
assert len(flags)==1
middle_values=[sum(int(model[138+i*131+bit])<<bit for bit in range(131))
               for i in range(5)]
support={}
for line in (here/"support_w19.tsv").open():
    mask,canonical=map(int,line.split())
    support[mask]=canonical
assert all(mask in support for mask in masks)
columns=[support[mask] for mask in masks]
assert len(set(columns))==7

ring=PolynomialRing(GF(2),"t")
t=ring.gen()
field=GF(2**131,name="t",modulus=t**131+t**13+t**2+t+1)
curve=EllipticCurve(field,[1,0,0,0,1])
zero=curve(0)
R=int(protocol["subgroup_order_r"])
def decode(value):
    return field(ring([(int(value)>>i)&1 for i in range(131)]))
def encode(value):
    return sum(int(bit)<<i for i,bit in enumerate(value.polynomial().list()))
def point(values):
    return curve(decode(values[0]),decode(values[1]))
def key(p):
    return [encode(p[0]),encode(p[1])]
def phi(p):
    if p==zero or p[0]==1:
        return None
    value=1/(p[0]+1)
    return None if value in (0,1) else value
def frob(p):
    return curve(p[0]**2,p[1]**2)

q=point(protocol["public_target_q"])
lam=int(prep["frobenius_eigenvalue_mod_r"])
qprime=pow(1+lam,-1,R)*q
assert q!=zero and R*q==R*qprime==zero
assert key(qprime)==result["transported_target_qprime"]
assert qprime+frob(qprime)==q
torsion=curve(field.one(),field.zero())
raw_targets=[pow(4,-1,R)*qprime+k*torsion for k in range(4)]
choices=[]
for i,mask in enumerate(masks):
    u=field.zero()
    for bit,basis_value in enumerate(prep["bases_u"][i]):
        if mask>>bit&1:
            u+=decode(basis_value)
    assert u not in (0,1)
    points=sorted(curve.lift_x(1+1/u,all=True),key=lambda p:encode(p[1]))
    assert len(points)==2 and all(phi(p)==u for p in points)
    choices.append(points)
found=[]
for signs in itertools.product((0,1),repeat=7):
    leaves=[choices[i][sign] for i,sign in enumerate(signs)]
    middle=[leaves[0]+leaves[1],leaves[2]+leaves[3],leaves[4]+leaves[5]]
    middle += [middle[0]+middle[1]]
    middle += [middle[3]+middle[2]]
    total=middle[4]+leaves[6]
    if total!=raw_targets[flags[0]]:
        continue
    if any(phi(p) is None for p in middle):
        continue
    if [encode(phi(p)) for p in middle]!=middle_values:
        continue
    assert 4*total==qprime
    assert sum((4*(p+frob(p)) for p in leaves),zero)==q
    found.append({"masks":masks,"signs":list(signs),
                  "folded_columns":columns,
                  "target_preimage_index":flags[0],
                  "raw_leaves":[key(p) for p in leaves],
                  "raw_sum":key(total),"target_qprime":key(qprime),
                  "public_target_q":key(q)})
if not found:
    raise ValueError("saved SAT model lacks a valid raw group lift")
replay={"status":"PASS_INDEPENDENT_PUBLIC_GROUP_REPLAY",
        "relation_count":len(found),"relations":found,
        "source_sha256":{"protocol":sha(here/"n131_public_protocol.json"),
                         "result":sha(folder/"result.json"),
                         "stdout":sha(folder/"solver.stdout.txt"),
                         "support":sha(here/"support_w19.tsv"),
                         "script":sha(Path(__file__))}}
with (folder/"sage_replay.json").open("x") as out:
    json.dump(replay,out,indent=2,sort_keys=True)
    out.write("\n")
print(json.dumps({"status":replay["status"],"relations":len(found)}))
