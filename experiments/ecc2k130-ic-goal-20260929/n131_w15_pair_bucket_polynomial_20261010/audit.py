"""Independent bit-field replay of the saved W15 bucket polynomial."""

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
FREEZE=HERE/"audit_protocol.json"


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


freeze=json.loads(FREEZE.read_text())
assert freeze["status"]=="FROZEN_BEFORE_W15_SPARSE_DIRECT_PRODUCT_AUDIT"
assert freeze["sha256"]=={"audit.py":sha(Path(__file__)),
    "polynomial_sparse_v3.json":sha(HERE/"polynomial_sparse_v3.json"),
    "result_v3.json":sha(HERE/"result_v3.json"),
    "receipt_v3.json":sha(HERE/"receipt_v3.json"),
    "restricted_audit_result.json":sha(BASE/"n131_w15_joint_block_resultant_20261010/restricted_audit_result.json")}
assert not (HERE/"audit_result.json").exists()
polynomial=json.loads((HERE/"polynomial_sparse_v3.json").read_text())
result=json.loads((HERE/"result_v3.json").read_text())
assert result["status"]=="PASS_N41_N131_PAIR_BUCKET_POLYNOMIAL_CONTROLS"
terms=polynomial["terms"]
assert len(terms)==result["n131"]["nonzero_coefficients"]==486
assert terms[0][0]==0 and terms[-1][0]==32768
assert all(terms[i][0]<terms[i+1][0] for i in range(len(terms)-1))
MOD=(1<<131)|(1<<13)|(1<<2)|(1<<1)|1
MASK=(1<<131)-1


def mul(a,b):
    out=0
    while b:
        if b&1:out^=a
        b>>=1
        a<<=1
        if a&(1<<131):a^=MOD
    return out


def square(a):return mul(a,a)


def w(mask):return mask<<1


seed=result["n131"]["seed"]
s=w(seed)
basis=[]
pivots={}
for i in range(15):
    wi=1<<(i+1)
    value=square(wi)^mul(s,wi)
    bits=value
    while bits:
        top=bits.bit_length()-1
        if top in pivots:bits^=pivots[top]
        else:pivots[top]=bits;basis.append(value);break
assert len(basis)==14
products=[0]
for value in basis:products += [x^value for x in products]
assert len(products)==16384 and len(set(products))==16384


def sparse_eval(c):
    squares=[c]
    for _ in range(15):squares.append(square(squares[-1]))
    result=0
    for exponent,coefficient in terms:
        power=1
        bit=0
        while exponent:
            if exponent&1:power=mul(power,squares[bit])
            exponent>>=1;bit+=1
        result^=mul(coefficient,power)
    return result


def direct_eval(c):
    cc=square(c)
    ss=square(s)
    out=1
    terms_evaluated=0
    for product in products:
        pc=mul(product,c)
        factor=cc^ss^square(pc)^pc
        out=mul(out,factor)
        terms_evaluated+=1
        if out==0:break
    return out,terms_evaluated


dense=[0]*32769
for exponent,coefficient in terms:
    assert 0<=exponent<=32768 and 0<=coefficient<=MASK
    dense[exponent]=coefficient
digest=hashlib.sha256()
for value in dense:digest.update(value.to_bytes(17,"little"))
assert digest.hexdigest()==polynomial["dense_coefficient_sha256"]
assert digest.hexdigest()==result["n131"]["coefficient_sha256"]

inputs=[result["n131"]["known_normalized_pair_output"],
        (1<<1)|1,(1<<2)|(1<<1)|1,(1<<13)|(1<<5)|1]
rows=[]
for c in inputs:
    sparse=sparse_eval(c)
    direct,checked=direct_eval(c)
    assert sparse==direct
    rows.append({"coordinate":c,"sparse_value":sparse,
                 "direct_value":direct,"direct_factors_evaluated":checked})
assert rows[0]["sparse_value"]==0
assert [int(rows[i]["sparse_value"]==0) for i in (1,2)]==result["n131"]["field_control_polynomial_zero"]
out={"status":"PASS_W15_SPARSE_POLYNOMIAL_INDEPENDENT_DIRECT_PRODUCT",
    "seed":seed,"product_basis_dimension":len(basis),
    "product_count":len(products),"degree":32768,"nonzero_coefficients":len(terms),
    "coefficient_sha256":digest.hexdigest(),"rows":rows,
    "protocol_sha256":sha(FREEZE),"candidate_id":None}
with (HERE/"audit_result.json").open("x") as output:
    json.dump(out,output,sort_keys=True,indent=2);output.write("\n")
print({"status":out["status"],"values":[row["sparse_value"] for row in rows]})
