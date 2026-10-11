"""Terminal source and result audit for N41 four-atom bucket census."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
REPLAY=BASE/"n41_seed_partition_indexless_20261010/replay_result.json"


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):return json.loads((HERE/name).read_text())


protocol=read("protocol.json")
assert protocol["status"]=="FROZEN_BEFORE_N41_FOURATOM_BUCKET_CENSUS"
assert protocol["source_sha256"]=={
    "produce.py":digest(HERE/"produce.py"),
    "run.py":digest(HERE/"run.py"),
    "replay_result.json":digest(REPLAY),
    "sage_runtime_info.json":digest(HERE/"sage_runtime_info.json")}
assert protocol["source_dimensions"]==[3,4,5,6]
assert protocol["worker_count"]==1
assert protocol["memory_cap_bytes"]==4*1024**3

result=read("result.json")
receipt=read("receipt.json")
assert result["status"]=="PASS_N41_FOURATOM_BUCKET_POLYNOMIAL_CENSUS"
assert result["source_sha256"]==protocol["source_sha256"]
assert result["protocol_sha256"]==digest(HERE/"protocol.json")
assert receipt["status"]=="COMPLETE" and receipt["exit_code"]==0
assert receipt["result_exists"]
assert receipt["protocol_sha256"]==digest(HERE/"protocol.json")
assert receipt["parent_wall_s"]<protocol["cap_seconds"]
assert receipt["sampled_peak_rss_bytes"]<protocol["memory_cap_bytes"]

audit_protocol=read("audit_protocol.json")
assert audit_protocol["status"]=="FROZEN_BEFORE_N41_INTEGER_FIELD_REPLAY"
assert audit_protocol["source_sha256"]=={
    "audit.py":digest(HERE/"audit.py"),
    "run_audit.py":digest(HERE/"run_audit.py"),
    "result.json":digest(HERE/"result.json")}
audit=read("audit_result.json")
audit_receipt=read("audit_receipt.json")
assert audit["status"]=="PASS_N41_FOURATOM_BUCKET_INDEPENDENT_INTEGER_FIELD_REPLAY"
assert audit["protocol_sha256"]==digest(HERE/"audit_protocol.json")
assert audit_receipt["status"]=="COMPLETE" and audit_receipt["exit_code"]==0
assert audit_receipt["result_exists"]
assert audit_receipt["parent_wall_s"]<audit_protocol["cap_seconds"]
assert audit_receipt["sampled_peak_rss_bytes"]<audit_protocol["memory_cap_bytes"]

assert [row["source_dimension"] for row in result["rows"]]==[3,4,5,6]
assert len(audit["rows"])==4
assert [row["polynomial_degree"] for row in result["rows"]]==[50,170,370,1370]
for row,other in zip(result["rows"],audit["rows"]):
    assert row["source_dimension"]==other["source_dimension"]
    assert row["polynomial_degree"]==other["block_output_count"]
    assert row["polynomial_nonzero_coefficients"]==row["polynomial_degree"]+1
    assert row["polynomial_nonzero_coefficients"]==other["polynomial_nonzero_coefficients"]
    assert row["polynomial_dense_coefficient_sha256"]==other["dense_coefficient_sha256"]
assert result["rows"][-1]["known_n41_public_witness_output_root"]

out={"status":"PASS_N41_FOURATOM_BUCKET_TERMINAL_AUDIT",
     "source_sha256":digest(Path(__file__)),
     "evidence_sha256":{name:digest(HERE/name) for name in
         ["protocol.json","result.json","receipt.json","audit_protocol.json",
          "audit_result.json","audit_receipt.json"]},
     "candidate_id":None}
with (HERE/"terminal_audit.json").open("w") as stream:
    json.dump(out,stream,sort_keys=True,indent=2)
    stream.write("\n")
print(out["status"])
