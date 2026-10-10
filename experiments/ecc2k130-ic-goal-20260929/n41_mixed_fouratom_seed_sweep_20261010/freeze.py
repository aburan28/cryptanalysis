#!/usr/bin/env python3
"""Freeze corrected N41 raw-atom seed sweep before measurement."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
files = {"sweep.py": HERE / "sweep.py",
         "screen.json": ROOT / "n41_n131_diagonal_atom_20261010/screen.json",
         "mixed_inputs.json": ROOT / "n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json",
         "sage_runtime_info.json": HERE / "sage_runtime_info.json"}
record = {"status": "FROZEN_BEFORE_N41_RAW_ATOM_SEED_SWEEP",
          "field": "GF(2^41), t^41+t^3+1",
          "rotations": [10, 15],
          "case_order": ["positive", "trace_zero_control"],
          "cap_seconds_per_case": 120,
          "rss_cap_bytes": 4294967296,
          "worker_count": 1,
          "source_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                            for name, path in files.items()}}
(HERE / "protocol.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
print(json.dumps({"status": record["status"]}, sort_keys=True))
