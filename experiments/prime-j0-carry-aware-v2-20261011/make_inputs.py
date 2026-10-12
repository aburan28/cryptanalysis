#!/usr/bin/env python3
"""Freeze a scalar panel disjoint from previous priority and direct-rho panels."""

from hashlib import sha256
import argparse
import importlib.util
import json
from pathlib import Path
import random


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PARENT = HERE.parent / "prime-j0-dual-orbit-20261011"
SPEC = importlib.util.spec_from_file_location("carry_prior_inputs",
                                             PARENT / "make_priority_inputs.py")
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
ORDER = prior.ORDER
COUNT = 4096
SEED = 20261011223217
SOURCES = (*prior.SOURCES,
           "prime-j0-dual-orbit-20261011/priority-fresh-inputs.json")


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direct-panel", type=Path, required=True)
    args = parser.parse_args()
    output = HERE / "holdout-inputs.json"
    if output.exists():
        raise SystemExit("holdout input file already exists")
    seen = set()
    sources = {}
    for name in SOURCES:
        raw = (ROOT / "experiments" / name).read_bytes()
        sources[name] = digest(raw)
        seen.update(int(value, 16) % ORDER
                    for value in json.loads(raw)["scalars_hex"])
    direct_raw = args.direct_panel.read_bytes()
    sources["prime-j0-direct-rho-20261011/fresh-inputs.json"] = digest(direct_raw)
    seen.update(int(value, 16) % ORDER
                for value in json.loads(direct_raw)["scalars_hex"])
    rng = random.Random(SEED)
    values = []
    while len(values) < COUNT:
        value = rng.getrandbits(256)
        reduced = value % ORDER
        if reduced in seen:
            continue
        values.append(value)
        seen.add(reduced)
    screen = HERE / "screen.py"
    receipt = {"schema": 1, "seed": SEED, "count": COUNT,
               "candidate_beam_width": 2,
               "candidate_source_sha256": digest(screen.read_bytes()),
               "source_sha256": sources,
               "scalar_sha256": digest(b"".join(
                   value.to_bytes(32, "big") for value in values)),
               "scalars_hex": [f"{value:064x}" for value in values]}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: receipt[k] for k in ("seed", "count",
                        "candidate_beam_width", "candidate_source_sha256",
                        "scalar_sha256")}, sort_keys=True))


if __name__ == "__main__":
    main()
