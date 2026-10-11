#!/usr/bin/env python3
"""Freeze a new public target with the independent Python affine group law."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
P = 4294967377
B = 15
ORDER = 23729779
BASE = (481899190, 1998487369)
LABEL = "paired2-plane-orbit-identity-single-target-20261007-v2"


def add(left, right):
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2 and (y1 + y2) % P == 0:
        return None
    if left == right:
        slope = 3 * x1 * x1 * pow(2 * y1, -1, P) % P
    else:
        slope = (y2 - y1) * pow((x2 - x1) % P, -1, P) % P
    x3 = (slope * slope - x1 - x2) % P
    return x3, (slope * (x1 - x3) - y1) % P


def multiply(point, scalar):
    result = None
    while scalar:
        if scalar & 1:
            result = add(result, point)
        point = add(point, point)
        scalar >>= 1
    return result


def main():
    path = HERE / "fixture-v2.json"
    if path.exists():
        raise SystemExit("fixture already exists; refusing overwrite")
    previous = [json.loads((HERE.parent / name / "fixture.json").read_text())
                for name in ("prime-j0-paired-rho-startup", "prime-j0-batch-rho-startup",
                             "prime-j0-unit-plane-rho")]
    previous.append(json.loads((HERE / "fixture.json").read_text()))
    scalar = int.from_bytes(hashlib.sha256((LABEL + ":target").encode()).digest(),
                            "big") % ORDER
    seed = int.from_bytes(hashlib.sha256((LABEL + ":rho-seed").encode()).digest()[:8],
                          "big")
    if not scalar or not seed or any(scalar == item["expected_scalar"] for item in previous):
        raise SystemExit("derived an invalid or reused scalar/seed")
    assert (BASE[1] * BASE[1] - BASE[0] ** 3 - B) % P == 0
    assert multiply(BASE, ORDER) is None
    target = multiply(BASE, scalar)
    assert target is not None and all(
        target != (item["target_x"], item["target_y"]) for item in previous)
    assert (target[1] ** 2 - target[0] ** 3 - B) % P == 0
    fixture = {
        "schema": 1, "label": LABEL, "curve": "glv-j0-32",
        "p": P, "b": B, "order": ORDER,
        "base_x": BASE[0], "base_y": BASE[1],
        "target_x": target[0], "target_y": target[1],
        "expected_scalar": scalar, "rho_seed": seed,
        "target_input_law": "one_previously_unseen_public_point",
        "fixture_generation": "sha256_scalar_and_independent_affine_double_and_add",
    }
    path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")
    print(path)


if __name__ == "__main__":
    main()
