#!/usr/bin/env sage -python
"""Freeze exact N131 basis, official subgroup identity, and separate control."""
import hashlib
import json
import random
from pathlib import Path
from sage.all import EllipticCurve, GF, PolynomialRing

here = Path(__file__).resolve().parent
params_path = Path("/Volumes/SSD990/crypto/docs/ic/params/ecc2k130-fixed.json")
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
protocol = json.loads((here/"support_protocol.json").read_text())
receipt = json.loads((here/"support_receipt.json").read_text())
audit = json.loads((here/"sage_support_audit.json").read_text())
runtime = json.loads((here/"sage_runtime_info.json").read_text())
params = json.loads(params_path.read_text())
assert protocol["status"] == "FROZEN_BEFORE_ENUMERATION"
assert receipt["status"] == "COMPLETE"
assert audit["status"] == "PASS_FULL_MASKS_ORBITS_AND_DISJOINT_WINDOWS"
assert runtime["status"] == "verified"
assert params["curve"]["degree"] == 131
assert params["curve"]["polynomial"] == "0x800000000000000000000000000002007"
R = int(params["curve"]["subgroup_order"])
ring = PolynomialRing(GF(2),"t")
t = ring.gen()
field = GF(2**131,name="t",modulus=t**131+t**13+t**2+t+1)
curve = EllipticCurve(field,[1,0,0,0,1])
zero = curve(0)
def decode(value):
    value = int(value,0) if isinstance(value,str) else int(value)
    return field(ring([(value>>i)&1 for i in range(131)]))
def encode(value):
    return sum(int(bit)<<i for i,bit in enumerate(value.polynomial().list()))
def point(values):
    return curve(decode(values[0]),decode(values[1]))
def key(p):
    return [encode(p[0]),encode(p[1])]
def frob(p):
    return curve(p[0]**2,p[1]**2)
def phi(p):
    if p==zero or p[0]==1:
        raise ValueError("undefined transformed coordinate")
    value = 1/(p[0]+1)
    if value in (0,1):
        raise ValueError("exceptional transformed coordinate")
    return value
G = point((params["generator"]["x"],params["generator"]["y"]))
Q = point((params["targets"][0]["x"],params["targets"][0]["y"]))
assert G != zero and Q != zero and R*G == R*Q == zero
roots = [(-GF(R)(1)+s)/2 for s in GF(R)(-7).sqrt(all=True)]
matching = [root for root in roots if int(root)*G == frob(G)]
if len(matching)!=1:
    raise ValueError("official-generator Frobenius eigenvalue ambiguous")
lam = int(matching[0])
assert (lam*lam+lam+2)%R == 0 and pow(lam,131,R)==1
assert lam*Q == frob(Q)

source_basis = [field.gen()**i for i in range(1,20)]
def halftrace(value):
    acc,term=field.zero(),value
    for _ in range(66):
        acc += term
        term = term**4
    assert acc**2+acc == value
    return acc
base_u = [halftrace(value) for value in source_basis]
rotations = protocol["rotations"]
bases_u = []
current = base_u[:]
for shift in range(max(rotations)+1):
    if shift in rotations:
        bases_u.append([encode(value) for value in current])
    current = [value**2 for value in current]
assert len(bases_u)==7

valid = {}
for line in (here/"support_w19.tsv").open():
    mask,canonical = map(int,line.split())
    valid[mask]=canonical
assert len(valid)==262390
rng = random.Random(202610091800)
masks_by_canonical = {}
for mask,canonical in valid.items():
    masks_by_canonical.setdefault(canonical,[]).append(mask)
torsion = curve(field.one(),field.zero())
assert 4*torsion == zero and 2*torsion != zero
for attempt in range(1000):
    selected = rng.sample(sorted(masks_by_canonical),7)
    masks = [rng.choice(masks_by_canonical[column]) for column in selected]
    leaves,signs,leaf_u = [],[],[]
    for i,mask in enumerate(masks):
        u = field.zero()
        for bit,basis_value in enumerate(bases_u[i]):
            if mask>>bit&1:
                u += decode(basis_value)
        assert u not in (0,1)
        options = sorted(curve.lift_x(1+1/u,all=True),key=lambda p:encode(p[1]))
        if len(options)!=2:
            raise ValueError("rational source mask has no two point signs")
        sign=rng.randrange(2)
        p=options[sign]
        assert phi(p)==u
        signs.append(sign)
        leaves.append(p)
        leaf_u.append(encode(u))
    middle=[leaves[0]+leaves[1],leaves[2]+leaves[3],leaves[4]+leaves[5]]
    middle += [middle[0]+middle[1]]
    middle += [middle[3]+middle[2]]
    total=middle[4]+leaves[6]
    if any(p==zero or p[0] in (0,1) for p in [*middle,total]):
        continue
    qprime=4*total
    if qprime==zero:
        continue
    qcontrol=qprime+frob(qprime)
    assert R*qprime==R*qcontrol==zero
    core=pow(4,-1,R)*qprime
    targets=[core+k*torsion for k in range(4)]
    if total not in targets:
        raise ValueError("planted raw endpoint absent from cofactor fiber")
    control={"kind":"n131_seven_source_planted_formula_control",
             "attempt":attempt,"seed":202610091800,
             "masks":masks,"signs":signs,"folded_columns":selected,
             "raw_leaves":[key(p) for p in leaves],
             "leaf_u":leaf_u,"middle_u":[encode(phi(p)) for p in middle],
             "raw_sum":key(total),"target_qprime":key(qprime),
             "target_q":key(qcontrol),
             "target_preimages_u":[encode(phi(p)) for p in targets],
             "target_preimage_index":targets.index(total)}
    break
else:
    raise RuntimeError("could not construct a nonexceptional planted control")

record={"kind":"n131_w19_seven_linear_source_exact_prep",
        "status":"PASS_OFFICIAL_SUBGROUP_AND_PLANTED_CONTROL",
        "curve_id":"EC1N131Ckb1heb5f1998f20b",
        "official_public_q":key(Q),"official_generator_g":key(G),
        "subgroup_order_r":str(R),"frobenius_eigenvalue_mod_r":str(lam),
        "bases_u":bases_u,"rotations":rotations,
        "actual_factor_base_points_B":receipt["actual_subgroup_factor_base_points_B"],
        "folded_columns_K":receipt["folded_columns_K"],
        "control":control,
        "source_sha256":{"params":sha(params_path),
                         "support_protocol":sha(here/"support_protocol.json"),
                         "support":sha(here/"support_w19.tsv"),
                         "support_audit":sha(here/"sage_support_audit.json"),
                         "runtime":sha(here/"sage_runtime_info.json"),
                         "script":sha(Path(__file__))}}
path=here/"n131_preparation.json"
with path.open("x") as out:
    json.dump(record,out,indent=2,sort_keys=True)
    out.write("\n")
print(json.dumps({"status":record["status"],"control_attempt":attempt,
                  "B":record["actual_factor_base_points_B"],
                  "K":record["folded_columns_K"]}))
