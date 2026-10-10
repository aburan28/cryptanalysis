#!/usr/bin/env sage -python
"""Reconstruct the surviving N41 block masks and signs from product values."""

import hashlib
import itertools
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
SCREEN=BASE/"n41_n131_diagonal_atom_20261010/screen.json"
HIT=BASE/"n131_w15_cross_block_seed_offset_20261010/n41_hit.json"
FREEZE=HERE/"replay_protocol.json"


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


freeze=json.loads(FREEZE.read_text())
assert freeze["status"]=="FROZEN_BEFORE_N41_DUAL_SOURCE_REPLAY"
assert freeze["sha256"]=={"dual_replay.py":sha(Path(__file__)),
    "dual_result.json":sha(HERE/"dual_result.json"),
    "result.json":sha(HERE/"result.json"),
    "n41_screen":sha(SCREEN),"n41_hit":sha(HIT),
    "sage_runtime_info":sha(HERE/"sage_runtime_info.json")}
assert not (HERE/"replay_result.json").exists()
screen=json.loads(SCREEN.read_text())
hit=json.loads(HIT.read_text())
dual=json.loads((HERE/"dual_result.json").read_text())
control=json.loads((HERE/"result.json").read_text())["n41"]
assert dual["status"]=="COMPLETE_N41_DUAL_PRODUCT_SCREEN"
ring=PolynomialRing(GF(2),"t")
t=ring.gen()
F=GF(2**41,"t",modulus=t**41+t**3+1)
E=EllipticCurve(F,[1,0,0,0,1])
zero=E(0)


def decode(value):return F(ring([(int(value)>>i)&1 for i in range(41)]))


def encode(value):return sum(int(bit)<<i for i,bit in enumerate(value.polynomial().list()))


def point(pair):return E(decode(pair[0]),decode(pair[1]))


def source_w(mask):
    return sum((F.gen()**(i+1) for i in range(6) if mask>>i&1),F.zero())


raw_by_mask={row["mask"]:point(row["raw_pair_point"]) for row in screen["raw_audit"]}


def rotated_raw(mask,block):
    p=raw_by_mask[mask]
    for _ in range(block*5):p=E(p[0]**2,p[1]**2)
    expected=next(row for row in screen["slots"][block]
                  if row["mask"]==mask and row["sign"]==0)
    if 4*p!=point(expected["point"]):p=-p
    assert 4*p==point(expected["point"])
    return p


def column(mask,block):
    return next(row["source_column"] for row in screen["slots"][block]
                if row["mask"]==mask and row["sign"]==0)


def product_pair(seed,rotation,product):
    pairs=set()
    for mask in range(64):
        if encode((source_w(mask)*source_w(mask^seed))**(2**rotation))==product:
            pairs.add(tuple(sorted((mask,mask^seed))))
    assert len(pairs)==1
    return next(iter(pairs))


def block_options(seed,rotations,products,output_z,first_block):
    first=product_pair(seed,rotations[0],products[0])
    second=product_pair(seed,rotations[1],products[1])
    masks=first+second
    atom_blocks=(first_block,first_block,first_block+1,first_block+1)
    if len({column(mask,block) for mask,block in zip(masks,atom_blocks)})!=4:
        return []
    raw=[rotated_raw(mask,block) for mask,block in zip(masks,atom_blocks)]
    options=[]
    for signs in itertools.product((0,1),repeat=4):
        p=sum((-atom if sign else atom for atom,sign in zip(raw,signs)),zero)
        if p==zero or p[0]==0 or encode(1/p[0])!=output_z:continue
        options.append({"masks":masks,"signs":signs,
                        "columns":[column(mask,block) for mask,block in zip(masks,atom_blocks)],
                        "point":p})
    return options


free=[]
for i in range(4):
    mask,sign=hit["masks"][i],hit["signs"][i]
    free.append(-rotated_raw(mask,i//2) if sign else rotated_raw(mask,i//2))
free_sum=sum(free,zero)
free_columns=[column(hit["masks"][i],i//2) for i in range(4)]
Q=point(control["public_target"])
order=549756390943
assert Q!=zero and order*Q==zero
t4=E(F.one(),F.zero())
assert 4*t4==zero and 2*t4!=zero
branches=[pow(4,-1,order)*Q+i*t4 for i in range(4)]
rows=[]
for row in dual["rows"]:
    branch=branches[row["branch"]]
    residual=branch-free_sum
    witness=[]
    for output in row["output_pairs"]:
        for fa in output["a_families"]:
            aa=block_options(control["seed_a"],(10,15),fa[:2],output["za"],2)
            for fb in output["b_families"]:
                bb=block_options(control["seed_b"],(20,25),fb[:2],output["zb"],4)
                for a in aa:
                    for b in bb:
                        if a["point"]+b["point"]!=residual:continue
                        columns=free_columns+a["columns"]+b["columns"]
                        if len(set(columns))!=12:continue
                        assert 4*(free_sum+a["point"]+b["point"])==Q
                        witness.append({"masks":hit["masks"][:4]+list(a["masks"])+list(b["masks"]),
                            "signs":hit["signs"][:4]+list(a["signs"])+list(b["signs"]),
                            "columns":columns,"branch":row["branch"]})
    rows.append({"branch":row["branch"],"output_pairs":row["output_pair_count"],
        "verified_reconstruction_count":len(witness),"witnesses":witness})
assert sum(row["verified_reconstruction_count"] for row in rows)>0
record={"status":"PASS_N41_DUAL_PRODUCT_SOURCE_REPLAY",
    "public_target":control["public_target"],"subgroup_order":str(order),
    "fixed_free_masks":hit["masks"][:4],"fixed_free_signs":hit["signs"][:4],
    "rows":rows,"protocol_sha256":sha(FREEZE)}
with (HERE/"replay_result.json").open("x") as output:
    json.dump(record,output,sort_keys=True,indent=2);output.write("\n")
print({"status":record["status"],
       "verified_by_branch":[row["verified_reconstruction_count"] for row in rows]})
