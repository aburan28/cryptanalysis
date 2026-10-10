import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


record={"status":"FROZEN_BEFORE_SOURCE_PAIR_CENSUS",
        "source_sha256":{
            "projection.py":digest(HERE/"projection.py"),
            "support_w15.tsv":digest(BASE/"n131_w15_coupled_sixpair_20261010/support_w15.tsv"),
            "as_result.json":digest(HERE/"as_result.json")}}
with (HERE/"projection_protocol.json").open("x") as stream:
    json.dump(record,stream,sort_keys=True,indent=2)
    stream.write("\n")
