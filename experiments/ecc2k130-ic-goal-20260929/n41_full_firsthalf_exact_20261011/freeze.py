"""Freeze all eligible N41 first-half inputs and exact join executable."""

import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
panel = json.loads((HERE / "panel.json").read_text())
assert panel["status"] == "FROZEN_FULL_TARGET_DERIVED_N41_FIRSTHALF_FAMILY"
assert panel["eligible_count"] == panel["selected_count"] == 1711
paths = {
    "panel": HERE / "panel.json",
    "targets": HERE / "targets.txt",
    "exact_input": HERE / "exact_input.txt",
    "producer": HERE / "make_full_sage.py",
    "runtime": HERE / "sage_runtime_info.json",
    "source": HERE / "exact_full.cpp",
    "binary": HERE / "exact_full_native",
    "helper": ROOT / "experiments/koblitz-s5-invariant-20260924/three_pair_s7_native.cpp",
    "public_fixture": HERE.parent / "n41_transport_cubic_s8_20261011/fixture.json",
    "prior_sample": HERE.parent / "n41_target_derived_join_panel_20261011/panel.json",
    "prior_exact": HERE.parent / "n41_target_derived_join_panel_20261011/exact_receipt.json",
}
out = {"status": "FROZEN_FULL_N41_FIRSTHALF_EXACT_CENSUS",
       "candidate_id": None,
       "utc": datetime.now(timezone.utc).isoformat(),
       "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
       "platform": platform.platform(), "machine": platform.machine(),
       "compiler": subprocess.check_output(["clang++", "--version"], text=True).splitlines()[0],
       "compile_flags": ["-std=c++17", "-O3", "-Wall", "-Wextra"],
       "sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                  for name, path in paths.items()},
       "limits": {"workers": 1, "total_seconds": 600, "rss_bytes": 4*1024**3},
       "input_law": "all 1711 eligible distinct trace-zero V=U-A-B plus known positive"}
path = HERE / "protocol.json"
if path.exists():
    raise SystemExit("protocol exists")
path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(out["status"], hashlib.sha256(path.read_bytes()).hexdigest())
