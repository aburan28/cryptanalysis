#!/usr/bin/env python3
"""Lift reciprocal S3 assignments to exact twelve-atom group relations."""

import argparse
import itertools
import json
from pathlib import Path

import importlib.util

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("n131_coupled_sixpair_lift_run",HERE / "run.py")
run=importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


def frobenius(field,point,steps):
    x,y=point
    for _ in range(steps):
        x,y=field.mul(x,x),field.mul(y,y)
    return x,y


def reciprocal(field,point):
    return None if point is None or point[0]==0 else field.inv(point[0])


def lift(masks,middle_reciprocals,q,target_index):
    columns,field,curve,_,_=run.source()
    if len(masks)!=12 or len(middle_reciprocals)!=10:
        raise ValueError("twelve masks and ten intermediate reciprocals required")
    if any(mask not in columns for mask in masks):
        raise ValueError("mask outside audited W14 support")
    folded=[columns[mask] for mask in masks]
    if len(set(folded))!=12:
        raise ValueError("folded-column collision")
    if masks[4]^masks[5]!=masks[6]^masks[7] or masks[8]^masks[9]!=masks[10]^masks[11]:
        raise ValueError("seed-sum equality failed")
    diagonal=run.prior.inverse_module.DiagonalPairInverse(columns)
    signed=[]
    for i,mask in enumerate(masks):
        plus=frobenius(field,diagonal.atom(mask),run.prior.ROTATIONS[i])
        signed.append((plus,curve.neg(plus)))
    pair_options=[]
    for i in range(6):
        options=[]
        for bits in itertools.product((0,1),repeat=2):
            leaves=(signed[2*i][bits[0]],signed[2*i+1][bits[1]])
            total=curve.add(*leaves)
            if reciprocal(field,total)==middle_reciprocals[i]:
                options.append((bits,leaves,total))
        pair_options.append(options)
    raw_targets=run.prior.prior.old.target_preimages(curve,q)
    if target_index not in range(4):
        raise ValueError("invalid target-fiber index")
    solutions=[]
    for choices in itertools.product(*pair_options):
        pair_sums=[item[2] for item in choices]
        upper=[curve.add(pair_sums[0],pair_sums[1]),
               curve.add(pair_sums[2],pair_sums[3]),
               curve.add(pair_sums[4],pair_sums[5])]
        upper.append(curve.add(upper[0],upper[1]))
        if [reciprocal(field,p) for p in upper]!=middle_reciprocals[6:]:
            continue
        total=curve.add(upper[3],upper[2])
        if total!=raw_targets[target_index] or curve.mul(4,total)!=q:
            continue
        leaves=[leaf for choice in choices for leaf in choice[1]]
        signs=[sign for choice in choices for sign in choice[0]]
        solutions.append({"masks":masks,"signs":signs,
                          "folded_columns":folded,
                          "raw_leaves":[list(p) for p in leaves],
                          "raw_sum":list(total),"projected_sum":list(q),
                          "target_preimage_index":target_index})
    return {"status":"GROUP_LIFT_FOUND" if solutions else "NO_GROUP_LIFT",
            "pair_option_counts":[len(options) for options in pair_options],
            "solutions":solutions}


def control():
    fixture=json.loads((HERE / "control.json").read_text())
    answer=lift(fixture["masks"],fixture["middle_reciprocals"],
                tuple(fixture["target_q"]),fixture["target_preimage_index"])
    assert answer["status"]=="GROUP_LIFT_FOUND"
    assert any(item["raw_leaves"]==fixture["raw_leaves"]
               for item in answer["solutions"])
    answer["source_sha256"]={"script":run.sha(__file__),
                             "control":run.sha(HERE / "control.json"),
                             "sage_audit":run.sha(HERE / "sage_audit.json")}
    run.save(HERE / "lift_control.json",answer)
    print(json.dumps({"status":answer["status"],
                      "solutions":len(answer["solutions"]),
                      "pair_option_counts":answer["pair_option_counts"]}))


def public():
    result=json.loads((HERE / "public_query/result.json").read_text())
    if result["status"]!="SAT_MODEL_PENDING_INDEPENDENT_GROUP_REPLAY":
        raise ValueError("published query has no SAT model to lift")
    q=tuple(result["target_q"])
    circuit,meta,_=run.formula_for(q)
    output=(HERE / "public_query/solver.stdout.txt").read_text()
    model=run.base.read_model(output,circuit.next_var-1)
    masks=[sum(1<<i for i,wire in enumerate(row) if model[wire])
           for row in meta["masks"]]
    middle=[sum(1<<i for i,wire in enumerate(row) if model[wire])
            for row in meta["middle"]]
    chosen=[i for i,wire in enumerate(meta["flags"]) if model[wire]]
    assert len(chosen)==1
    answer=lift(masks,middle,q,chosen[0])
    answer["source_sha256"]={"script":run.sha(__file__),
                             "query_result":run.sha(HERE / "public_query/result.json"),
                             "solver_stdout":run.sha(HERE / "public_query/solver.stdout.txt"),
                             "formula":result["formula"]["sha256"]}
    run.save(HERE / "public_query/group_lift.json",answer)
    print(json.dumps({"status":answer["status"],
                      "solutions":len(answer["solutions"]),
                      "pair_option_counts":answer["pair_option_counts"]}))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=("control","public"))
    {"control":control,"public":public}[parser.parse_args().mode]()
