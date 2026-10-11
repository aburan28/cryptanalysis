"""Freeze independent integer-field replay before auditing corrected lifts."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
paths = {"audit": HERE / "audit.py", "corrected": HERE / "result.json",
         "prior_torsion_screen": ROOT / "rotated_fouratom_factorization_20261010" / "torsion_result.json",
         "archived_preimages": ROOT / "n131_fixed_seed_eight_pair_circuit_20261010" / "target_preimages.json"}
record = {"status": "FROZEN_BEFORE_INDEPENDENT_RECIPROCAL_X_LIFT_AUDIT",
          "source_sha256": {name: [str(path), hashlib.sha256(path.read_bytes()).hexdigest()]
                            for name, path in paths.items()},
          "method": "integer GF(2^n) group arithmetic, fourfold replay, and coordinate conversion"}
with (HERE / "audit_protocol.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
