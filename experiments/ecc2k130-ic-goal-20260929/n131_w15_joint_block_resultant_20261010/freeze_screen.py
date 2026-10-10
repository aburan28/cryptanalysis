"""Freeze N41 within-branch product-family screen inputs."""

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROTATED=HERE.parent/"n131_w15_rotated_fouratom_inverse_20261010/resultant.json"
paths={"screen.py":HERE/"screen.py","result.json":HERE/"result.json",
       "rotated_resultant":ROTATED,"sage_runtime_info":HERE/"sage_runtime_info.json"}
record={"status":"FROZEN_BEFORE_N41_JOINT_PRODUCT_FAMILY_SCREEN",
        "sha256":{name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in paths.items()},
        "workload":"N41 public point; known first two free-pair outputs and fixed second-block product family; screen all 1,024 first-block product families in each raw target branch",
        "workers":1}
with (HERE/"screen_protocol.json").open("x") as output:
    json.dump(record,output,sort_keys=True,indent=2);output.write("\n")
