#!/usr/bin/env sage -python
"""Independently replay one native ten-source public-point relation in Sage."""
import hashlib
import json
from pathlib import Path
from sage.all import EllipticCurve,GF,PolynomialRing

here=Path(__file__).resolve().parent
gate=here.parent/"n41_w5_ten_source_gate_20261010"
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
protocol=json.loads((here/"protocol.json").read_text())
export=json.loads((here/"export_receipt.json").read_text())
geometry=json.loads((gate/"geometry_result.json").read_text())
terminal=json.loads((here/"run/result.json").read_text())
runtime=json.loads((here/"sage_runtime_info.json").read_text())
assert runtime["status"]=="verified"
assert terminal["status"]=="FOUND_PENDING_SAGE_REPLAY"
assert export["input_sha256"]==sha(here/"input.txt")
hits=(here/"run/hits.jsonl").read_text().splitlines()
assert len(hits)==1
hit=json.loads(hits[0])
assert hit["status"]=="NATIVE_RELATION_PENDING_SAGE"
F2=GF(2)
ring=PolynomialRing(F2,"t")
t=ring.gen()
field=GF(2**41,name="t",modulus=t**41+t**3+1)
curve=EllipticCurve(field,[1,0,0,0,1])
zero=curve(0)
R=int(geometry["subgroup_order_r"])
def decode(v):
    return field(ring([(int(v)>>i)&1 for i in range(41)]))
def encode(v):
    return sum(int(b)<<i for i,b in enumerate(v.polynomial().list()))
def point(v):
    return curve(decode(v[0]),decode(v[1]))
def key(v):
    return [encode(v[0]),encode(v[1])]
def frob(v):
    return curve(v[0]**2,v[1]**2)
def column(v):
    p=4*v
    keys=[]
    for _ in range(41):
        keys.extend((tuple(key(p)),tuple(key(-p))))
        p=frob(p)
    return min(keys)

q=point(protocol["public_q"])
qprime=point(protocol["qprime"])
assert q!=zero and R*q==R*qprime==zero
assert qprime+frob(qprime)==q
raw_targets=[point(v) for v in export["target_raw_preimages"]]
assert len(set(raw_targets))==4 and all(4*v==qprime for v in raw_targets)
source_basis=[field.gen()**i for i in range(1,6)]
half_basis=[decode(v) for v in geometry["source_basis_u"]]
assert all(u**2+u==w for u,w in zip(half_basis,source_basis))
column_keys=sorted({tuple(v) for v in geometry["mask_columns"].values()})
assert len(column_keys)==14
leaves=[]
for block,(mask,sign,index,reported_column) in enumerate(zip(
        hit["masks"],hit["signs"],hit["indices"],hit["columns"])):
    assert 0<=index<34 and 1<=mask<32 and sign in (0,1)
    w=sum((source_basis[i] for i in range(5) if mask>>i&1),field.zero())
    assert int((1/w).trace())==0
    u=sum((half_basis[i] for i in range(5) if mask>>i&1),field.zero())
    assert u**2+u==w and u not in (0,1)
    options=sorted(curve.lift_x(1+1/u,all=True),key=lambda v:tuple(key(v)))
    assert len(options)==2
    selected=options[sign]
    assert key(selected)==geometry["raw_points"][str(mask)][sign]
    for _ in range(geometry["rotations"][block]):
        selected=frob(selected)
    assert tuple(geometry["mask_columns"][str(mask)])==column(selected)
    assert column_keys[reported_column]==column(selected)
    leaves.append(selected)
assert len({column(v) for v in leaves})==10
total=sum(leaves,zero)
assert key(total)==hit["raw_sum"]
assert total==raw_targets[hit["target_preimage_index"]]
assert 4*total==qprime and 4*total+frob(4*total)==q
result={"status":"PASS_INDEPENDENT_SAGE_PUBLIC_GROUP_REPLAY",
        "curve_id":protocol["curve_id"],"public_q":key(q),
        "transported_qprime":key(qprime),
        "raw_sum":key(total),"target_preimage_index":hit["target_preimage_index"],
        "masks":hit["masks"],"signs":hit["signs"],
        "folded_columns":hit["columns"],
        "source_sha256":{"protocol":sha(here/"protocol.json"),
                         "input":sha(here/"input.txt"),
                         "native_result":sha(here/"run/result.json"),
                         "native_hit":sha(here/"run/hits.jsonl"),
                         "geometry":sha(gate/"geometry_result.json"),
                         "runtime":sha(here/"sage_runtime_info.json"),
                         "script":sha(Path(__file__))}}
with (here/"sage_hit_audit.json").open("x") as f:
    json.dump(result,f,indent=2,sort_keys=True);f.write("\n")
print(json.dumps({"status":result["status"],"target_preimage_index":result["target_preimage_index"]}))
