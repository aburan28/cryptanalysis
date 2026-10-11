import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


record={"status":"FROZEN_BEFORE_N41_INTEGER_FIELD_REPLAY",
        "source_sha256":{
            "audit.py":digest(HERE/"audit.py"),
            "run_audit.py":digest(HERE/"run_audit.py"),
            "result.json":digest(HERE/"result.json")},
        "cap_seconds":120,"memory_cap_bytes":1*1024**3,"worker_count":1}
with (HERE/"audit_protocol.json").open("x") as stream:
    json.dump(record,stream,sort_keys=True,indent=2)
    stream.write("\n")
