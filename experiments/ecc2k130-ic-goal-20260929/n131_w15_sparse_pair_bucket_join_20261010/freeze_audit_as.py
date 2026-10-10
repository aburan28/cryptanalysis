import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


record={"status":"FROZEN_BEFORE_AS_HIT_AUDIT",
        "source_sha256":{
            "audit_as.py":digest(HERE/"audit_as.py"),
            "as_result.json":digest(HERE/"as_result.json"),
            "restricted_result.json":digest(BASE/"n131_w15_joint_block_resultant_20261010/restricted_result.json"),
            "support_w15.tsv":digest(BASE/"n131_w15_coupled_sixpair_20261010/support_w15.tsv")}}
with (HERE/"audit_protocol.json").open("x") as stream:
    json.dump(record,stream,sort_keys=True,indent=2)
    stream.write("\n")
