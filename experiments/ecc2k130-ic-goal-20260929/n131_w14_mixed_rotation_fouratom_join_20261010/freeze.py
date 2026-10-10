#!/usr/bin/env python3
"""Freeze exact mixed-rotation controls, sources, binary, and run order."""

import hashlib
import json
from pathlib import Path

here = Path(__file__).resolve().parent
old = here.parent / "n131_w14_coupled_fouratom_inverse_20261010"
support = here.parent / "n131_w14_ten_source_gate_20261009" / "support_w14.tsv"
inputs = json.loads((here / "inputs.json").read_text())
assert inputs["status"] == "PASS_MIXED_ROTATION_CONTROLS"
files = {
    "native.cpp": here / "native.cpp",
    "native": here / "native",
    "prepare.py": here / "prepare.py",
    "inputs.json": here / "inputs.json",
    "run.py": here / "run.py",
    "sage_audit.py": here / "sage_audit.py",
    "sage_runtime_info.json": here / "sage_runtime_info.json",
    "legacy_native.cpp": old / "native.cpp",
    "support_w14.tsv": support,
}
order = []
for n in (41,131):
    panel = inputs["panels"][str(n)]
    r1,r2 = panel["rotations"]
    for case in ("positive","trace_zero_control"):
        z = panel["positive_z" if case == "positive" else "trace_zero_control_z"]
        path = here / f"n{n}_{case}.txt"
        path.write_text(f"{n} {panel['source_dimension']} {panel['seed_sum']} {r1} {r2} {z}\n")
        files[path.name] = path
        order.append([n,case])
protocol = {
    "status": "FROZEN_BEFORE_MIXED_ROTATION_PANEL",
    "candidate_id": None,
    "curve_ids": {str(n):inputs["panels"][str(n)]["curve_id"] for n in (41,131)},
    "field_models": {"41":"t^41+t^3+1", "131":"t^131+t^13+t^2+t+1"},
    "rotations": {"41":[10,15], "131":[26,39]},
    "run_order": order,
    "cap_seconds_per_run": 30,
    "rss_cap_bytes": 4294967296,
    "worker_count": 1,
    "source_sha256": {name:hashlib.sha256(path.read_bytes()).hexdigest()
                     for name,path in files.items()},
}
(here / "protocol.json").write_text(json.dumps(protocol,indent=2,sort_keys=True)+"\n")
print(json.dumps({"status":protocol["status"],"runs":len(order)},sort_keys=True))
