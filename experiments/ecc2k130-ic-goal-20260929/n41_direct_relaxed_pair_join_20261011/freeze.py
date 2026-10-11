"""Freeze the executable, inputs, and resource contract before the run."""

import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


paths = {
    "source": HERE / "direct_join.cpp",
    "helper": ROOT / "experiments/koblitz-s5-invariant-20260924/three_pair_s7_native.cpp",
    "binary": HERE / "direct_join_native",
    "targets": HERE / "targets.txt",
    "input_manifest": HERE / "input_manifest.json",
    "producer": HERE / "make_input.py",
}
receipt = {
    "status": "FROZEN_BEFORE_NATIVE_RUN",
    "utc": datetime.now(timezone.utc).isoformat(),
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "platform": platform.platform(),
    "machine": platform.machine(),
    "compiler": subprocess.check_output(["clang++", "--version"], text=True).splitlines()[0],
    "compile_command": "clang++ -std=c++17 -O3 -Wall -Wextra direct_join.cpp -o direct_join_native",
    "sha256": {name: sha(path) for name, path in paths.items()},
    "workload": "one frozen positive and eight N41 target-derived right-middle points",
    "limits": {"workers": 1, "setup_seconds": 120, "online_seconds_per_query": 120, "rss_bytes": 4294967296},
    "accounting": "setup is target independent; each query starts before its first group subtraction and includes every probe and exact replay",
}
out = HERE / "protocol.json"
if out.exists():
    raise SystemExit("protocol.json already exists")
out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
print("FROZEN_BEFORE_NATIVE_RUN", sha(out))
