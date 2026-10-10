"""Freeze the Sage replay inputs for all four native terminal rows."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
names = ["audit_native.py", "control_result.json", "resultant.json",
         "native_protocol.json", "sage_runtime_info.json"]
for label in ("n41_positive", "n41_field_control", "n131_positive", "n131_field_control"):
    names.extend([f"native_{label}.json", f"receipt_{label}.json"])
record = {"status": "FROZEN_BEFORE_INDEPENDENT_NATIVE_SAGE_AUDIT",
          "sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                     for name in names}}
with (HERE / "audit_protocol.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
