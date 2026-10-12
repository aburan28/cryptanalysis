#!/usr/bin/env python3
"""Freeze scalar inputs for the radix-943 signed-limb comparison."""

import hashlib
import json
from pathlib import Path
import random


ORDER = int("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141", 16)
SEED = 20261009413
RANDOM_CASES = 512


def main():
    rng = random.Random(SEED)
    scalars = [0, 1, 2, ORDER - 2, ORDER - 1, ORDER, ORDER + 1]
    scalars.extend(rng.getrandbits(256) % ORDER for _ in range(RANDOM_CASES))
    encoded = [f"{value:064x}" for value in scalars]
    digest = hashlib.sha256(b"".join(value.to_bytes(32, "big") for value in scalars)).hexdigest()
    result = {
        "schema": 1,
        "order_hex": f"{ORDER:064x}",
        "seed": SEED,
        "boundary_cases": 7,
        "random_cases": RANDOM_CASES,
        "scalar_sha256": digest,
        "scalars_hex": encoded,
    }
    output = Path(__file__).with_name("inputs.json")
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(scalars), "scalar_sha256": digest}, sort_keys=True))


if __name__ == "__main__":
    main()
