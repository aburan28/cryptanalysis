#!/usr/bin/env python3
"""Predict native rotations for the frozen selective-orbit holdout."""

from hashlib import sha256
import json
from pathlib import Path
import sys

import model

HERE = Path(__file__).resolve().parent


def main():
    assert sys.argv[1:] in ([], ["--write"])
    fixture = HERE / "selective-holdout.json"
    cases = json.loads(fixture.read_bytes())["cases"]
    policy_path = HERE / "selective-policy.json"
    policy = json.loads(policy_path.read_bytes())
    compressed = policy["compressed_channels"]
    atlases = model.atlas_records()
    plain_rotations = selective_rotations = hybrid_rotations = tree_calls = 0
    term_counts = {}
    for case in cases:
        scalar = int(case["scalar_hex"], 16) % model.mixed.screen.ORDER
        a, b = model.mixed.screen.representative(scalar)
        terms = 0
        for index, radix in enumerate(model.mixed.RADICES):
            label = "512" if index < 6 else "391" if index == 13 else "640"
            digit, seed_id, exponent, unit = atlases[label][0].decode(a, b)
            if seed_id:
                terms += 1
                rotates = int(unit // 2 != 0)
                plain_rotations += rotates
                selective_rotations += rotates * int(not compressed[index][exponent])
                hybrid_rotations += rotates * int(exponent == 1)
            a, b = (a - digit[0]) // radix, (b - digit[1]) // radix
        assert (a, b) == (0, 0)
        term_counts[str(terms)] = term_counts.get(str(terms), 0) + 1
        tree_calls += model.tree_calls(terms)
    record = {
        "schema": 1,
        "status": "frozen_selective_policy_recode_model",
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "fixture_sha256": sha256(fixture.read_bytes()).hexdigest(),
        "policy_sha256": sha256(policy_path.read_bytes()).hexdigest(),
        "cases": len(cases),
        "nonzero_terms": term_counts,
        "predicted_join_calls": tree_calls,
        "predicted_all_affine_rotations": plain_rotations,
        "predicted_selective_rotations": selective_rotations,
        "predicted_hybrid_rotations": hybrid_rotations,
        "predicted_point_and_atlas_bytes": policy["point_and_atlas_bytes"],
    }
    target = HERE / "selective-test-model.json"
    if sys.argv[1:] == ["--write"]:
        target.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    else:
        assert json.loads(target.read_bytes()) == record
    print(json.dumps({name: record[name] for name in
                      ("cases", "predicted_join_calls",
                       "predicted_all_affine_rotations",
                       "predicted_selective_rotations",
                       "predicted_hybrid_rotations")}, sort_keys=True))


if __name__ == "__main__":
    main()
