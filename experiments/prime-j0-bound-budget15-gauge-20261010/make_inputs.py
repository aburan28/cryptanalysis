#!/usr/bin/env python3
"""Draw a disjoint panel after the two-bucket gauge source freeze."""

import hashlib
import json
from pathlib import Path
import random

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
N = int("fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141", 16)
SEED = 20261010157
COUNT = 4096
SOURCES = (
    "prime-j0-radix943-word-20261009/inputs.json",
    "prime-j0-exact-reciprocal-20261010/fresh-inputs.json",
    "prime-j0-certified-voronoi-20261010/fresh-inputs.json",
    "prime-j0-fixed-limb-voronoi-20261010/fresh-inputs.json",
    "prime-j0-hybrid-finalize-20261010/fresh-inputs.json",
    "prime-j0-binary-inverse-20261010/fresh-inputs.json",
    "prime-j0-direct-limb-scalar-20261010/fresh-inputs.json",
    "prime-j0-u256-point-20261010/fresh-inputs.json",
    "prime-j0-u14-gauge-20261010/fresh-inputs.json",
    "prime-j0-arithmetic-atlas-20261010/fresh-inputs.json",
    "prime-j0-formula-atlas-20261010/fresh-inputs.json",
    "prime-j0-sector-digit-20261010/fresh-inputs.json",
    "prime-j0-cache-window-20261010/fresh-inputs.json",
    "prime-j0-radix384-20261010/fresh-inputs.json",
    "prime-j0-radix384-fast-20261010/fresh-inputs.json",
    "prime-j0-tau384-matching-20261010/fresh-inputs.json",
    "prime-j0-tau-expanded-20261010/fresh-inputs.json",
    "prime-j0-orbit-tau-fusion-20261010/fresh-inputs.json",
    "prime-j0-xyzz-orbit-tau-20261010/fresh-inputs.json",
    "prime-j0-frontier17-orbit-xyzz-20261010/fresh-inputs.json",
    "prime-j0-frontier18-orbit-xyzz-20261010/fresh-inputs.json",
    "prime-j0-two-x-orbit-20261010/fresh-inputs.json",
    "prime-j0-tau-bucket-two-x-20261010/fresh-inputs.json",
    "prime-j0-frontier16-xyzz-tau-20261010/fresh-inputs.json",
    "prime-j0-frontier16-compact-affine-20261010/fresh-inputs.json",
    "prime-j0-frontier16-beta-solinas-20261010/fresh-inputs.json",
    "prime-j0-bound-budget15-20261010/fresh-inputs.json",
)


def digest(data):
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
        source_hashes[name] = digest(raw)
        seen.update(int(value, 16) % N for value in json.loads(raw)["scalars_hex"])
    rng = random.Random(SEED)
    values = []
    while len(values) < COUNT:
        value = rng.getrandbits(256)
        residue = value % N
        if residue not in seen:
            values.append(value)
            seen.add(residue)
    record = {
        "schema": 1,
        "seed": SEED,
        "count": COUNT,
        "source_sha256": source_hashes,
        "scalar_sha256": digest(b"".join(v.to_bytes(32, "big") for v in values)),
        "scalars_hex": [f"{v:064x}" for v in values],
    }
    target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(record["scalar_sha256"])


if __name__ == "__main__":
    main()
