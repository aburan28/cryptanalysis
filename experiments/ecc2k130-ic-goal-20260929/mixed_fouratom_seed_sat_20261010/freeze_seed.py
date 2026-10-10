#!/usr/bin/env python3
"""Freeze exact all-seed N41 comparator before its checked-Sage run."""

import hashlib
import json
from pathlib import Path

here=Path(__file__).resolve().parent
root=here.parent
files={"allseed.py":here/"allseed.py",
       "w6_input.txt":root/"n41_upper_xor_projection_20261010/w6_input.txt",
       "mixed_inputs.json":root/"n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json",
       "sage_runtime_info.json":here/"sage_runtime_info.json"}
record={"status":"FROZEN_BEFORE_N41_MIXED_ALLSEED_SWEEP",
        "field":"GF(2^41), t^41+t^3+1","rotations":[10,15],
        "case_order":["positive","trace_zero_control"],
        "cap_seconds_per_case":120,"rss_cap_bytes":4294967296,
        "worker_count":1,
        "source_sha256":{name:hashlib.sha256(path.read_bytes()).hexdigest()
                         for name,path in files.items()}}
(here/"seed_protocol.json").write_text(json.dumps(record,indent=2,sort_keys=True)+"\n")
print(json.dumps({"status":record["status"]},sort_keys=True))
