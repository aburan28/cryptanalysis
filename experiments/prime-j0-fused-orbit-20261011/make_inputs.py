#!/usr/bin/env python3
"""Draw a new disjoint panel after the fused atlas construction freeze."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import random


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PARENT = HERE.parent / "prime-j0-adic-orbit-20261011/make_inputs.py"
SPEC = importlib.util.spec_from_file_location("prior_fused_panel_law", PARENT)
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
ORDER = prior.ORDER
SEED = 20261011032514
COUNT = 4096
CONSTRUCTION_COMMIT = "bc11e30258dae55ba9120d15193994a2ecfa9b60"
SOURCES = (*prior.SOURCES,
           "prime-j0-adic-orbit-20261011/fresh-inputs.json")


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    output = HERE / "fresh-inputs.json"
    if output.exists():
        raise SystemExit("fresh input file already exists")
    seen = set()
    source_hashes = {}
    for name in SOURCES:
        raw = (ROOT / "experiments" / name).read_bytes()
        source_hashes[name] = digest(raw)
        seen.update(int(value, 16) % ORDER
                    for value in json.loads(raw)["scalars_hex"])
    rng = random.Random(SEED)
    values = []
    while len(values) < COUNT:
        value = rng.getrandbits(256)
        reduced = value % ORDER
        if reduced in seen:
            continue
        values.append(value)
        seen.add(reduced)
    receipt = {"schema": 1, "seed": SEED, "count": COUNT,
               "construction_commit": CONSTRUCTION_COMMIT,
               "source_sha256": source_hashes,
               "scalar_sha256": digest(b"".join(
                   value.to_bytes(32, "big") for value in values)),
               "scalars_hex": [f"{value:064x}" for value in values]}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(receipt["scalar_sha256"])


if __name__ == "__main__":
    main()
