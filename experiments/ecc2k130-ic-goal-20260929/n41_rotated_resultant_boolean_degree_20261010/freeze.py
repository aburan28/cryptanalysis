"""Freeze exact inputs and resource ceiling before the ANF calculation."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "n131_w15_rotated_fouratom_inverse_20261010"
sources = {"run": HERE / "run.py", "resultant": PARENT / "resultant.json",
           "control": PARENT / "control_result.json"}
record = {
    "status": "FROZEN_BEFORE_N41_ROTATED_RESULTANT_BOOLEAN_ANF",
    "source_sha256": {key: [str(path), hashlib.sha256(path.read_bytes()).hexdigest()]
                      for key, path in sources.items()},
    "resource": {"workers": 1, "wall_cap_seconds": 120,
                 "rss_cap_bytes": 4294967296},
    "cases": ["N41 public relation block", "independent field-element control"],
    "method": "all 1024 product pairs then exact GF(2^41)-valued Mobius transform",
}
with (HERE / "protocol.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
