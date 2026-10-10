"""Terminal provenance, failure, cap, and sparse-certificate audit."""

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
RESTRICTED=BASE/"n131_w15_joint_block_resultant_20261010/restricted_result.json"
RESTRICTED_AUDIT=BASE/"n131_w15_joint_block_resultant_20261010/restricted_audit_result.json"
SUPPORT=BASE/"n131_w15_coupled_sixpair_20261010/support_w15.tsv"


def read(path):return json.loads(path.read_text())


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


for version in (1,2,3):
    suffix="" if version==1 else f"_v{version}"
    protocol=read(HERE/f"protocol{suffix}.json")
    source={f"produce{suffix}.py":HERE/f"produce{suffix}.py",
            f"run{suffix}.py":HERE/f"run{suffix}.py",
            "restricted_result.json":RESTRICTED,
            "support_w15.tsv":SUPPORT,
            "sage_runtime_info":HERE/"sage_runtime_info.json"}
    assert protocol["sha256"]=={name:sha(path) for name,path in source.items()}

failure=read(HERE/"failure_v1.json")
assert failure["status"]=="PRODUCER_FAILURE_RSS_MONITOR_PERMISSION"
assert failure["protocol_sha256"]==sha(HERE/"protocol.json")
assert failure["runner_sha256"]==sha(HERE/"run.py")
assert failure["producer_sha256"]==sha(HERE/"produce.py")
assert failure["result_present"] is False
assert failure["stdout_sha256"]==sha(HERE/"stdout.txt")
assert failure["stderr_sha256"]==sha(HERE/"stderr.txt")

results=[]
for version in (2,3):
    suffix=f"_v{version}"
    receipt=read(HERE/f"receipt{suffix}.json")
    result=read(HERE/f"result{suffix}.json")
    n41=read(HERE/f"control_n41{suffix}.json")
    assert receipt["status"]==result["status"]=="PASS_N41_N131_PAIR_BUCKET_POLYNOMIAL_CONTROLS"
    assert receipt["process_exit_code"]==0 and receipt["protocol_sha256"]==sha(HERE/f"protocol{suffix}.json")
    assert receipt["result_sha256"]==sha(HERE/f"result{suffix}.json")
    assert receipt["n41_control_sha256"]==sha(HERE/f"control_n41{suffix}.json")
    assert receipt["peak_sampled_process_rss_bytes"]<4294967296
    assert receipt["parent_wall_ns"]<150*10**9
    assert receipt["stderr_sha256"]==sha(HERE/f"stderr{suffix}.txt")
    assert result["n41"]==n41 and n41["direct_product_equal"] is True
    assert n41["degree"]==64 and n41["nonzero_coefficients"]==33
    assert result["n131"]["product_basis_dimension"]==14
    assert result["n131"]["degree"]==32768
    assert result["n131"]["nonzero_coefficients"]==486
    assert result["n131"]["known_output_polynomial_zero"] is True
    assert result["n131"]["field_control_polynomial_zero"]==[0,0]
    assert result["source_sha256"]==read(HERE/f"protocol{suffix}.json")["sha256"]
    results.append(result)
assert results[0]["n131"]["coefficient_sha256"]==results[1]["n131"]["coefficient_sha256"]

sparse=read(HERE/"polynomial_sparse_v3.json")
result=results[1]
assert result["n131"]["sparse_polynomial_sha256"]==sha(HERE/"polynomial_sparse_v3.json")
assert read(HERE/"receipt_v3.json")["sparse_polynomial_sha256"]==sha(HERE/"polynomial_sparse_v3.json")
assert len(sparse["terms"])==486 and sparse["terms"][-1][0]==32768
assert sparse["dense_coefficient_sha256"]==result["n131"]["coefficient_sha256"]

audit_protocol=read(HERE/"audit_protocol.json")
audit_sources={"audit.py":HERE/"audit.py",
    "polynomial_sparse_v3.json":HERE/"polynomial_sparse_v3.json",
    "result_v3.json":HERE/"result_v3.json",
    "receipt_v3.json":HERE/"receipt_v3.json",
    "restricted_audit_result.json":RESTRICTED_AUDIT}
assert audit_protocol["sha256"]=={name:sha(path) for name,path in audit_sources.items()}
audit=read(HERE/"audit_result.json")
assert audit["status"]=="PASS_W15_SPARSE_POLYNOMIAL_INDEPENDENT_DIRECT_PRODUCT"
assert audit["protocol_sha256"]==sha(HERE/"audit_protocol.json")
assert audit["product_count"]==16384 and len(audit["rows"])==4
assert all(row["direct_value"]==row["sparse_value"] for row in audit["rows"])
assert audit["rows"][0]["sparse_value"]==0

out={"status":"PASS_W15_PAIR_BUCKET_POLYNOMIAL_TERMINAL_AUDIT",
    "candidate_id":None,
    "n41_degree":64,"n41_terms":33,
    "n131_degree":32768,"n131_terms":486,
    "n131_product_count":16384,
    "n131_dense_coefficient_sha256":sparse["dense_coefficient_sha256"],
    "v3_parent_wall_ns":read(HERE/"receipt_v3.json")["parent_wall_ns"],
    "v3_peak_sampled_process_rss_bytes":read(HERE/"receipt_v3.json")["peak_sampled_process_rss_bytes"],
    "protocol_sha256":sha(HERE/"protocol_v3.json"),
    "audit_protocol_sha256":sha(HERE/"audit_protocol.json")}
with (HERE/"terminal_audit.json").open("x") as output:
    json.dump(out,output,sort_keys=True,indent=2);output.write("\n")
print(out)
