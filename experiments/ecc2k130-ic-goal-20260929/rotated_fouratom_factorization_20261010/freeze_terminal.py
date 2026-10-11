"""Freeze exact receipt inputs before the terminal audit."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
names = ("terminal_audit.py", "symbolic_result.json", "symbolic_audit_result.json",
         "torsion_result.json", "boolean_result.json", "split_n131_positive.json",
         "split_receipt.json", "split_audit_result.json")
record = {"status": "FROZEN_BEFORE_QUARTIC_FACTORIZATION_TERMINAL_AUDIT",
          "source_sha256": {name: [str(HERE / name), hashlib.sha256((HERE / name).read_bytes()).hexdigest()]
                            for name in names}}
with (HERE / "terminal_protocol.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
