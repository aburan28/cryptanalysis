#!/usr/bin/env python3
"""Predict tau-entry rotations on the source-frozen hybrid holdout."""

from hashlib import sha256
import json
from pathlib import Path
import sys

import model

HERE = Path(__file__).resolve().parent


def main():
    assert sys.argv[1:] in ([], ["--write"])
    fixture = HERE / "hybrid-holdout.json"
    panel = json.loads(fixture.read_bytes())
    atlases = model.atlas_records()
    total_rotations = 0
    total_join_calls = 0
    nonzero_counts = {}
    for case in panel["cases"]:
        scalar = int(case["scalar_hex"], 16) % model.mixed.screen.ORDER
        a, b = model.mixed.screen.representative(scalar)
        points = 0
        for index, radix in enumerate(model.mixed.RADICES):
            label = "512" if index < 6 else "391" if index == 13 else "640"
            digit, seed_id, exponent, unit_code = atlases[label][0].decode(a, b)
            if seed_id:
                points += 1
                total_rotations += int(exponent == 1 and unit_code // 2 != 0)
            a, b = (a - digit[0]) // radix, (b - digit[1]) // radix
        assert (a, b) == (0, 0)
        nonzero_counts[str(points)] = nonzero_counts.get(str(points), 0) + 1
        total_join_calls += model.tree_calls(points)
    record = {"schema": 1, "status": "integer_recode_operation_model",
              "fixture_sha256": sha256(fixture.read_bytes()).hexdigest(),
              "model_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "cases": len(panel["cases"]), "nonzero_terms": nonzero_counts,
              "predicted_join_calls": total_join_calls,
              "predicted_tau_rotations": total_rotations,
              "point_and_atlas_bytes": 415190 * 160 + 4729980}
    target = HERE / "hybrid-model.json"
    if sys.argv[1:] == ["--write"]:
        target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    else:
        assert json.loads(target.read_bytes()) == record
    print(json.dumps({key: record[key] for key in
                      ("cases", "nonzero_terms", "predicted_join_calls",
                       "predicted_tau_rotations")}, sort_keys=True))


if __name__ == "__main__":
    main()
