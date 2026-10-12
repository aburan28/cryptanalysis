#!/usr/bin/env python3
"""Freeze a new scalar panel disjoint from all prior listed j=0 panels."""

from hashlib import sha256
import argparse
import importlib.util
import json
from pathlib import Path
import random
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PARENT = HERE / "prune.py"
SPEC = importlib.util.spec_from_file_location("cycle_inputs_parent", PARENT)
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
ORDER = parent.dual.screen.ORDER
COUNT = 4096
SEED = 20261011090617
SOURCE_FILES = ("prune.py", "exchange.py", "refine.py", "verify_exchange.py",
                "verify_cover.py", "make_inputs.py", "replay_holdout.py",
                "verify_holdout.py", "phase_cost.py")


def digest(raw):
    return sha256(raw).hexdigest()


def prior_bytes(name):
    path = ROOT / "experiments" / name
    if path.is_file():
        return path.read_bytes()
    return subprocess.run(["git", "show", f"HEAD:experiments/{name}"],
                          cwd=ROOT, check=True, capture_output=True).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-commit", required=True)
    args = parser.parse_args()
    output = HERE / "holdout-inputs.json"
    if output.exists():
        raise SystemExit("holdout input file already exists")
    cover = (HERE / "cover-cycle-refined.bin").read_bytes()
    check = json.loads((HERE / "cover-check.json").read_bytes())
    assert check["status"] == "passed"
    assert digest(cover) == check["covers"][-1]["cover_sha256"]
    parent_raw = prior_bytes("prime-j0-tau-bound-20261011/holdout-inputs.json")
    parent = json.loads(parent_raw)
    sources = dict(parent["prior_panel_sha256"])
    sources["prime-j0-tau-bound-20261011/holdout-inputs.json"] = digest(parent_raw)
    seen = set()
    for name, expected in sorted(sources.items()):
        raw = prior_bytes(name)
        assert digest(raw) == expected, name
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
               "candidate_source_sha256": {
                   name: digest((HERE / name).read_bytes())
                   for name in SOURCE_FILES},
               "cover_sha256": digest(cover),
               "prior_panel_sha256": dict(sorted(sources.items())),
               "scalar_sha256": digest(b"".join(
                   value.to_bytes(32, "big") for value in values)),
               "scalars_hex": [f"{value:064x}" for value in values]}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("seed", "count", "frozen_commit", "cover_sha256",
                       "scalar_sha256")}, sort_keys=True))


if __name__ == "__main__":
    main()
