"""Freeze the independent checked-Sage replay on the system volume."""

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
EXPERIMENT=HERE
BASE=EXPERIMENT.parent
paths={"audit":HERE/"replay.py",
       "screen":BASE/"n41_n131_diagonal_atom_20261010/screen.json",
       "input":BASE/"n41_coupled_sixpair_full_ic_20261010/heldout_input.txt",
       "native":EXPERIMENT/"native_result.json",
       "hit":EXPERIMENT/"hit.json",
       "query_receipt":EXPERIMENT/"receipt.json",
       "runtime":EXPERIMENT/"sage_runtime_info.json"}
record={"status":"FROZEN_BEFORE_N41_SEED_PARTITION_SAGE_REPLAY",
        "curve_id":"EC1N41Ckb1h023d9a38bbf7",
        "source_sha256":{name:hashlib.sha256(path.read_bytes()).hexdigest()
                         for name,path in paths.items()},
        "workers":1,"candidate_id":None}
with (HERE/"replay_protocol.json").open("x") as output:
    json.dump(record,output,sort_keys=True,indent=2);output.write("\n")
