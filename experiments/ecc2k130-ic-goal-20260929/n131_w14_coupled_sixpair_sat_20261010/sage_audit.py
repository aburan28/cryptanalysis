#!/usr/bin/env sage -python
"""Independent Sage replay of the N131 coupled six-pair control."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE=Path(__file__).resolve().parent
SUPPORT=HERE.parent / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
R=680564733841876926932320129493409985129


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    control=json.loads((HERE / "control.json").read_text())
    runtime=json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"]=="verified"
    assert control["status"]=="CONSTRUCTED_COUPLED_SIXPAIR_CONTROL"
    f2=GF(2)
    ring=PolynomialRing(f2,"t")
    t=ring.gen()
    field=GF(2**131,name="t",modulus=t**131+t**13+t**2+t+1)
    curve=EllipticCurve(field,[1,0,0,0,1])

    def element(value):
        result,power=field.zero(),field.one()
        while value:
            if value&1:
                result+=power
            value>>=1
            power*=field.gen()
        return result

    def encoded(value):
        return sum(int(bit)<<i for i,bit in enumerate(value.polynomial().list()))

    def point(pair):
        return curve(element(pair[0]),element(pair[1]))

    def s3(a,b,c):
        product=a*b*c
        return (a+b+c)**2+product+product**2==0

    columns=dict(tuple(map(int,row.split())) for row in SUPPORT.read_text().splitlines())
    assert len(columns)==8220
    assert len({columns[mask] for mask in control["masks"]})==12
    masks=control["masks"]
    assert len(masks)==12 and len(control["rotations"])==12
    for left,right in ((2,3),(4,5)):
        a,b=masks[2*left:2*left+2]
        c,d=masks[2*right:2*right+2]
        assert a^b==c^d
    leaves=[point(pair) for pair in control["raw_leaves"]]
    for mask,rotation,leaf in zip(masks,control["rotations"],leaves):
        w=sum((field.gen()**(i+1) for i in range(14) if mask>>i&1),field.zero())
        assert leaf!=curve(0) and leaf[0]!=0
        assert 1/leaf[0]==w**(2**rotation)
        assert R*(4*leaf)==curve(0)
    middle=[leaves[2*i]+leaves[2*i+1] for i in range(6)]
    middle.extend((middle[0]+middle[1],middle[2]+middle[3],middle[4]+middle[5]))
    middle.append(middle[6]+middle[7])
    total=middle[9]+middle[8]
    assert all(p!=curve(0) and p[0]!=0 for p in [*middle,total])
    assert [encoded(1/p[0]) for p in middle]==control["middle_reciprocals"]
    assert [encoded(total[0]),encoded(total[1])]==control["raw_sum"]
    assert [encoded((4*total)[0]),encoded((4*total)[1])]==control["target_q"]
    assert R*(4*total)==curve(0)
    for i in range(6):
        assert s3(1/leaves[2*i][0],1/leaves[2*i+1][0],1/middle[i][0])
    for a,b,c in ((0,1,6),(2,3,7),(4,5,8),(6,7,9),(9,8,None)):
        assert s3(1/middle[a][0],1/middle[b][0],
                  1/(total if c is None else middle[c])[0])
    receipt={"status":"PASS_INDEPENDENT_SAGE_N131_COUPLED_SIXPAIR_GROUP_REPLAY",
             "curve_id":control["curve_id"],"target_q":control["target_q"],
             "masks":masks,"folded_columns":control["folded_columns"],
             "shared_seed_sums":[masks[4]^masks[5],masks[8]^masks[9]],
             "checked_leaf_links":6,"checked_upper_links":5,
             "sha256":{"control":sha(HERE / "control.json"),
                       "runtime":sha(HERE / "sage_runtime_info.json"),
                       "script":sha(__file__)}}
    with (HERE / "sage_audit.json").open("x") as out:
        json.dump(receipt,out,indent=2,sort_keys=True)
        out.write("\n")
    print(json.dumps({"status":receipt["status"],
                      "shared_seed_sums":receipt["shared_seed_sums"]}))


if __name__=="__main__":
    main()
