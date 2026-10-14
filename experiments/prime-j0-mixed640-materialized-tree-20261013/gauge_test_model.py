#!/usr/bin/env python3
"""Predict fixed-gauge operations on the post-freeze holdout."""

from hashlib import sha256
import json
from pathlib import Path
import sys

import model

HERE = Path(__file__).resolve().parent


def main():
    assert sys.argv[1:] in ([], ["--write"])
    fixture = HERE / "gauge-holdout.json"
    panel = json.loads(fixture.read_bytes())
    policy_path = HERE / "gauge-policy.json"
    gauges = json.loads(policy_path.read_bytes())["gauges"]
    atlases = model.atlas_records()
    old_rotations = 0
    gauged_rotations = 0
    tree_calls = 0
    nonzero_counts = {}
    for case in panel["cases"]:
        scalar = int(case["scalar_hex"], 16) % model.mixed.screen.ORDER
        a, b = model.mixed.screen.representative(scalar)
        points = 0
        for index, radix in enumerate(model.mixed.RADICES):
            label = "512" if index < 6 else "391" if index == 13 else "640"
            digit, seed_id, exponent, unit = atlases[label][0].decode(a, b)
            if seed_id:
                points += 1
                power = unit // 2
                old_rotations += int(power != 0)
                gauged_rotations += int(power != gauges[index][exponent])
            a, b = (a - digit[0]) // radix, (b - digit[1]) // radix
        assert (a, b) == (0, 0)
        nonzero_counts[str(points)] = nonzero_counts.get(str(points), 0) + 1
        tree_calls += model.tree_calls(points)
    record = {
        "schema": 1,
        "status": "fixed_policy_integer_recode_model",
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "fixture_sha256": sha256(fixture.read_bytes()).hexdigest(),
        "policy_sha256": sha256(policy_path.read_bytes()).hexdigest(),
        "cases": len(panel["cases"]),
        "nonzero_terms": nonzero_counts,
        "predicted_join_calls": tree_calls,
        "predicted_plain_rotations": old_rotations,
        "predicted_gauged_rotations": gauged_rotations,
    }
    target = HERE / "gauge-test-model.json"
    if sys.argv[1:] == ["--write"]:
        target.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    else:
        assert json.loads(target.read_bytes()) == record
    print(json.dumps({key: record[key] for key in
                      ("cases", "predicted_join_calls", "predicted_plain_rotations",
                       "predicted_gauged_rotations")}, sort_keys=True))


if __name__ == "__main__":
    main()
