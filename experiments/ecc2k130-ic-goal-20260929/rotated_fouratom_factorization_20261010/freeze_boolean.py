"""Freeze the N41 quartic Boolean-support experiment."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
paths = {"evaluator": HERE / "factor_boolean.py",
         "positive_factors": HERE / "n41_positive.json",
         "public_factors": HERE / "n41_public_target.json",
         "earlier_full_resultant": ROOT / "n41_rotated_resultant_boolean_degree_20261010" / "result.json"}
record = {"status": "FROZEN_BEFORE_N41_QUARTIC_BOOLEAN_SUPPORT",
          "source_sha256": {name: [str(path), hashlib.sha256(path.read_bytes()).hexdigest()]
                            for name, path in paths.items()},
          "cases": ["known public relation block", "public target as proposed block output"],
          "method": "all 1024 product pairs and exact field-valued Mobius transform"}
with (HERE / "boolean_protocol.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
