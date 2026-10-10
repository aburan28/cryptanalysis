"""Freeze the independent N41 product-to-source replay."""

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
paths={"dual_replay.py":HERE/"dual_replay.py",
       "dual_result.json":HERE/"dual_result.json",
       "result.json":HERE/"result.json",
       "n41_screen":BASE/"n41_n131_diagonal_atom_20261010/screen.json",
       "n41_hit":BASE/"n131_w15_cross_block_seed_offset_20261010/n41_hit.json",
       "sage_runtime_info":HERE/"sage_runtime_info.json"}
record={"status":"FROZEN_BEFORE_N41_DUAL_SOURCE_REPLAY",
        "sha256":{name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in paths.items()},
        "workload":"N41 public point; first two free pairs fixed; reconstruct both remaining block masks and signs from dual-screen product families and verify distinct-column group sum",
        "candidate_id":None,"workers":1}
with (HERE/"replay_protocol.json").open("x") as output:
    json.dump(record,output,sort_keys=True,indent=2);output.write("\n")
