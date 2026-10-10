#!/usr/bin/env python3
"""Exact N41 mixed-rotation all-seed group-domain join for fixed outputs."""

import hashlib
import json
import resource
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

here=Path(__file__).resolve().parent
root=here.parent
w6=root/"n41_upper_xor_projection_20261010/w6_input.txt"
mixed=root/"n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json"
protocol=json.loads((here/"seed_protocol.json").read_text())
sources={"allseed.py":Path(__file__),"w6_input.txt":w6,"mixed_inputs.json":mixed,
         "sage_runtime_info.json":here/"sage_runtime_info.json"}
assert protocol["source_sha256"]=={
    name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in sources.items()}
started=time.monotonic_ns()
ring=PolynomialRing(GF(2),"t");t=ring.gen()
F=GF(2**41,name="t",modulus=t**41+t**3+1)
decode=lambda v:F(ring([(int(v)>>i)&1 for i in range(41)]))
encode=lambda v:sum(int(bit)<<i for i,bit in enumerate(v.polynomial().list()))
E=EllipticCurve(F,[1,0,0,0,1])
points={};columns={}
for line in w6.read_text().splitlines()[2:66]:
    x,y,mask,sign,column=map(int,line.split())
    points.setdefault(mask,{})[sign]=E(decode(x),decode(y))
    if mask in columns:assert columns[mask]==column
    columns[mask]=column
assert len(points)==32 and all(len(v)==2 for v in points.values())
assert len(set(columns.values()))==26


def rotate(point,steps):
    x,y=point.xy()
    for _ in range(steps):x,y=x*x,y*y
    return E(x,y)


rotations=[10,15]
buckets=[{s:{} for s in range(1,64)} for _ in range(2)]
signed_pairs=0
masks=sorted(points)
for i,a in enumerate(masks):
    for b in masks[i+1:]:
        if columns[a]==columns[b]:continue
        seed=a^b
        for sign_a,pa in points[a].items():
            for sign_b,pb in points[b].items():
                pair=pa+pb
                if pair==E(0) or pair[0]==0:continue
                signed_pairs+=1
                for side,r in enumerate(rotations):
                    rotated=rotate(pair,r)
                    c=encode(~rotated[0])
                    buckets[side][seed].setdefault(c,[]).append((a,b,sign_a,sign_b,rotated))
setup_ns=time.monotonic_ns()-started
assert signed_pairs==1956
P=PolynomialRing(F,"D");D=P.gen()
cases={}
panel=json.loads(mixed.read_text())["panels"]["41"]
for case in ("positive","trace_zero_control"):
    z=decode(panel["positive_z" if case=="positive" else "trace_zero_control_z"])
    query_start=time.monotonic_ns()
    algebraic_seeds=[];hits=[]
    for seed in range(1,64):
        if (time.monotonic_ns()-query_start) >= protocol["cap_seconds_per_case"]*10**9:
            raise TimeoutError("all-seed query cap reached")
        found=False
        for c_int,left_states in buckets[0][seed].items():
            c=decode(c_int)
            u=(1+z*z*c*c)*D*D+z*c*D+z*z+c*c
            for d,_ in u.roots():
                right_states=buckets[1][seed].get(encode(d),())
                if not right_states:continue
                found=True
                for la,lb,lsa,lsb,lpoint in left_states:
                    for ra,rb,rsa,rsb,rpoint in right_states:
                        if len({columns[v] for v in (la,lb,ra,rb)})!=4:continue
                        total=lpoint+rpoint
                        if total!=E(0) and total[0]!=0 and ~total[0]==z:
                            hits.append({"seed":seed,"masks":[la,lb,ra,rb],
                                         "signs":[lsa,lsb,rsa,rsb],
                                         "raw_sum":[encode(v) for v in total.xy()]})
        if found:algebraic_seeds.append(seed)
    query_ns=time.monotonic_ns()-query_start
    cases[case]={"status":"COMPLETE_EXACT_SEED_SWEEP",
                 "target_z":encode(z),"tested_seeds":63,
                 "algebraic_hit_seeds":algebraic_seeds,
                 "group_hits":hits,"query_ns":query_ns}
    print(json.dumps({"case":case,"hit_seeds":algebraic_seeds,
                      "group_hits":len(hits),"query_s":query_ns/1e9},sort_keys=True),flush=True)
rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
if rss<0:raise RuntimeError("invalid RSS")
result={"status":"PASS_EXACT_N41_MIXED_ALLSEED_PANEL",
        "source_sha256":protocol["source_sha256"],
        "signed_pair_states_per_rotation":signed_pairs,
        "pair_output_coordinates_per_rotation":[sum(len(v) for v in side.values()) for side in buckets],
        "setup_ns":setup_ns,"cases":cases,"peak_process_rss_bytes":rss,
        "protocol_sha256":hashlib.sha256((here/"seed_protocol.json").read_bytes()).hexdigest()}
assert rss<protocol["rss_cap_bytes"]
(here/"seed_result.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
