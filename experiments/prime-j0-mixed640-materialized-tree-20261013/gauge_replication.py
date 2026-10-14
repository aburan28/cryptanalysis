#!/usr/bin/env python3
"""Estimate fixed-policy rotation yield on 65,536 new uniform scalars."""

from hashlib import sha256
import json
import math
from pathlib import Path
import random
import sys

import model

HERE = Path(__file__).resolve().parent
FREEZE = "f05eb12cd4d490a4aaa1c60b1d3ad96d95c73814"
CASES = 65_536


def main():
    assert sys.argv[1:] in ([], ["--write"])
    policy_path = HERE / "gauge-policy.json"
    gauges = json.loads(policy_path.read_bytes())["gauges"]
    fixture_names = ("holdout.json", "hybrid-holdout.json",
                     "affine-holdout.json", "gauge-holdout.json")
    prior = set()
    for name in fixture_names:
        prior.update(int(case["scalar_hex"], 16) % model.mixed.screen.ORDER
                     for case in json.loads((HERE / name).read_bytes())["cases"])
    training = HERE.parent / "prime-j0-mixed-radix640-20261010/fresh-inputs.json"
    prior.update(int(x, 16) % model.mixed.screen.ORDER
                 for x in json.loads(training.read_bytes())["scalars_hex"])
    seed = int.from_bytes(sha256((FREEZE + ":gauge-replication-v1").encode()).digest(), "big")
    rng = random.Random(seed)
    atlases = model.atlas_records()
    stream_hash = sha256()
    plain_rotations = gauged_rotations = 0
    savings_sum = savings_square_sum = 0
    seen = set()
    while len(seen) < CASES:
        scalar = rng.getrandbits(256)
        residue = scalar % model.mixed.screen.ORDER
        if residue in prior or residue in seen:
            continue
        seen.add(residue)
        stream_hash.update(scalar.to_bytes(32, "big"))
        a, b = model.mixed.screen.representative(residue)
        plain = gauged = 0
        for index, radix in enumerate(model.mixed.RADICES):
            label = "512" if index < 6 else "391" if index == 13 else "640"
            digit, seed_id, exponent, unit = atlases[label][0].decode(a, b)
            if seed_id:
                power = unit // 2
                plain += int(power != 0)
                gauged += int(power != gauges[index][exponent])
            a, b = (a - digit[0]) // radix, (b - digit[1]) // radix
        assert (a, b) == (0, 0)
        plain_rotations += plain
        gauged_rotations += gauged
        delta = plain - gauged
        savings_sum += delta
        savings_square_sum += delta * delta
    mean = savings_sum / CASES
    variance = (savings_square_sum - CASES * mean * mean) / (CASES - 1)
    se = math.sqrt(variance / CASES)
    record = {
        "schema": 1,
        "status": "model_only_fixed_policy_replication",
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "policy_sha256": sha256(policy_path.read_bytes()).hexdigest(),
        "source_freeze_commit": FREEZE,
        "case_count": CASES,
        "input_law": "Python MT19937 getrandbits(256), reject prior and duplicate subgroup residues",
        "seed_hex": f"{seed:064x}",
        "scalar_stream_sha256": stream_hash.hexdigest(),
        "prior_fixture_sha256": {
            name: sha256((HERE / name).read_bytes()).hexdigest()
            for name in fixture_names
        },
        "training_sha256": sha256(training.read_bytes()).hexdigest(),
        "plain_rotations": plain_rotations,
        "gauged_rotations": gauged_rotations,
        "rotation_savings": savings_sum,
        "mean_savings_per_scalar": mean,
        "standard_error_per_scalar": se,
        "normal_95_interval_per_scalar": [mean - 1.96 * se, mean + 1.96 * se],
        "native_verified_cases": 0,
    }
    target = HERE / "gauge-replication.json"
    if sys.argv[1:] == ["--write"]:
        target.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    else:
        assert json.loads(target.read_bytes()) == record
    print(json.dumps({key: record[key] for key in
                      ("case_count", "plain_rotations", "gauged_rotations",
                       "rotation_savings", "normal_95_interval_per_scalar")}, sort_keys=True))


if __name__ == "__main__":
    main()
