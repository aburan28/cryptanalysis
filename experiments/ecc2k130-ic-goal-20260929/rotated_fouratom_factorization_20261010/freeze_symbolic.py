"""Freeze the exact symbolic identity inputs before derivation."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_w15_rotated_fouratom_inverse_20261010" / "resultant.json"
paths = {"derive_symbolic": HERE / "derive_symbolic.py", "resultant": SOURCE,
         "runtime": HERE / "sage_runtime_info.json"}
record = {
    "status": "FROZEN_BEFORE_UNIVERSAL_ARTIN_SCHREIER_FACTORIZATION",
    "source_sha256": {name: [str(path), hashlib.sha256(path.read_bytes()).hexdigest()]
                      for name, path in paths.items()},
    "worker_count": 1,
    "parent_wall_cap_seconds": 120,
    "resource_note": "exploratory symbolic derivation; no CPU speedup metric",
    "substitution": {"b": "a+v^2+v", "z": "u^2+u"},
}
with (HERE / "symbolic_protocol.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
