"""Independent integer-field replay of the N131 pair-bucket hit."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
RESULT=HERE/"as_result.json"
CONTROL=BASE/"n131_w15_joint_block_resultant_20261010/restricted_result.json"
SUPPORT=BASE/"n131_w15_coupled_sixpair_20261010/support_w15.tsv"
MODULUS=(1<<131)|(1<<13)|(1<<2)|(1<<1)|1
MASK=(1<<131)-1


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


freeze=json.loads((HERE/"audit_protocol.json").read_text())
assert freeze["status"]=="FROZEN_BEFORE_AS_HIT_AUDIT"
assert freeze["source_sha256"]=={
    "audit_as.py":digest(Path(__file__)),
    "as_result.json":digest(RESULT),
    "restricted_result.json":digest(CONTROL),
    "support_w15.tsv":digest(SUPPORT)}
assert not (HERE/"audit_result.json").exists()


def mul(a,b):
    out=0
    while b:
        if b&1:out^=a
        b>>=1
        a<<=1
        if a&(1<<131):a^=MODULUS
    return out&MASK


def square(a):return mul(a,a)


def frob(a,k):
    for _ in range(k):a=square(a)
    return a


def g(c,p,s):
    pc=mul(p,c)
    return square(c)^square(s)^square(pc)^pc


def upper(c,d,r):
    cd=mul(c,d)
    return mul(1^square(cd),square(r))^mul(cd,r)^square(c^d)


result=json.loads(RESULT.read_text())
control=json.loads(CONTROL.read_text())
support={int(m):int(col) for m,col in
         (line.split() for line in SUPPORT.read_text().splitlines())}
assert result["status"]=="PASS_N131_W15_ONE_SIDED_AS_JOIN_CONTROLS"
assert result["positive"]["bucket_hit_count"]==1
assert result["negative"]["bucket_hit_count"]==0
hit=result["positive"]["bucket_hits"][0]
lm,ln=hit["left_masks"]
rm,rn=hit["right_masks"]
assert {lm,ln}==set(control["masks"][4:6])
assert {rm,rn}==set(control["masks"][6:8])
assert all(m in support for m in (lm,ln,rm,rn))
assert len({support[m] for m in (lm,ln,rm,rn)})==4
assert (lm^ln)==(rm^rn)==13686
pl=frob(mul(lm<<1,ln<<1),26)
pr=frob(mul(rm<<1,rn<<1),39)
sl=frob(13686<<1,26)
sr=frob(13686<<1,39)
assert pl==hit["left_product"]==control["known_products"][0]
assert pr==hit["right_product"]==control["known_products"][1]
c,d=hit["left_output"],hit["right_output"]
assert g(c,pl,sl)==g(d,pr,sr)==0
assert upper(c,d,result["positive_residual"])==0
assert upper(c,d,result["negative_residual"])!=0
record={"status":"PASS_AS_HIT_INDEPENDENT_INTEGER_FIELD_REPLAY",
        "field_degree":131,"seed":13686,"verified_hit":hit,
        "positive_residual":result["positive_residual"],
        "negative_residual":result["negative_residual"],
        "all_four_folded_columns_distinct":True,
        "source_sha256":freeze["source_sha256"],
        "protocol_sha256":digest(HERE/"audit_protocol.json")}
with (HERE/"audit_result.json").open("x") as stream:
    json.dump(record,stream,sort_keys=True,indent=2)
    stream.write("\n")
print(record["status"])
