"""Bind independent tensor audit sources before replay."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "n131_w15_rotated_fouratom_inverse_20261010"
sources = {"audit": HERE / "audit.py", "result": HERE / "result.json",
           "resultant": PARENT / "resultant.json",
           "control": PARENT / "control_result.json"}
record = {"status": "FROZEN_BEFORE_TENSOR_ANF_AUDIT",
          "source_sha256": {name: [str(path), hashlib.sha256(path.read_bytes()).hexdigest()]
                            for name, path in sources.items()},
          "method": "univariate power ANFs and tensor coefficient assembly, independent of 1024 full resultant evaluations"}
with (HERE / "audit_protocol.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
