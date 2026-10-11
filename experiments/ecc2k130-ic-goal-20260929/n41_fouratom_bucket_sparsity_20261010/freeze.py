import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


record={"status":"FROZEN_BEFORE_N41_FOURATOM_BUCKET_CENSUS",
        "source_sha256":{
            "produce.py":digest(HERE/"produce.py"),
            "run.py":digest(HERE/"run.py"),
            "replay_result.json":digest(BASE/"n41_seed_partition_indexless_20261010/replay_result.json"),
            "sage_runtime_info.json":digest(HERE/"sage_runtime_info.json")},
        "field_degree":41,"source_dimensions":[3,4,5,6],
        "seed":2,"rotations":[20,25],
        "cap_seconds":150,"memory_cap_bytes":4*1024**3,"worker_count":1,
        "enumerated_domain":"all algebraic product-image outputs; source support filter absent"}
with (HERE/"protocol.json").open("x") as stream:
    json.dump(record,stream,sort_keys=True,indent=2)
    stream.write("\n")
