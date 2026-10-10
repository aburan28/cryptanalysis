"""Terminal evidence audit for the sparse pair-bucket join experiment."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):return json.loads((HERE/name).read_text())


def source_path(name):
    mapping={
        "replay_result.json":BASE/"n41_seed_partition_indexless_20261010/replay_result.json",
        "restricted_result.json":BASE/"n131_w15_joint_block_resultant_20261010/restricted_result.json",
        "support_w15.tsv":BASE/"n131_w15_coupled_sixpair_20261010/support_w15.tsv",
        "polynomial_sparse_v3.json":BASE/"n131_w15_pair_bucket_polynomial_20261010/polynomial_sparse_v3.json"}
    return mapping.get(name,HERE/name)


def check_protocol(name):
    record=read(name)
    assert all(digest(source_path(k))==value for k,value in record["source_sha256"].items())
    return record


for name in ["protocol.json","protocol_v2.json","protocol_v3.json",
             "protocol_n131.json","protocol_n131_v2.json","protocol_n131_v3.json",
             "protocol_as.json","audit_protocol.json","projection_protocol.json"]:
    check_protocol(name)

assert read("n41_receipt.json")["reason"]=="WALL_CAP"
assert read("n41_receipt_v2.json")["exit_code"]==-6
assert read("n41_receipt_v3.json")["status"]=="COMPLETE"
assert read("n131_receipt.json")["reason"]=="RSS_CAP"
assert read("n131_receipt_v2.json")["status"]=="PRODUCER_RECEIPT_WRITE_ENOSPC"
assert read("n131_receipt_v3.json")["reason"]=="RSS_CAP"
assert read("as_receipt.json")["status"]=="COMPLETE"

n41=read("n41_result_v3.json")
assert n41["status"]=="PASS_N41_QUOTIENT_PAIR_BUCKET_JOIN_V3"
assert n41["positive"]["intersection_degree"]==1
assert n41["positive"]["known_right_root_in_intersection"]
assert n41["negative"]["intersection_degree"]==0
assert n41["protocol_sha256"]==digest(HERE/"protocol_v3.json")

as_result=read("as_result.json")
assert as_result["status"]=="PASS_N131_W15_ONE_SIDED_AS_JOIN_CONTROLS"
assert as_result["usable_product_pairs"]==4144
assert as_result["right_output_count"]==8288
assert as_result["positive"]["upper_candidates"]==16576
assert as_result["positive"]["bucket_hit_count"]==1
assert as_result["positive"]["known_witness_count"]==1
assert as_result["negative"]["bucket_hit_count"]==0
assert as_result["protocol_sha256"]==digest(HERE/"protocol_as.json")

audit=read("audit_result.json")
assert audit["status"]=="PASS_AS_HIT_INDEPENDENT_INTEGER_FIELD_REPLAY"
assert audit["protocol_sha256"]==digest(HERE/"audit_protocol.json")
assert audit["verified_hit"]==as_result["positive"]["bucket_hits"][0]
projection=read("projection_result.json")
assert projection["different_column_unordered_pairs"]==135144958
assert projection["protocol_sha256"]==digest(HERE/"projection_protocol.json")

files=["n41_result_v3.json","n41_receipt.json","n41_receipt_v2.json",
       "n41_receipt_v3.json","n131_receipt.json","n131_receipt_v2.json",
       "n131_receipt_v3.json","as_result.json","as_receipt.json",
       "audit_result.json","projection_result.json"]
out={"status":"PASS_N41_N131_PAIR_BUCKET_JOIN_TERMINAL_AUDIT",
     "result_sha256":{name:digest(HERE/name) for name in files},
     "verification_source_sha256":digest(Path(__file__)),
     "candidate_id":None}
with (HERE/"terminal_audit.json").open("w") as stream:
    json.dump(out,stream,sort_keys=True,indent=2)
    stream.write("\n")
print(out["status"])
