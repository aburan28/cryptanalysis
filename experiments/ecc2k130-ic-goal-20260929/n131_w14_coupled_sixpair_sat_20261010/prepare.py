#!/usr/bin/env python3
"""Construct a twelve-atom W14 control with two shared seed sums."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPARSE = ROOT / "n131_w14_diagonal_sparse_sat_20261010"
PAIR = ROOT / "n131_w14_diagonal_pair_inverse_20261010"
ROTATIONS = [0,0,13,13,26,26,39,39,52,52,65,65]
R = 680564733841876926932320129493409985129


def load(name,path):
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prior = load("n131_sparse_prepare_for_sixpair",SPARSE / "prepare.py")
inverse_module = load("n131_diagonal_pair_inverse_for_sixpair",PAIR / "pair_inverse.py")


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def save(path,value):
    with Path(path).open("x") as stream:
        json.dump(value,stream,indent=2,sort_keys=True)
        stream.write("\n")


def frobenius(field,point,steps):
    x,y=point
    for _ in range(steps):
        x,y=field.mul(x,x),field.mul(y,y)
    return x,y


def chain(curve,leaves):
    middle=[curve.add(leaves[2*i],leaves[2*i+1]) for i in range(6)]
    middle.extend((curve.add(middle[0],middle[1]),
                   curve.add(middle[2],middle[3]),
                   curve.add(middle[4],middle[5])))
    middle.append(curve.add(middle[6],middle[7]))
    return middle,curve.add(middle[9],middle[8])


def construct():
    _,_,columns,field,curve,basis_w,panel=prior.source()
    inverse=inverse_module.DiagonalPairInverse(columns)
    positive=[(i,case) for i,case in enumerate(panel["cases"])
              if case["kind"]=="positive"]
    pairs=[]
    seen=set()

    def add_pair(a,b,right_negative,source_index):
        if a not in columns or b not in columns or a==b:
            return False
        new={columns[a],columns[b]}
        if len(new)!=2 or new&seen:
            return False
        pairs.append({"a":a,"b":b,"right_negative":int(right_negative),
                      "source_index":source_index,"seed_sum":a^b})
        seen.update(new)
        return True

    for index,case in positive:
        if add_pair(case["a"],case["b"],case["right_negative"],index):
            if len(pairs)==2:
                break
    if len(pairs)!=2:
        raise RuntimeError("two disjoint free pairs unavailable")
    for block in range(2):
        found=False
        for index,case in positive:
            a,b=case["a"],case["b"]
            if (a not in columns or b not in columns or
                    columns[a] in seen or columns[b] in seen or
                    columns[a]==columns[b]):
                continue
            seed=a^b
            for c in columns:
                d=c^seed
                if c>=d or d not in columns:
                    continue
                candidate={columns[a],columns[b],columns[c],columns[d]}
                if len(candidate)!=4 or candidate&seen:
                    continue
                assert add_pair(a,b,case["right_negative"],index)
                assert add_pair(c,d,False,None)
                found=True
                break
            if found:
                break
        if not found:
            raise RuntimeError(f"same-seed block {block} unavailable")
    if len(pairs)!=6 or len(seen)!=12:
        raise AssertionError("six distinct pairs were not constructed")
    masks=[mask for pair in pairs for mask in (pair["a"],pair["b"])]
    raw=[]
    for pair in pairs:
        left,right=inverse.atom(pair["a"]),inverse.atom(pair["b"])
        raw.extend((left,curve.neg(right) if pair["right_negative"] else right))
    leaves=[frobenius(field,point,ROTATIONS[i]) for i,point in enumerate(raw)]
    middle,total=chain(curve,leaves)
    if any(point is None or point[0]==0 for point in [*leaves,*middle,total]):
        raise ValueError("control has an exceptional reciprocal join")
    q=curve.mul(4,total)
    if q is None or curve.mul(R,q) is not None:
        raise AssertionError("control projection is outside subgroup")
    lifts=prior.old.target_preimages(curve,q)
    if total not in lifts:
        raise AssertionError("raw control sum absent from target fiber")
    for i,(mask,point) in enumerate(zip(masks,leaves)):
        w=prior.old.coordinate(basis_w,mask)
        if field.inv(point[0])!=prior.old.method.frob(field,w,ROTATIONS[i]):
            raise AssertionError("diagonal reciprocal leaf changed")
    if pairs[2]["seed_sum"]!=pairs[3]["seed_sum"] or pairs[4]["seed_sum"]!=pairs[5]["seed_sum"]:
        raise AssertionError("coupled seed sums changed")
    return {"status":"CONSTRUCTED_COUPLED_SIXPAIR_CONTROL",
            "curve_id":"EC1N131Ckb1heb5f1998f20b",
            "rotations":ROTATIONS,"pairs":pairs,"masks":masks,
            "folded_columns":[columns[mask] for mask in masks],
            "raw_leaves":[list(p) for p in leaves],
            "middle_reciprocals":[field.inv(p[0]) for p in middle],
            "raw_sum":list(total),"target_q":list(q),
            "target_preimage_index":lifts.index(total)}


def main():
    control=construct()
    save(HERE / "control.json",control)
    print(json.dumps({"status":control["status"],
                      "seed_sums":[p["seed_sum"] for p in control["pairs"]],
                      "target_q":control["target_q"]}))


if __name__=="__main__":
    main()
