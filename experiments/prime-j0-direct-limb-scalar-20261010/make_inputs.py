#!/usr/bin/env python3
"""Freeze disjoint unsigned 256-bit scalar inputs after the protocol commit."""

import hashlib
import json
from pathlib import Path
import random

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
N = int("fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141", 16)
SEED = 20261010625
COUNT = 4096
SOURCES = (
    "prime-j0-radix943-word-20261009/inputs.json",
    "prime-j0-exact-reciprocal-20261010/fresh-inputs.json",
    "prime-j0-certified-voronoi-20261010/fresh-inputs.json",
    "prime-j0-fixed-limb-voronoi-20261010/fresh-inputs.json",
    "prime-j0-hybrid-finalize-20261010/fresh-inputs.json",
    "prime-j0-binary-inverse-20261010/fresh-inputs.json",
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    target = HERE / "fresh-inputs.json"
    if target.exists():
        raise SystemExit("fresh input file already exists")
    seen = set()
    source_hashes = {}
    for name in SOURCES:
        path = ROOT / "experiments" / name
        raw = path.read_bytes()
        source_hashes[name] = sha(raw)
        seen.update(int(value, 16) % N for value in json.loads(raw)["scalars_hex"])
    rng = random.Random(SEED)
    values = []
    while len(values) < COUNT:
        value = rng.getrandbits(256)
        if value % N not in seen:
            values.append(value)
            seen.add(value % N)
    record = {
        "schema": 1, "seed": SEED, "count": COUNT,
        "source_sha256": source_hashes,
        "scalar_sha256": sha(b"".join(value.to_bytes(32, "big") for value in values)),
        "scalars_hex": [f"{value:064x}" for value in values],
    }
    target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(record["scalar_sha256"])


if __name__ == "__main__":
    main()
