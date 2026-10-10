#!/usr/bin/env python3
"""Freeze the exact W14 source-filtered pair-output comparison."""

import hashlib
import json
from pathlib import Path

here = Path(__file__).resolve().parent
legacy = here.parent / "n131_w14_coupled_fouratom_inverse_20261010"
support = here.parent / "n131_w14_ten_source_gate_20261009" / "support_w14.tsv"
files = {
    "native_filtered.cpp": here / "native_filtered.cpp",
    "native_filtered": here / "native_filtered",
    "native.cpp": here / "native.cpp",
    "native": here / "native",
    "legacy_native.cpp": legacy / "native.cpp",
    "legacy_native": legacy / "native",
    "support_w14.tsv": support,
    "n131_positive.txt": legacy / "native_n131_positive.txt",
    "n131_trace_zero_control.txt": legacy / "native_n131_trace_zero_control.txt",
    "run_filtered.py": here / "run_filtered.py",
}
record = {
    "status": "FROZEN_BEFORE_FILTERED_COMPARISON",
    "field": "GF(2^131), t^131+t^13+t^2+t+1",
    "curve": "y^2+xy=x^3+1",
    "source": "W14 rational masks with distinct archived folded columns; seed s=t",
    "support_policy": "For mask a and b=a XOR 1, both rows must be present in support_w14.tsv and columns differ",
    "expected_rational_masks": 8220,
    "expected_allowed_source_pairs": 2062,
    "run_order": [[case, variant] for case in ("positive", "trace_zero_control")
                  for variant in ("legacy", "pair_join", "filtered_pair_join")],
    "cap_seconds_per_run": 120,
    "rss_cap_bytes": 4294967296,
    "worker_count": 1,
    "timing_policy": "native setup_ns separate from proposed-output query_ns; exploratory host",
    "source_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                      for name, path in files.items()},
}
(here / "protocol_filtered.json").write_text(json.dumps(record, indent=2, sort_keys=True)+"\n")
print(json.dumps({"status": record["status"],
                  "run_count": len(record["run_order"])}, sort_keys=True))
