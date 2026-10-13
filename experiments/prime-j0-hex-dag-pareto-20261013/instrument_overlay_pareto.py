#!/usr/bin/env python3
"""Build the Pareto plan with the previously audited Solinas-call counter."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "prime-j0-hex-workdepth-20261013"
sys.path.insert(0, str(PRIOR))
import instrument_overlay as counter  # noqa: E402
import native_overlay_pareto as pareto  # noqa: E402


def prepare(target: Path) -> dict:
    counter.parent = pareto
    record = counter.prepare(target)
    assert record["hex_tree_plan_sha256"] == sha256((HERE / "plans.bin").read_bytes()).hexdigest()
    record["pareto_instrument_wrapper_sha256"] = sha256(Path(__file__).read_bytes()).hexdigest()
    (target / "overlay.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
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
