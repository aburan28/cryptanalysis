"""Freeze the exact W15 support-bound calculation."""

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
paths={"project.py":HERE/"project.py",
       "native.cpp":HERE/"native.cpp",
       "support_w15.tsv":BASE/"n131_w15_coupled_sixpair_20261010/support_w15.tsv",
       "signed_seed_counts.tsv":BASE/"n131_w15_cross_block_seed_offset_20261010/signed_seed_counts.tsv",
       "protocol.json":HERE/"protocol.json"}
record={"status":"FROZEN_BEFORE_W15_FIRST_BUCKET_EXACT_COUNT",
    "sha256":{name:hashlib.sha256(path.read_bytes()).hexdigest()
              for name,path in paths.items()},
    "candidate_id":None,"workers":1}
with (HERE/"projection_protocol.json").open("x") as output:
    json.dump(record,output,sort_keys=True,indent=2);output.write("\n")
