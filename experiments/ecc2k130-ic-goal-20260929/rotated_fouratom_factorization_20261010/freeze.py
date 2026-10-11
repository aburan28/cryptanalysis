"""Bind the specialization/factorization source and field controls."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n131_w15_rotated_fouratom_inverse_20261010"
paths = {"derive": HERE / "derive.py",
         "resultant": SOURCE / "resultant.json",
         "controls": SOURCE / "control_result.json",
         "runtime": HERE / "sage_runtime_info.json"}
record = {
    "status": "FROZEN_BEFORE_SPECIALIZED_ROTATED_RESULTANT_FACTORIZATION",
    "source_sha256": {name: [str(path), hashlib.sha256(path.read_bytes()).hexdigest()]
                      for name, path in paths.items()},
    "cases": ["n41_positive", "n41_control", "n41_public_target",
              "n131_positive", "n131_control"],
    "worker_count": 1,
    "per_case_parent_cap_seconds": 100,
    "rss_cap_bytes": 4294967296,
    "output_scope": "exact polynomial factorization and product identity; times exploratory",
}
with (HERE / "protocol.json").open("x") as output:
    json.dump(record, output, sort_keys=True, indent=2)
    output.write("\n")
