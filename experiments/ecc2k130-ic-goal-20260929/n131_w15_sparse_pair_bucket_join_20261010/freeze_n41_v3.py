import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


record={"status":"FROZEN_BEFORE_N41_QUOTIENT_JOIN_V3",
        "source_sha256":{
            "n41_quotient_v3.py":digest(HERE/"n41_quotient_v3.py"),
            "run_n41_v3.py":digest(HERE/"run_n41_v3.py"),
            "replay_result.json":digest(BASE/"n41_seed_partition_indexless_20261010/replay_result.json"),
            "sage_runtime_info.json":digest(HERE/"sage_runtime_info.json")},
        "cap_seconds":120,"memory_cap_bytes":4*1024**3,"worker_count":1,
        "positive_control":"N41 public relation pair blocks 4 and 5",
        "negative_control":"fixed nonroot residual t+1"}
with (HERE/"protocol_v3.json").open("x") as stream:
    json.dump(record,stream,sort_keys=True,indent=2)
    stream.write("\n")
