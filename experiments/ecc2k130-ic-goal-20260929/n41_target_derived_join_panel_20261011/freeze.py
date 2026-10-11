"""Freeze the seeded panel and both native executables before measurement."""

import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
panel = json.loads((HERE / "panel.json").read_text())
assert panel["status"] == "FROZEN_SEEDED_TARGET_DERIVED_N41_PANEL"
assert panel["selected_count"] == 512
paths = {
    "panel": HERE / "panel.json",
    "targets": HERE / "targets.txt",
    "exact_input": HERE / "exact_input.txt",
    "producer": HERE / "make_panel_sage.py",
    "sage_runtime": HERE / "sage_runtime_info.json",
    "relaxed_source": HERE / "relaxed_panel.cpp",
    "relaxed_binary": HERE / "relaxed_panel_native",
    "exact_source": HERE / "exact_panel.cpp",
    "exact_binary": HERE / "exact_panel_native",
    "helper": ROOT / "experiments/koblitz-s5-invariant-20260924/three_pair_s7_native.cpp",
    "source_input": HERE.parent / "n131_w18_four_pairs/native_join/native_input.txt",
    "source_fixture": HERE.parent / "n41_transport_cubic_s8_20261011/fixture.json",
    "raw_input": HERE.parent / "n41_exact_transport_pair_join_20261011/input_v2.txt",
    "prior_relaxed": HERE.parent / "n41_direct_relaxed_pair_join_20261011/receipt.json",
    "prior_exact": HERE.parent / "n41_exact_transport_pair_join_20261011/receipt_v2.json",
}
out = {"status": "FROZEN_N41_TARGET_DERIVED_RELAXED_EXACT_PANEL",
       "candidate_id": None,
       "utc": datetime.now(timezone.utc).isoformat(),
       "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
       "platform": platform.platform(), "machine": platform.machine(),
       "compiler": subprocess.check_output(["clang++", "--version"], text=True).splitlines()[0],
       "compile_flags": ["-std=c++17", "-O3", "-Wall", "-Wextra"],
       "sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                  for name, path in paths.items()},
       "limits": {"workers": 1, "relaxed_setup_seconds": 120,
                  "relaxed_seconds_per_query": 120,
                  "total_seconds_per_panel": 600,
                  "rss_bytes": 4*1024**3},
       "comparison": "identical seeded public-target-derived middle points; relaxed complete join then exact complete join"}
path = HERE / "protocol.json"
if path.exists():
    raise SystemExit("protocol exists")
path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(out["status"], hashlib.sha256(path.read_bytes()).hexdigest())
