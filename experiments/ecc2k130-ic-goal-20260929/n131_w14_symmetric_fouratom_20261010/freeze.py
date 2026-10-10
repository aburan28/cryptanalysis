#!/usr/bin/env python3
"""Freeze source identities before the exact Sage diagnostic."""

import hashlib
import json
from pathlib import Path

here = Path(__file__).resolve().parent
parent = here.parent / "n131_w14_coupled_fouratom_inverse_20261010"
paths = {
    "run.py": here / "run.py",
    "resultant_terms.json": parent / "resultant_terms.json",
    "inputs.json": parent / "inputs.json",
}
record = {
    "status": "FROZEN_BEFORE_RUN",
    "method": "Symmetric quotient H(s,p,q,z)=Hbar(s,p+q,pq,z); finite image check for T=p^2+Pp",
    "panels": [41, 131],
    "random_seed_rule": "20261010 + field degree",
    "random_identity_checks": {"41": 256, "131": 128},
    "n41_control_policy": "exhaustive 32 by 32 ordered algebraic pairs for both frozen z values",
    "n131_control_policy": "constructed pair evaluation for both frozen z values",
    "resource_policy": "one checked-Sage process; exploratory host timing; no single-target speed claim",
    "source_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                      for name, path in paths.items()},
}
(here / "protocol.json").write_text(json.dumps(record, indent=2, sort_keys=True)+"\n")
print(json.dumps(record["source_sha256"], sort_keys=True))
