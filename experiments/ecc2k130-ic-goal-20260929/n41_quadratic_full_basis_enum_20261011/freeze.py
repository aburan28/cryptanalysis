"""Freeze the root-and-residual halftrace-basis enumerator comparison."""

import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
inputs = {
    "source": HERE / "full_basis_compare.cpp",
    "binary": HERE / "full_basis_compare_native",
    "runner": HERE / "run.py",
    "helper": ROOT / "experiments/koblitz-s5-invariant-20260924/three_pair_s7_native.cpp",
    "targets": HERE / "targets.txt",
    "prior_receipt": HERE.parent / "n41_direct_relaxed_pair_join_20261011/receipt.json",
    "prior_quadratic_receipt": HERE.parent / "n41_quadratic_pair_enum_20261011/receipt.json",
    "prior_quadratic_source": HERE.parent / "n41_quadratic_pair_enum_20261011/quadratic_compare.cpp",
    "prior_basis_receipt": HERE.parent / "n41_quadratic_basis_enum_20261011/receipt.json",
}
output = {
    "status": "FROZEN_BEFORE_FULL_HALFTRACE_BASIS_COMPARISON",
    "utc": datetime.now(timezone.utc).isoformat(),
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "platform": platform.platform(),
    "machine": platform.machine(),
    "compiler": subprocess.check_output(["clang++", "--version"], text=True).splitlines()[0],
    "compile_flags": ["-std=c++17", "-O3", "-Wall", "-Wextra"],
    "sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
               for name, path in inputs.items()},
    "limits": {"workers": 1, "wall_seconds": 120, "rss_bytes": 4294967296},
    "comparison": "complete equality of all unrotated relaxed curve points; repeat nine frozen group queries; count root and residual halftrace calls avoided",
}
path = HERE / "protocol.json"
if path.exists():
    raise SystemExit("protocol already exists")
path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
print(output["status"], hashlib.sha256(path.read_bytes()).hexdigest())
