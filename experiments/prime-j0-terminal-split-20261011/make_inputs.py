#!/usr/bin/env python3
"""Draw an unseen secp256k1 scalar panel after the candidate source freezes."""

import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import random
import subprocess


HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parent
REPO = EXPERIMENTS.parent
PRIOR = EXPERIMENTS / "prime-j0-budget-optimal-20261011/make_inputs.py"
SPEC = importlib.util.spec_from_file_location("terminal_split_prior_inputs", PRIOR)
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
ORDER = prior.ORDER
COUNT = 4096
SEED = 20261011204501
SOURCES = (*prior.SOURCES,
           "prime-j0-budget-optimal-20261011/holdout-inputs.json")
SOURCE_FILES = ("PROTOCOL.md", "replay.py", "verify.py", "make_inputs.py")
COVER = EXPERIMENTS / "prime-j0-budget-optimal-20261011/cover-budget-optimal.bin"
TERMINAL = EXPERIMENTS / "prime-j0-fused-orbit-20261011/atlas-r1024-terminal-fused-orbit.bin"


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-commit", required=True)
    args = parser.parse_args()
    output = HERE / "holdout-inputs.json"
    if output.exists():
        raise SystemExit("refusing to overwrite frozen inputs")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                   text=True).strip()
    if head != args.frozen_commit:
        raise SystemExit("frozen commit must be the current HEAD")
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal"],
                                    cwd=REPO, text=True)
    if dirty:
        raise SystemExit("freeze candidate source in a clean commit before drawing inputs")
    seen = set()
    source_hashes = {}
    for name in SOURCES:
        raw = (EXPERIMENTS / name).read_bytes()
        source_hashes[name] = digest(raw)
        seen.update(int(value, 16) % ORDER for value in json.loads(raw)["scalars_hex"])
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
               "frozen_commit": head,
               "candidate_source_sha256": {
                   name: digest((HERE / name).read_bytes()) for name in SOURCE_FILES},
               "cover_sha256": digest(COVER.read_bytes()),
               "terminal_sha256": digest(TERMINAL.read_bytes()),
               "prior_panel_sha256": source_hashes,
               "scalar_sha256": digest(b"".join(
                   value.to_bytes(32, "big") for value in values)),
               "scalars_hex": [f"{value:064x}" for value in values]}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("seed", "count", "frozen_commit", "cover_sha256",
                       "terminal_sha256", "scalar_sha256")}, sort_keys=True))


if __name__ == "__main__":
    main()
