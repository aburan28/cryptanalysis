#!/usr/bin/env python3
"""Freeze exact public target fiber and ten W5 source blocks for native join."""
import hashlib
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
GATE=ROOT/"n41_w5_ten_source_gate_20261010"
OLD=ROOT/"n41_n131_seven_diagonal_20261009"
sys.path.insert(0,str(OLD))
import run as old

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
    with Path(path).open("x") as f:
        json.dump(value,f,indent=2,sort_keys=True);f.write("\n")

def main():
    protocol=json.loads((HERE/"protocol.json").read_text())
    prior=json.loads((GATE/"protocol_v2.json").read_text())
    public=json.loads((GATE/"public/result.json").read_text())
    geometry=json.loads((GATE/"geometry_result.json").read_text())
    assert protocol["status"]=="FROZEN_BEFORE_EXPORT_AND_JOIN"
    assert protocol["source_sha256"]=={
        "export":sha(Path(__file__)),"geometry":sha(GATE/"geometry_result.json"),
        "public":sha(GATE/"public/result.json"),
        "prior_protocol":sha(GATE/"protocol_v2.json"),
        "old_run":sha(OLD/"run.py"),"base":sha(old.base.__file__)}
    assert geometry["curve_id"]==prior["curve_id"]==public["curve_id"]
    assert geometry["public_target_q"]==prior["public_target_q"]==public["public_target_q"]
    assert public["status"]=="CENSORED_TIME"
    assert geometry["actual_subgroup_factor_base_points_B"]==340
    assert geometry["folded_columns_K"]==14
    field=old.base.Field(41,[0,3]);curve=old.base.Curve(field,0)
    q=tuple(geometry["public_target_q"])
    qprime=tuple(public["transported_target_qprime"])
    assert curve.on_curve(q) and curve.mul(549756390943,q) is None
    assert curve.add(qprime,old.point_frob(field,qprime,1))==q
    targets=old.base.target_preimages(field,curve,qprime)
    assert len(targets)==4 and all(curve.mul(4,p)==qprime for p in targets)
    columns={int(k):tuple(v) for k,v in geometry["mask_columns"].items()}
    column_ids={key:i for i,key in enumerate(sorted(set(columns.values())))}
    raw={int(k):[tuple(p) for p in row]
         for k,row in geometry["raw_points"].items()}
    blocks=[]
    for rotation in geometry["rotations"]:
        block=[]
        for mask in sorted(raw):
            for sign,p in enumerate(raw[mask]):
                rotated=old.point_frob(field,p,rotation)
                assert curve.on_curve(rotated)
                assert old.base.signed_frob_key(field,curve,rotated)==columns[mask]
                block.append((rotated[0],rotated[1],column_ids[columns[mask]],mask,sign))
        assert len(block)==34
        blocks.append(block)
    input_path=HERE/"input.txt"
    with input_path.open("x") as f:
        f.write(f"{q[0]} {q[1]} {qprime[0]} {qprime[1]} 549756390943 10\n")
        for p in targets:f.write(f"{p[0]} {p[1]}\n")
        for block in blocks:
            f.write(f"{len(block)}\n")
            for row in block:f.write(" ".join(map(str,row))+"\n")
    receipt={"status":"PASS_EXACT_NATIVE_INPUT_EXPORT",
             "curve_id":geometry["curve_id"],"public_q":list(q),
             "transported_qprime":list(qprime),
             "target_raw_preimages":[list(p) for p in targets],
             "blocks":10,"states_per_block":34,"folded_columns_K":14,
             "actual_factor_base_points_B":340,
             "input_bytes":input_path.stat().st_size,
             "input_sha256":sha(input_path),
             "source_sha256":{"protocol":sha(HERE/"protocol.json"),
                              "script":sha(Path(__file__)),
                              "geometry":sha(GATE/"geometry_result.json"),
                              "public":sha(GATE/"public/result.json")}}
    save(HERE/"export_receipt.json",receipt)
    print(json.dumps({"status":receipt["status"],"input_sha256":receipt["input_sha256"]}))

if __name__=="__main__":main()
