"""Freeze the exact W15 offset-three source construction and joint screen."""

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
OLD=BASE/"n131_w15_coupled_sixpair_20261010"
paths={"restricted_control.py":HERE/"restricted_control.py",
       "w15_lift.py":OLD/"w15_lift.py",
       "support_w15.tsv":OLD/"support_w15.tsv",
       "control_group_lift.json":OLD/"control_group_lift.json",
       "rotated_resultant":BASE/"n131_w15_rotated_fouratom_inverse_20261010/resultant.json",
       "sage_runtime_info":HERE/"sage_runtime_info.json"}
record={"status":"FROZEN_BEFORE_N131_EIGHT_OFFSET_CONSTRUCTED_CONTROL",
        "sha256":{name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in paths.items()},
        "source_law":"retain archived first eight leaves; choose lexicographically first two disjoint distinct-column W15 pairs for last four leaves with seed offset three; signs zero for last four",
        "candidate_id":None,"workers":1}
with (HERE/"restricted_protocol.json").open("x") as output:
    json.dump(record,output,sort_keys=True,indent=2);output.write("\n")
