#!/usr/bin/env python3
"""Freeze a scalar panel disjoint from earlier prime-j0 cover panels."""

from hashlib import sha256
import argparse
import importlib.util
import json
from pathlib import Path
import random


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PRIOR = HERE.parent / "prime-j0-carry-aware-v2-20261011/make_inputs.py"
SPEC = importlib.util.spec_from_file_location("orbit_swap_prior_inputs", PRIOR)
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
ORDER = prior.ORDER
COUNT = 4096
SEED = 20261011234517
SOURCES = (*prior.SOURCES,
           "prime-j0-direct-rho-20261011/fresh-inputs.json",
           "prime-j0-carry-aware-v2-20261011/holdout-inputs.json")
SOURCE_FILES = ("optimize.py", "verify_cover.py", "make_inputs.py",
                "replay_holdout.py", "verify_holdout.py")


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-commit", required=True)
    args = parser.parse_args()
    output = HERE / "holdout-inputs.json"
    if output.exists():
        raise SystemExit("holdout input file already exists")
    check = json.loads((HERE / "cover-check.json").read_bytes())
    assert check["status"] == "passed"
    cover_raw = (HERE / "cover-swapped-rho0.bin").read_bytes()
    assert digest(cover_raw) == check["cover_sha256"]
    seen = set()
    sources = {}
    for name in SOURCES:
        raw = (ROOT / "experiments" / name).read_bytes()
        sources[name] = digest(raw)
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
               "frozen_commit": args.frozen_commit,
               "candidate_source_sha256": {name: digest((HERE / name).read_bytes())
                                           for name in SOURCE_FILES},
               "cover_sha256": digest(cover_raw),
               "prior_panel_sha256": sources,
               "scalar_sha256": digest(b"".join(
                   value.to_bytes(32, "big") for value in values)),
               "scalars_hex": [f"{value:064x}" for value in values]}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: receipt[k] for k in
                      ("seed", "count", "frozen_commit", "cover_sha256",
                       "scalar_sha256")}, sort_keys=True))


if __name__ == "__main__":
    main()
