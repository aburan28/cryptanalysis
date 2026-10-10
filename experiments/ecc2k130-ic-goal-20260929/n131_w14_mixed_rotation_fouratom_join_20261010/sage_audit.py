#!/usr/bin/env python3
"""Independent curve and resultant replay of mixed-rotation native hits."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

here=Path(__file__).resolve().parent
old=here.parent/"n131_w14_coupled_fouratom_inverse_20261010"/"inputs.json"
source=json.loads(old.read_text())["panels"]
inputs=json.loads((here/"inputs.json").read_text())["panels"]
protocol=json.loads((here/"protocol.json").read_text())
result=json.loads((here/"result.json").read_text())
assert result["protocol_sha256"]==hashlib.sha256((here/"protocol.json").read_bytes()).hexdigest()
assert len(result["rows"])==4
checks={}
for n in (41,131):
    base=PolynomialRing(GF(2),"t");t=base.gen()
    exponents=source[str(n)]["field_modulus_exponents"]
    F=GF(2**n,name="t",modulus=sum(t**e for e in exponents))
    def decode(v):return F(base([(int(v)>>i)&1 for i in range(n)]))
    def encode(v):return sum(int(bit)<<i for i,bit in enumerate(v.polynomial().list()))
    E=EllipticCurve(F,[1,0,0,0,1])
    panel=inputs[str(n)]
    r1,r2=panel["rotations"]
    raw=[E(decode(x),decode(y)) for x,y in source[str(n)]["raw_diagonal_atoms"]]
    def rotate(point,k):
        x,y=point.xy()
        for _ in range(k):x,y=x*x,y*y
        return E(x,y)
    leaves=[rotate(point,r1 if i<2 else r2) for i,point in enumerate(raw)]
    cpoint=leaves[0]+leaves[1]
    dpoint=leaves[2]+leaves[3]
    total=cpoint+dpoint
    assert [encode(v) for v in total.xy()]==panel["raw_sum"]
    assert [encode(v) for v in (4*total).xy()]==panel["projected_sum"]
    assert int(source[str(n)]["subgroup_order"])*(4*total)==E(0)
    c,d,z=[~point[0] for point in (cpoint,dpoint,total)]
    assert [encode(c),encode(d)]==panel["pair_outputs_reciprocal"]
    assert encode(z)==panel["positive_z"]
    p,q=[decode(v) for v in panel["source_products"]]
    s=decode(panel["seed_sum"])
    pp,qq=p**(2**r1),q**(2**r2)
    ss,tt=s**(2**r1),s**(2**r2)
    assert (1+pp*pp)*c*c+pp*c+ss*ss==0
    assert (1+qq*qq)*d*d+qq*d+tt*tt==0
    assert (1+c*c*d*d)*z*z+c*d*z+(c+d)**2==0
    positive=next(row for row in result["rows"] if row["field_degree"]==n and row["case"]=="positive")
    control=next(row for row in result["rows"] if row["field_degree"]==n and row["case"]=="trace_zero_control")
    for row in (positive,control):
        assert row["status"]=="PROCESS_OK" and row["returncode"]==0
        native=row["native"]
        assert native["status"]=="COMPLETE_ALGEBRAIC_SCAN"
        assert native["rotations"]==[r1,r2]
        assert native["left_outputs_checked"]==native["distinct_pair_outputs"][0]
        assert native["peak_rss_bytes"]<protocol["rss_cap_bytes"]
    expected=(int(panel["source_products"][0]),int(panel["source_products"][1]))
    got={(int(hit["p"][0]),int(hit["q"][0])) for hit in positive["native"]["hits"]}
    assert expected in got
    assert not control["native"]["hits"]
    checks[str(n)]={"constructed_source_product_witness":list(expected),
                    "positive_algebraic_hits":len(got),
                    "control_algebraic_hits":0,
                    "group_sum_replay":True,
                    "projected_subgroup_replay":True}
audit={"status":"PASS_INDEPENDENT_MIXED_ROTATION_REPLAY","checks":checks,
       "source_sha256":{
           "archived_inputs":hashlib.sha256(old.read_bytes()).hexdigest(),
           "inputs":hashlib.sha256((here/"inputs.json").read_bytes()).hexdigest(),
           "protocol":hashlib.sha256((here/"protocol.json").read_bytes()).hexdigest(),
           "result":hashlib.sha256((here/"result.json").read_bytes()).hexdigest(),
           "script":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}
(here/"sage_audit.json").write_text(json.dumps(audit,indent=2,sort_keys=True)+"\n")
print(json.dumps({"status":audit["status"],"checks":checks},sort_keys=True))
