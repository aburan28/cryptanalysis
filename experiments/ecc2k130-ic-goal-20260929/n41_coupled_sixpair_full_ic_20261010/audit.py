#!/usr/bin/env sage -python
"""Independent Sage replay of 26 setup relations and factor-base logs."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, Matrix, PolynomialRing, is_prime

HERE=Path(__file__).resolve().parent
R=549756390943
K=26


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block:=stream.read(1<<20):
            digest.update(block)
    return digest.hexdigest()


def main():
    protocol=json.loads((HERE / "protocol.json").read_text())
    workload=json.loads((HERE / "workload.json").read_text())
    collection=json.loads((HERE / "collection_result.json").read_text())
    factors=json.loads((HERE / "factor_logs.json").read_text())
    runtime=json.loads((HERE / "sage_runtime_info.json").read_text())
    rows=[json.loads(line) for line in (HERE / "rows.jsonl").read_text().splitlines()]
    assert runtime["status"]=="verified"
    assert protocol["status"]=="FROZEN_BEFORE_N41_W6_FACTOR_LOG_COLLECTION"
    assert collection["status"]=="FULL_RANK_FACTOR_LOGS_PENDING_SAGE_REPLAY"
    assert factors["status"]==collection["status"]
    assert collection["source_sha256"]["rows"]==sha(HERE / "rows.jsonl")
    assert factors["source_sha256"]["rows"]==sha(HERE / "rows.jsonl")
    assert len(rows)==collection["attempted_queries"]==26
    assert collection["final_rank"]==K
    assert is_prime(R)
    ring=PolynomialRing(GF(2),"t")
    t=ring.gen()
    field=GF(2**41,name="t",modulus=t**41+t**3+1)
    curve=EllipticCurve(field,[1,0,0,0,1])
    zero=curve(0)

    def decode(value):
        return field(ring([(int(value)>>i)&1 for i in range(41)]))

    def encode(value):
        return sum(int(bit)<<i for i,bit in enumerate(value.polynomial().list()))

    def point(pair):
        return curve(decode(pair[0]),decode(pair[1]))

    def key(p):
        return (encode(p[0]),encode(p[1]))

    def frobenius(p):
        return curve(p[0]**2,p[1]**2)

    generator=point(workload["generator"])
    lam=workload["frobenius_eigenvalue_mod_r"]
    assert R*generator==zero and lam*generator==frobenius(generator)
    reps=[point(pair) for pair in workload["representatives"]]
    logs=factors["logs_mod_r"]
    assert len(reps)==len(logs)==K
    for i,(rep,log) in enumerate(zip(reps,logs)):
        assert R*rep==zero
        assert log*generator==rep, f"factor-base logarithm {i} failed replay"
    orbit={}
    for column,representative in enumerate(reps):
        current=representative
        coefficient=1
        for shift in range(41):
            for candidate,factor in ((current,coefficient),(-current,-coefficient)):
                value=(column,factor%R)
                k=key(candidate)
                if k in orbit and orbit[k]!=value:
                    raise AssertionError("signed Frobenius orbit collision")
                orbit[k]=value
            current=frobenius(current)
            coefficient=(coefficient*lam)%R
    atom_map={}
    for atom in workload["atoms"]:
        point_key=tuple(atom["point"])
        assert orbit[point_key]==(atom["column"],atom["coefficient_mod_r"])
        atom_map[(atom["block"],atom["mask"],atom["sign"])]=atom
    assert len(atom_map)==384
    coefficients=[]
    for index,row in enumerate(rows):
        fixture=workload["setup_targets"][index]
        assert row["index"]==fixture["index"]==index
        assert row["scalar"]==fixture["scalar"]
        q=point(fixture["point"])
        assert q==row["scalar"]*generator and tuple(row["target_q"])==key(q)
        assert row["native_status"]=="FOUND_PENDING_SAGE_REPLAY"
        assert row["rank_before"]==index and row["rank_after"]==index+1
        assert row["novel_rank"] is True
        folder=HERE / "runs" / f"{index:03d}"
        native=json.loads((folder / "native_result.json").read_text())
        hit=json.loads((folder / "hit.json").read_text())
        assert native["status"]=="FOUND_PENDING_SAGE_REPLAY"
        assert row["native_result_sha256"]==sha(folder / "native_result.json")
        assert row["hit_sha256"]==sha(folder / "hit.json")
        assert tuple(hit["raw_sum"])==key(q)
        assert len(set(hit["columns"]))==12
        assert hit["seed_sums"][2]==hit["seed_sums"][3]
        assert hit["seed_sums"][4]==hit["seed_sums"][5]
        selected=[]
        vector=[0]*K
        for slot,(mask,sign,column) in enumerate(zip(hit["masks"],hit["signs"],hit["columns"])):
            atom=atom_map[(slot//2,mask,sign)]
            p=point(atom["point"])
            assert atom["column"]==column
            independent_column,coefficient=orbit[key(p)]
            assert independent_column==column
            vector[column]=(vector[column]+coefficient)%R
            selected.append(p)
        assert sum(selected,zero)==q
        assert vector==row["coefficients_mod_r"]
        assert sum(value*log for value,log in zip(vector,logs))%R==row["scalar"]
        coefficients.append(vector)
    assert Matrix(GF(R),coefficients).rank()==K
    receipt={"status":"PASS_INDEPENDENT_SAGE_N41_FACTOR_LOGS_AND_26_RELATIONS",
             "candidate_id":None,"curve_id":workload["curve_id"],
             "setup_relation_count":len(rows),"novel_rank":K,
             "folded_columns_K":K,"verified_factor_logs":K,
             "generator":workload["generator"],
             "source_sha256":{"script":sha(__file__),"protocol":sha(HERE / "protocol.json"),
                              "workload":sha(HERE / "workload.json"),
                              "collection":sha(HERE / "collection_result.json"),
                              "rows":sha(HERE / "rows.jsonl"),
                              "factors":sha(HERE / "factor_logs.json"),
                              "runtime":sha(HERE / "sage_runtime_info.json")}}
    with (HERE / "sage_audit.json").open("x") as out:
        json.dump(receipt,out,indent=2,sort_keys=True)
        out.write("\n")
    print(json.dumps({"status":receipt["status"],
                      "setup_relation_count":len(rows),
                      "verified_factor_logs":K}))


if __name__=="__main__":
    main()
