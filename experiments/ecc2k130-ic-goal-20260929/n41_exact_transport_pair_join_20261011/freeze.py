"""Bind the exact transported pair join before native execution."""

import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
paths = {
    "source": HERE / "exact_join.cpp",
    "binary": HERE / "exact_join_native",
    "helper": ROOT / "experiments/koblitz-s5-invariant-20260924/three_pair_s7_native.cpp",
    "input": HERE / "input.txt",
    "input_manifest": HERE / "input_manifest.json",
    "producer": HERE / "make_input.py",
    "screen": HERE.parent / "n131_w18_four_pairs/screen.json",
    "fixture": HERE.parent / "n41_two_pair_relaxation_20261011/targets.json",
    "relaxed_receipt": HERE.parent / "n41_direct_relaxed_pair_join_20261011/receipt.json",
}
out = {
    "status": "FROZEN_EXACT_TRANSPORT_N41_PAIR_JOIN",
    "candidate_id": None,
    "utc": datetime.now(timezone.utc).isoformat(),
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "platform": platform.platform(),
    "machine": platform.machine(),
    "compiler": subprocess.check_output(["clang++", "--version"], text=True).splitlines()[0],
    "compile_flags": ["-std=c++17", "-O3", "-Wall", "-Wextra"],
    "sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
               for name, path in paths.items()},
    "limits": {"workers": 1, "setup_seconds": 120,
               "online_seconds_per_query": 120, "rss_bytes": 4*1024**3},
    "input_law": "frozen positive and eight target-derived raw middle points; exact transported W6 rows at rotations 20 and 30",
}
protocol = HERE / "protocol.json"
if protocol.exists():
    raise SystemExit("protocol exists")
protocol.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
print(out["status"], hashlib.sha256(protocol.read_bytes()).hexdigest())
