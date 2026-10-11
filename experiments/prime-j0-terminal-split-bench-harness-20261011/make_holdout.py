#!/usr/bin/env python3
"""Freeze fresh secp256k1 scalars and independently computed points."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import random
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "experiments/prime-j0-secp256k1-native"))
import lazy_tau_screen as curve

SEED = 20261011213935
COUNT = 9
PRIOR = REPO / "experiments/prime-j0-terminal-split-20261011/holdout-inputs.json"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-commit", required=True)
    args = parser.parse_args()
    output = HERE / "prospective-fixture.json"
    if output.exists():
        raise SystemExit("refusing to overwrite frozen fixture")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    if head != args.frozen_commit:
        raise SystemExit("candidate source must be at the declared frozen commit")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO):
        raise SystemExit("commit all candidate source before drawing scalars")
    prior = json.loads(PRIOR.read_text())
    seen = {int(value, 16) % curve.ORDER for value in prior["scalars_hex"]}
    rng = random.Random(SEED)
    cases = []
    while len(cases) < COUNT:
        scalar = rng.getrandbits(256)
        reduced = scalar % curve.ORDER
        if reduced == 0 or reduced in seen:
            continue
        seen.add(reduced)
        point = curve.point_multiply(reduced)
        assert point is not None
        cases.append({"index": len(cases), "scalar_hex": f"{scalar:064x}",
                      "base_x_hex": f"{curve.GENERATOR[0]:064x}",
                      "base_y_hex": f"{curve.GENERATOR[1]:064x}",
                      "expected_identity": False,
                      "expected_x_hex": f"{point[0]:064x}",
                      "expected_y_hex": f"{point[1]:064x}"})
    receipt = {"schema": 1, "curve": "secp256k1", "kind": "prospective-terminal-split",
               "input_law": "nine 256-bit uniform pseudorandom scalars from frozen seed; disjoint modulo group order from 4096-scalar development panel",
               "seed": SEED, "frozen_commit": head, "prior_sha256": digest(PRIOR),
               "point_reference_sha256": digest(REPO / "experiments/prime-j0-secp256k1-native/lazy_tau_screen.py"),
               "generator_sha256": digest(Path(__file__)), "cases": cases}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases), "fixture_sha256": digest(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
