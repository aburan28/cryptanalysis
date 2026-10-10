"""Freeze an independent direct-product check of the sparse certificate."""

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
paths={"audit.py":HERE/"audit.py",
    "polynomial_sparse_v3.json":HERE/"polynomial_sparse_v3.json",
    "result_v3.json":HERE/"result_v3.json",
    "receipt_v3.json":HERE/"receipt_v3.json",
    "restricted_audit_result.json":BASE/"n131_w15_joint_block_resultant_20261010/restricted_audit_result.json"}
record={"status":"FROZEN_BEFORE_W15_SPARSE_DIRECT_PRODUCT_AUDIT",
    "sha256":{name:hashlib.sha256(path.read_bytes()).hexdigest()
              for name,path in paths.items()},
    "input_law":"known raw-pair output from frozen N131 constructed control, t+1, t squared+t+1, and t to 13+t to 5+1",
    "method":"independent bit-polynomial field arithmetic, enumerate all 16384 distinct seed products, compare direct factor product to saved sparse coefficient evaluation",
    "candidate_id":None,"workers":1}
with (HERE/"audit_protocol.json").open("x") as output:
    json.dump(record,output,sort_keys=True,indent=2);output.write("\n")
