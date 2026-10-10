#!/usr/bin/env python3
"""Freeze a rationality/upper-S3 trace audit over the exact pair supports."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sources = {"audit.py": HERE / "audit.py",
           "arithmetic_snapshot.py": ROOT / "n41_two_free_pair_occupancy_20261009/arithmetic_snapshot.py",
           "n41_screen.json": ROOT / "n41_n131_diagonal_atom_20261010/screen.json",
           "mixed_inputs.json": ROOT / "n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json",
           "n131_index.bin": ROOT / "n131_mixed_s3_stream64_20261010/index.bin",
           "n131_index_setup.json": ROOT / "n131_mixed_s3_stream64_20261010/setup.json"}
record = {"status": "FROZEN_BEFORE_S3_RATIONAL_TRACE_AUDIT",
          "candidate_id": None,
          "fields": {"41": "t^41+t^3+1",
                     "131": "t^131+t^13+t^2+t+1"},
          "worker_count": 1, "cap_seconds": 120,
          "rss_cap_bytes": 4294967296,
          "source_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                            for name, path in sources.items()}}
(HERE / "protocol.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
print(json.dumps({"status": record["status"]}, sort_keys=True))
