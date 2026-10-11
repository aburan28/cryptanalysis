"""Bind all correction receipts before the terminal audit."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
names = ("terminal_audit.py", "result.json", "audit_result.json", "lift_result.json",
         "source_trace_result.json")
record = {"status": "FROZEN_BEFORE_CORRECTED_PUBLIC_LIFT_TERMINAL_AUDIT",
          "source_sha256": {name: [str(HERE / name), hashlib.sha256((HERE / name).read_bytes()).hexdigest()]
                            for name in names}}
with (HERE / "terminal_protocol.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
