import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


record={"status":"FROZEN_BEFORE_N131_W15_QUOTIENT_JOIN_V3",
        "source_sha256":{
            "n131_quotient_v3.py":digest(HERE/"n131_quotient_v3.py"),
            "run_n131_v3.py":digest(HERE/"run_n131_v3.py"),
            "restricted_result.json":digest(BASE/"n131_w15_joint_block_resultant_20261010/restricted_result.json"),
            "polynomial_sparse_v3.json":digest(BASE/"n131_w15_pair_bucket_polynomial_20261010/polynomial_sparse_v3.json"),
            "sage_runtime_info.json":digest(HERE/"sage_runtime_info.json")},
        "cap_seconds":600,"memory_cap_bytes":4*1024**3,"worker_count":1,
        "positive_control":"constructed N131 block A, pair rotations 26 and 39",
        "negative_control":"fixed nonroot residual t+1",
        "stage":"target-conditioned pair-bucket intersection only"}
with (HERE/"protocol_n131_v3.json").open("x") as stream:
    json.dump(record,stream,sort_keys=True,indent=2)
    stream.write("\n")
