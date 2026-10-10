"""Freeze the corrected per-process RSS monitor before its W15 run."""

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
paths={"produce_v2.py":HERE/"produce_v2.py","run_v2.py":HERE/"run_v2.py",
       "restricted_result.json":BASE/"n131_w15_joint_block_resultant_20261010/restricted_result.json",
       "support_w15.tsv":BASE/"n131_w15_coupled_sixpair_20261010/support_w15.tsv",
       "sage_runtime_info":HERE/"sage_runtime_info.json"}
record={"status":"FROZEN_BEFORE_W15_PAIR_BUCKET_POLYNOMIAL_V2",
    "sha256":{name:hashlib.sha256(path.read_bytes()).hexdigest()
              for name,path in paths.items()},
    "cases":["N41 full 32-product identity at seed four",
             "N131 W15 seed 13686 known pair and two fixed field controls"],
    "one_worker":True,"parent_cap_seconds":150,"rss_cap_bytes":4294967296,
    "rss_policy":"sample launched Sage process RSS every 50 ms; launcher uses exec",
    "candidate_id":None}
with (HERE/"protocol_v2.json").open("x") as output:
    json.dump(record,output,sort_keys=True,indent=2);output.write("\n")
