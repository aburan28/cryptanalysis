#!/usr/bin/env sage -python
"""Independently map W6 atoms to 26 orbit columns and freeze setup queries."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent / "n41_upper_xor_projection_20261010"
PUBLIC=HERE.parent / "n41_adjacent_pairpair/public_target.json"
R=549756390943
LAMBDA=256851699273
SEED="n41-coupled-sixpair-factorlogs-20261010-v1"
TARGETS=128


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    runtime=json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"]=="verified"
    prior=json.loads((SOURCE / "w6_protocol.json").read_text())
    official=json.loads(PUBLIC.read_text())
    assert prior["status"]=="FROZEN_BEFORE_N41_W6_PUBLIC_QUERY"
    assert prior["source_sha256"]["input"]==sha(SOURCE / "w6_input.txt")
    assert official["subgroup_order"]==R
    ring=PolynomialRing(GF(2),"t")
    t=ring.gen()
    field=GF(2**41,name="t",modulus=t**41+t**3+1)
    curve=EllipticCurve(field,[1,0,0,0,1])
    zero=curve(0)

    def decode(value):
        return field(ring([(int(value)>>i)&1 for i in range(41)]))

    def encode(value):
        return sum(int(bit)<<i for i,bit in enumerate(value.polynomial().list()))

    def point(pair):
        return curve(decode(pair[0]),decode(pair[1]))

    def key(p):
        return (encode(p[0]),encode(p[1]))

    def frobenius(p):
        return curve(p[0]**2,p[1]**2)

    generator=point(official["generator"])
    qpublic=point(official["target_q"])
    assert R*generator==zero and R*qpublic==zero
    assert LAMBDA*generator==frobenius(generator)
    assert pow(LAMBDA,41,R)==1
    lines=(SOURCE / "w6_input.txt").read_text().splitlines()
    head=tuple(map(int,lines[0].split()))
    assert head==(*official["target_q"],R,6)
    cursor=1
    atoms=[]
    for block in range(6):
        rotation,count=map(int,lines[cursor].split())
        cursor+=1
        assert rotation==prior["paired_rotations"][block] and count==64
        for index in range(count):
            x,y,mask,sign,column=map(int,lines[cursor].split())
            cursor+=1
            p=point((x,y))
            assert R*p==zero and 0<=column<26
            atoms.append({"block":block,"index":index,"mask":mask,
                          "sign":sign,"column":column,"point":[x,y]})
    assert cursor==len(lines) and len(atoms)==384
    reps={}
    for item in atoms:
        reps.setdefault(item["column"],point(item["point"]))
    assert set(reps)==set(range(26))
    orbit={}
    for column,representative in reps.items():
        current=representative
        coefficient=1
        for shift in range(41):
            for candidate,factor in ((current,coefficient),(-current,-coefficient)):
                k=key(candidate)
                value=(column,factor%R)
                if k in orbit and orbit[k]!=value:
                    raise AssertionError("inconsistent signed-Frobenius orbit map")
                orbit[k]=value
            current=frobenius(current)
            coefficient=(coefficient*LAMBDA)%R
    for item in atoms:
        column,coefficient=orbit[key(point(item["point"]))]
        assert column==item["column"]
        item["coefficient_mod_r"]=coefficient
    setup=[]
    seen=set()
    for index in range(TARGETS):
        scalar=int.from_bytes(hashlib.sha256(f"{SEED}:{index}".encode()).digest(),"big")%R
        if scalar==0 or scalar in seen:
            raise AssertionError("fixture scalar collision")
        seen.add(scalar)
        q=scalar*generator
        assert q!=zero and q!=qpublic and R*q==zero
        setup.append({"index":index,"scalar":scalar,"point":list(key(q))})
    receipt={"status":"FROZEN_N41_W6_ORBIT_COLUMNS_AND_SETUP_TARGETS",
             "curve_id":official["curve_id"],"subgroup_order":R,
             "generator":list(key(generator)),"public_target_q":list(key(qpublic)),
             "frobenius_eigenvalue_mod_r":LAMBDA,
             "actual_factor_base_points_B":384,"folded_columns_K":26,
             "rotations":prior["paired_rotations"],"atoms":atoms,
             "representatives":[list(key(reps[i])) for i in range(26)],
             "setup_scalar_seed":SEED,"setup_targets":setup,
             "source_sha256":{"script":sha(__file__),
                              "runtime":sha(HERE / "sage_runtime_info.json"),
                              "prior_protocol":sha(SOURCE / "w6_protocol.json"),
                              "atom_input":sha(SOURCE / "w6_input.txt"),
                              "public_point":sha(PUBLIC)}}
    with (HERE / "workload.json").open("x") as out:
        json.dump(receipt,out,indent=2,sort_keys=True)
        out.write("\n")
    print(json.dumps({"status":receipt["status"],"atoms":len(atoms),
                      "columns":len(reps),"setup_targets":len(setup)}))


if __name__=="__main__":
    main()
