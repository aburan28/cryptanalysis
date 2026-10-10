#!/usr/bin/env python3
"""Replay the exact redundant W24 x/z field identity on frozen masks."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIELD = ROOT / "experiments/ecc2k130-263-native-w24-m6-20261010/field.py"
sys.path.insert(0, str(FIELD.parent))
import field as ref  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    source_path = HERE / "source.json"
    masks_path = HERE / "runs/R1/masks.json"
    source = json.loads(source_path.read_text())
    masks = json.loads(masks_path.read_text())
    field_key = str(FIELD.relative_to(ROOT))
    if (source["pins"][field_key] != sha(FIELD)
            or masks["source_sha256"] != sha(source_path)
            or len(masks["masks"]) != 8):
        raise ValueError("frozen field source or mask panel differs")
    checked = []
    for row in masks["masks"]:
        for policy in source["policies"]:
            alpha, _ = ref.coefficients(policy)
            value = row["curves"][policy]
            x, z, u, w = (value[name] for name in ("x", "z", "u", "w"))
            if (ref.multiply(w, z) != 1
                    or ref.multiply(u, x ^ alpha) != alpha
                    or ref.multiply(alpha, ref.multiply(x, z))
                    != ref.square(x ^ alpha)):
                raise ArithmeticError("W24 field identity failed")
            checked.append({"policy": policy, "mask": row["mask"],
                            "alpha_x_z_equals_x_plus_alpha_squared": True})
    result = {
        "schema": "ecc2k130-263-selector-cut-identity-v1",
        "status": "PASS_16_FROZEN_CURVE_MASK_PAIRS",
        "identity": "alpha*x*z=(x+alpha)^2",
        "source_sha256": sha(source_path),
        "masks_sha256": sha(masks_path),
        "field_source_sha256": sha(FIELD),
        "check_source_sha256": sha(Path(__file__)),
        "rows": checked,
    }
    data = json.dumps(result, sort_keys=True, indent=2) + "\n"
    path = HERE / "runs/R1/identity.json"
    if args.write:
        if path.exists() and path.read_text() != data:
            raise ValueError("existing identity receipt differs")
        if not path.exists():
            path.write_text(data)
    print(json.dumps({"status": result["status"],
                      "checked_pairs": len(checked)}, sort_keys=True))


if __name__ == "__main__":
    main()
