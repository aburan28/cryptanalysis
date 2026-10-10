"""Freeze independent replay of the N131 offset-three constructed control."""

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
OLD=BASE/"n131_w15_coupled_sixpair_20261010"
paths={"restricted_audit.py":HERE/"restricted_audit.py",
       "restricted_result.json":HERE/"restricted_result.json",
       "w15_lift.py":OLD/"w15_lift.py",
       "support_w15.tsv":OLD/"support_w15.tsv",
       "rotated_resultant":BASE/"n131_w15_rotated_fouratom_inverse_20261010/resultant.json",
       "sage_runtime_info":HERE/"sage_runtime_info.json"}
record={"status":"FROZEN_BEFORE_N131_EIGHT_OFFSET_REPLAY",
        "sha256":{name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in paths.items()},
        "candidate_id":None,"workers":1}
with (HERE/"restricted_audit_protocol.json").open("x") as output:
    json.dump(record,output,sort_keys=True,indent=2);output.write("\n")
