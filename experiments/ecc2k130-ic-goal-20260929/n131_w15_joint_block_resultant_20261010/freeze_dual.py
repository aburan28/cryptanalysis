"""Freeze the N41 both-product-family screen before running Sage."""

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
paths={"dual_screen.py":HERE/"dual_screen.py",
       "result.json":HERE/"result.json",
       "rotated_resultant":BASE/"n131_w15_rotated_fouratom_inverse_20261010/resultant.json",
       "sage_runtime_info":HERE/"sage_runtime_info.json"}
record={"status":"FROZEN_BEFORE_N41_DUAL_PRODUCT_SCREEN",
        "sha256":{name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in paths.items()},
        "workload":"N41 public point; known first two free-pair outputs and fixed block seeds; both block product families unrestricted; all four raw target branches",
        "candidate_id":None,"workers":1}
with (HERE/"dual_protocol.json").open("x") as output:
    json.dump(record,output,sort_keys=True,indent=2);output.write("\n")
