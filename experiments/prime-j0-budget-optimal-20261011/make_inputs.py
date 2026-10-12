#!/usr/bin/env python3
"""Freeze a scalar panel disjoint from all preceding j=0 panels."""

from hashlib import sha256
import argparse
import importlib.util
import json
from pathlib import Path
import random
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PRIOR = HERE.parent / "prime-j0-phase-optimal-20261011/make_inputs.py"
SPEC = importlib.util.spec_from_file_location("tau_bound_prior_inputs", PRIOR)
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
ORDER = prior.ORDER
COUNT = 4096
SEED = 20261011191000
SOURCES = (*prior.SOURCES,
           "prime-j0-phase-optimal-20261011/holdout-inputs.json",
           "prime-j0-budget-optimal-20261011/preflight-inputs.json")
SOURCE_FILES = ("construct.py", "verify.py", "make_inputs.py",
                "replay_holdout.py", "verify_holdout.py",
                "build_native_atlas.py", "verify_native_atlas.py",
                "phase_cost.py", "materialize_native.py")


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-commit", required=True)
    parser.add_argument("--prior-root", type=Path, action="append", default=[],
                        help="additional experiments root for sparse checkouts")
    args = parser.parse_args()
    output = HERE / "holdout-inputs.json"
    if output.exists():
        raise SystemExit("holdout input file already exists")
    exact = json.loads((HERE / "check.json").read_bytes())
    assert exact["status"] == "passed"
    cover = (HERE / "cover-budget-optimal.bin").read_bytes()
    assert digest(cover) == exact["cover_sha256"]
    seen = set()
    sources = {}
    roots = [ROOT / "experiments", *args.prior_root]
    for name in SOURCES:
        path = next((root / name for root in roots if (root / name).is_file()), None)
        raw = (path.read_bytes() if path is not None else
               subprocess.check_output(
                   ["git", "show", f"{args.frozen_commit}:experiments/{name}"],
                   cwd=ROOT))
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
               "cover_sha256": digest(cover),
               "prior_panel_sha256": sources,
               "scalar_sha256": digest(b"".join(
                   value.to_bytes(32, "big") for value in values)),
               "scalars_hex": [f"{value:064x}" for value in values]}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("seed", "count", "frozen_commit", "cover_sha256",
                       "scalar_sha256")}, sort_keys=True))


if __name__ == "__main__":
    main()
