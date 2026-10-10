#!/usr/bin/env sage -python
"""Independent N131 seven-source control group and archived-formula audit."""
import gzip
import hashlib
import json
from pathlib import Path
from sage.all import EllipticCurve, GF, PolynomialRing

here=Path(__file__).resolve().parent
params_path=Path("/Volumes/SSD990/crypto/docs/ic/params/ecc2k130-fixed.json")
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
prep=json.loads((here/"n131_preparation.json").read_text())
control=prep["control"]
result=json.loads((here/"n131_control_result.json").read_text())
terminal=json.loads((here/"n131_control_terminal.json").read_text())
params=json.loads(params_path.read_text())
assert prep["status"]=="PASS_OFFICIAL_SUBGROUP_AND_PLANTED_CONTROL"
assert result["status"]=="PASS_FULL_FORMULA_CONTROL"
assert terminal["status"]=="PASS"
assert result["formula"]["clauses"]==result["xcnf_check"]["cnf_clauses"]
assert result["formula"]["xor_rows"]==result["xcnf_check"]["xor_rows"]
archive=here/"n131_control.xcnf.gz"
assert result["formula"]["compressed_sha256"]==sha(archive)
digest=hashlib.sha256()
bytes_read=0
with gzip.open(archive,"rb") as stream:
    for block in iter(lambda:stream.read(1<<20),b""):
        digest.update(block)
        bytes_read+=len(block)
assert digest.hexdigest()==result["formula"]["sha256"]
assert bytes_read==result["formula"]["bytes"]

ring=PolynomialRing(GF(2),"t")
t=ring.gen()
field=GF(2**131,name="t",modulus=t**131+t**13+t**2+t+1)
curve=EllipticCurve(field,[1,0,0,0,1])
zero=curve(0)
R=int(params["curve"]["subgroup_order"])
def decode(value):
    return field(ring([(int(value)>>i)&1 for i in range(131)]))
def encode(value):
    return sum(int(bit)<<i for i,bit in enumerate(value.polynomial().list()))
def point(values):
    return curve(decode(values[0]),decode(values[1]))
def key(p):
    return [encode(p[0]),encode(p[1])]
def phi(p):
    assert p!=zero and p[0]!=1
    return 1/(p[0]+1)
def frob(p):
    return curve(p[0]**2,p[1]**2)

support={}
for line in (here/"support_w19.tsv").open():
    mask,canonical=map(int,line.split())
    support[mask]=canonical
assert [support[mask] for mask in control["masks"]]==control["folded_columns"]
assert len(set(control["folded_columns"]))==7
leaves=[]
for i,mask in enumerate(control["masks"]):
    u=field.zero()
    for bit,value in enumerate(prep["bases_u"][i]):
        if mask>>bit&1:
            u+=decode(value)
    assert u not in (0,1) and encode(u)==control["leaf_u"][i]
    raw=point(control["raw_leaves"][i])
    assert raw in curve.lift_x(1+1/u,all=True)
    assert phi(raw)==u
    leaves.append(raw)
middle=[leaves[0]+leaves[1],leaves[2]+leaves[3],leaves[4]+leaves[5]]
middle += [middle[0]+middle[1]]
middle += [middle[3]+middle[2]]
total=middle[4]+leaves[6]
assert [encode(phi(p)) for p in middle]==control["middle_u"]
assert key(total)==control["raw_sum"]
qprime=point(control["target_qprime"])
q=point(control["target_q"])
assert 4*total==qprime and qprime+frob(qprime)==q
assert R*qprime==R*q==zero
torsion=curve(field.one(),field.zero())
fiber=[pow(4,-1,R)*qprime+k*torsion for k in range(4)]
assert fiber.index(total)==control["target_preimage_index"]
assert [encode(phi(p)) for p in fiber]==control["target_preimages_u"]
audit={"status":"PASS_EXACT_GROUP_AND_ARCHIVED_XCNF_CONTROL",
       "factor_base_B":prep["actual_factor_base_points_B"],
       "folded_columns_K":prep["folded_columns_K"],
       "raw_leaves_checked":len(leaves),"middle_sums_checked":len(middle),
       "xcnf_bytes_checked":bytes_read,
       "xcnf_clauses":result["formula"]["clauses"],
       "xcnf_xor_rows":result["formula"]["xor_rows"],
       "source_sha256":{"prep":sha(here/"n131_preparation.json"),
                        "control_result":sha(here/"n131_control_result.json"),
                        "control_terminal":sha(here/"n131_control_terminal.json"),
                        "formula_archive":sha(archive),
                        "support":sha(here/"support_w19.tsv"),
                        "script":sha(Path(__file__))}}
with (here/"n131_control_audit.json").open("x") as out:
    json.dump(audit,out,indent=2,sort_keys=True)
    out.write("\n")
print(json.dumps({"status":audit["status"],"raw_leaves":len(leaves)}))
