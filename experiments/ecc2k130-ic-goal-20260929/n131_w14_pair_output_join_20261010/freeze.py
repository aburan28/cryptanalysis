#!/usr/bin/env python3
"""Freeze source, executable, inputs, and run order before the comparison."""

import hashlib
import json
from pathlib import Path

here = Path(__file__).resolve().parent
legacy = here.parent / "n131_w14_coupled_fouratom_inverse_20261010"
files = {
    "native.cpp": here / "native.cpp",
    "native": here / "native",
    "legacy_native.cpp": legacy / "native.cpp",
    "legacy_native": legacy / "native",
    "legacy_resultant_terms.hpp": legacy / "resultant_terms.hpp",
    "run.py": here / "run.py",
}
for n in (41, 131):
    for case in ("positive", "trace_zero_control"):
        files[f"n{n}_{case}.txt"] = legacy / f"native_n{n}_{case}.txt"
record = {
    "status": "FROZEN_BEFORE_MATCHED_DIAGNOSTIC",
    "field_models": {"41": "t^41+t^3+1", "131": "t^131+t^13+t^2+t+1"},
    "curve_model": "y^2+xy=x^3+1",
    "source_seed": 2,
    "cap_seconds_per_run": 120,
    "rss_cap_bytes": 4294967296,
    "worker_count": 1,
    "comparison_order": [
        [n, case, variant]
        for n in (41, 131)
        for case in ("positive", "trace_zero_control")
        for variant in ("legacy", "pair_join")
    ],
    "timing_policy": "setup_ns and query_ns from native monotonic clock; exploratory host",
    "source_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                      for name, path in files.items()},
}
(here / "protocol.json").write_text(json.dumps(record, indent=2, sort_keys=True)+"\n")
print(json.dumps({"status": record["status"],
                  "run_count": len(record["comparison_order"])}, sort_keys=True))
