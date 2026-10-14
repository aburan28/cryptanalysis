#!/usr/bin/env python3
"""Build the frozen native gauge-tree evaluator with low-work plans."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "prime-j0-hex-tree-20261013"
sys.path.insert(0, str(PRIOR))
import native_overlay_tree as parent  # noqa: E402


def prepare(target: Path) -> dict:
    target = target.resolve()
    record = parent.prepare(target)
    plans = target / "plans.bin"
    shutil.copyfile(HERE / "plans.bin", plans)
    record.update({
        "schema": 7,
        "hex_tree_plan_sha256": sha256(plans.read_bytes()).hexdigest(),
        "workdepth_transform_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "workdepth_plan_receipt_sha256": sha256((HERE / "plans.json").read_bytes()).hexdigest(),
    })
    (target / "overlay.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "low_work_overlay_prepared",
                      "plan_sha256": record["hex_tree_plan_sha256"]}, sort_keys=True))
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    prepare(args.target)
    if args.build:
        subprocess.run(["cargo", "build", "--offline", "--locked", "--release",
                        "--bin", "eisenstein_fixed"],
                       cwd=args.target / "experiments/prime-j0-secp256k1-native", check=True)
