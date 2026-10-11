"""Freeze independent GF(2) identity replay before execution."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_w15_rotated_fouratom_inverse_20261010" / "resultant.json"
paths = {"audit": HERE / "audit_symbolic.py", "resultant": SOURCE,
         "symbolic_result": HERE / "symbolic_result.json"}
record = {"status": "FROZEN_BEFORE_INDEPENDENT_GF2_QUARTIC_IDENTITY_REPLAY",
          "source_sha256": {name: [str(path), hashlib.sha256(path.read_bytes()).hexdigest()]
                            for name, path in paths.items()},
          "method": "sparse monomial expansion and XOR cancellation; no Sage factorization dependency"}
with (HERE / "symbolic_audit_protocol.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
