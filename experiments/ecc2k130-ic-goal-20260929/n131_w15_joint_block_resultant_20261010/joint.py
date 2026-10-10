#!/usr/bin/env sage -python
"""Eliminate both block outputs against a public-target raw residual."""

import hashlib
import json
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROTATED = BASE / "n131_w15_rotated_fouratom_inverse_20261010/resultant.json"
SCREEN = BASE / "n41_n131_diagonal_atom_20261010/screen.json"
HIT = BASE / "n131_w15_cross_block_seed_offset_20261010/n41_hit.json"
LIFT = BASE / "n131_w15_coupled_sixpair_20261010/control_group_lift.json"
FREEZE = HERE / "protocol_v2.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


freeze = json.loads(FREEZE.read_text())
assert freeze["status"] == "FROZEN_BEFORE_JOINT_BLOCK_RESULTANT_PANEL"
assert freeze["source_sha256"] == {"joint.py": sha(Path(__file__)),
    "rotated_resultant": sha(ROTATED), "n41_screen": sha(SCREEN),
    "n41_hit": sha(HIT), "n131_lift": sha(LIFT),
    "sage_runtime_info": sha(HERE / "sage_runtime_info.json")}
assert not (HERE / "result.json").exists()
terms = json.loads(ROTATED.read_text())["terms"]


def field_curve(n):
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    modulus = t**41+t**3+1 if n == 41 else t**131+t**13+t**2+t+1
    field = GF(2**n, "t", modulus=modulus)
    return ring,field,EllipticCurve(field,[1,0,0,0,1])


def decode(ring,field,n,value):
    return field(ring([(int(value)>>i)&1 for i in range(n)]))


def encode(value):
    return sum(int(bit)<<i for i,bit in enumerate(value.polynomial().list()))


def source_w(field,d,mask):
    return sum((field.gen()**(i+1) for i in range(d) if mask>>i&1),field.zero())


def block_parameters(field,d,rotations,masks):
    s0,s1=masks[0]^masks[1],masks[2]^masks[3]
    assert s0==s1 and s0!=0
    s=source_w(field,d,s0)
    a,b=(s**(2**r) for r in rotations)
    p=(source_w(field,d,masks[0])*source_w(field,d,masks[1]))**(2**rotations[0])
    q=(source_w(field,d,masks[2])*source_w(field,d,masks[3]))**(2**rotations[1])
    return s0,a,b,p,q


def h_polynomial(poly,a,b,p,q):
    field=poly.base_ring()
    ap,bp,pp,qp=([base**i for i in range(9)] for base in (a,b,p,q))
    coeff=[field.zero() for _ in range(9)]
    for ea,eb,ep,eq,ez in terms:
        coeff[ez]+=ap[ea]*bp[eb]*pp[ep]*qp[eq]
    return poly(coeff)


def joint_eliminant(poly,hb,residual_z):
    z=poly.gen()
    ring_d=PolynomialRing(poly,"d")
    d=ring_d.gen()
    hbd=ring_d([poly(x) for x in hb.list()])
    u=(1+z**2*residual_z**2)*d**2+z*residual_z*d+(residual_z**2+z**2)
    return poly(hbd.resultant(u))


def n41_raw_points():
    screen=json.loads(SCREEN.read_text())
    hit=json.loads(HIT.read_text())
    ring,field,curve=field_curve(41)
    by_mask={row["mask"]:row for row in screen["raw_audit"]}
    points=[]
    for block in range(6):
        for local in range(2):
            i=2*block+local
            mask,sign=hit["masks"][i],hit["signs"][i]
            slot=next(row for row in screen["slots"][block]
                      if row["mask"]==mask and row["sign"]==sign)
            projected=curve(decode(ring,field,41,slot["point"][0]),
                            decode(ring,field,41,slot["point"][1]))
            raw_row=by_mask[mask]["raw_pair_point"]
            raw=curve(decode(ring,field,41,raw_row[0]),decode(ring,field,41,raw_row[1]))
            for _ in range(block*5):
                raw=curve(raw[0]**2,raw[1]**2)
            if 4*raw!=projected:raw=-raw
            assert 4*raw==projected
            points.append(raw)
    return ring,field,curve,points,hit["masks"],549756390943,hit["raw_sum"]


def n131_raw_points():
    solution=json.loads(LIFT.read_text())["solutions"][0]
    ring,field,curve=field_curve(131)
    points=[curve(decode(ring,field,131,x),decode(ring,field,131,y))
            for x,y in solution["raw_leaves"]]
    return ring,field,curve,points,solution["masks"],680564733841876926932320129493409985129,solution["projected_sum"]


def panel(n,d,rotations_a,rotations_b,source):
    ring,field,curve,points,masks,order,public_pair=source
    public=curve(decode(ring,field,n,public_pair[0]),
                 decode(ring,field,n,public_pair[1]))
    assert order*public==curve(0) and 4*sum(points,curve(0))==public
    t4=curve(field.one(),field.zero())
    assert 4*t4==curve(0) and 2*t4!=curve(0)
    base=pow(4,-1,order)*public
    raw_total=sum(points,curve(0))
    branches=[base+i*t4 for i in range(4)]
    assert len(set(branches))==4 and all(4*branch==public for branch in branches)
    matching=[i for i,branch in enumerate(branches) if branch==raw_total]
    assert len(matching)==1
    free_sum=sum(points[:4],curve(0))
    block_a=sum(points[4:8],curve(0))
    block_b=sum(points[8:12],curve(0))
    assert block_a+block_b==raw_total-free_sum
    assert block_a[0]!=0 and block_b[0]!=0
    za,zb=1/block_a[0],1/block_b[0]
    seed_a,a0,a1,pa,qa=block_parameters(field,d,rotations_a,masks[4:8])
    seed_b,b0,b1,pb,qb=block_parameters(field,d,rotations_b,masks[8:12])
    if n==41:assert (seed_a^seed_b)<8
    poly=PolynomialRing(field,"z")
    ha=h_polynomial(poly,a0,a1,pa,qa)
    hb=h_polynomial(poly,b0,b1,pb,qb)
    assert ha(za)==0 and hb(zb)==0 and ha.degree()<=8 and hb.degree()<=8
    out=[]
    for i,branch in enumerate(branches):
        residual=branch-free_sum
        assert residual!=curve(0) and residual[0]!=0
        zr=1/residual[0]
        started=time.perf_counter_ns()
        k=joint_eliminant(poly,hb,zr)
        eliminant_ns=time.perf_counter_ns()-started
        g=ha.gcd(k)
        witness_upper=(1+za**2*zb**2)*zr**2+za*zb*zr+(za+zb)**2
        if i==matching[0]:
            assert witness_upper==0 and k(za)==0 and g(za)==0 and g.degree()>0
        out.append({"branch":i,"matches_witness":i==matching[0],
                    "residual_z":encode(zr),"upper_equation_on_known_outputs_zero":witness_upper==0,
                    "h_a_degree":int(ha.degree()),"h_b_degree":int(hb.degree()),
                    "joint_eliminant_degree":int(k.degree()),
                    "joint_gcd_degree":int(g.degree()),
                    "eliminant_ns":eliminant_ns})
    return {"field_degree":n,"source_dimension":d,"seed_a":seed_a,"seed_b":seed_b,
            "cross_block_seed_offset":seed_a^seed_b,
            "public_target":public_pair,"known_block_output_z":[encode(za),encode(zb)],
            "known_products":[encode(pa),encode(qa),encode(pb),encode(qb)],
            "matching_branch":matching[0],"branches":out}


started=time.perf_counter_ns()
n41=panel(41,6,[10,15],[20,25],n41_raw_points())
print("N41_BRANCHES",[(x["branch"],x["joint_gcd_degree"],x["eliminant_ns"]) for x in n41["branches"]],flush=True)
n131=panel(131,15,[26,39],[52,65],n131_raw_points())
print("N131_BRANCHES",[(x["branch"],x["joint_gcd_degree"],x["eliminant_ns"]) for x in n131["branches"]],flush=True)
record={"status":"PASS_JOINT_BLOCK_RESULTANT_CONTROLS",
        "n41":n41,"n131":n131,"wall_ns":time.perf_counter_ns()-started,
        "protocol_sha256":sha(FREEZE),"source_sha256":freeze["source_sha256"]}
with (HERE/"result.json").open("x") as output:
    json.dump(record,output,sort_keys=True,indent=2)
    output.write("\n")
