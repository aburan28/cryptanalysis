#!/usr/bin/env python3
"""Freeze a same-source baseline and target-split half-trace panel."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT / "n131_w14_mixed_rotation_fouratom_join_20261010"
SUPPORT = ROOT / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
LEGACY = ROOT / "n131_w14_coupled_fouratom_inverse_20261010/native.cpp"
files = {name: HERE / name for name in
         ("native.cpp", "native", "baseline.cpp", "baseline", "run.py",
          "compiler_version.txt")}
files.update({"legacy_native.cpp": LEGACY,
              "support_w14.tsv": SUPPORT,
              "mixed_inputs.json": BASE / "inputs.json"})
for n in (41, 131):
    for case in ("positive", "trace_zero_control"):
        name = f"n{n}_{case}.txt"
        files[name] = BASE / name
assert (HERE / "baseline.cpp").read_bytes() == (BASE / "native.cpp").read_bytes()
order = []
for n in (41, 131):
    for case in ("positive", "trace_zero_control"):
        for variant in ("baseline", "split", "split", "baseline"):
            order.append([n, case, variant])
protocol = {
    "status": "FROZEN_BEFORE_TARGET_SPLIT_HALFTRACE_PANEL",
    "candidate_id": None,
    "compiler_command": "clang++ -O3 -std=c++17 SOURCE -o BINARY",
    "worker_count": 1,
    "cap_seconds_per_run": 30,
    "rss_cap_bytes": 4294967296,
    "run_order": order,
    "source_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                      for name, path in files.items()}}
(HERE / "protocol.json").write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
print(json.dumps({"status": protocol["status"], "trials": len(order)}, sort_keys=True))
