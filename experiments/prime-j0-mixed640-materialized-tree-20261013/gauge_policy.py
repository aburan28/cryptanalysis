#!/usr/bin/env python3
"""Freeze window/exponent gauges using only the prior 4,096-scalar panel."""

from hashlib import sha256
import json
from pathlib import Path
import sys

import model

HERE = Path(__file__).resolve().parent
TRAIN = HERE.parent / "prime-j0-mixed-radix640-20261010/fresh-inputs.json"


def frequencies(scalars, atlases):
    counts = [[[0, 0, 0] for _ in range(2)] for _ in model.mixed.RADICES]
    for scalar_hex in scalars:
        scalar = int(scalar_hex, 16) % model.mixed.screen.ORDER
        a, b = model.mixed.screen.representative(scalar)
        for index, radix in enumerate(model.mixed.RADICES):
            label = "512" if index < 6 else "391" if index == 13 else "640"
            digit, seed_id, exponent, unit = atlases[label][0].decode(a, b)
            if seed_id:
                counts[index][exponent][unit // 2] += 1
            a, b = (a - digit[0]) // radix, (b - digit[1]) // radix
        assert (a, b) == (0, 0)
    return counts


def policy():
    source = json.loads(TRAIN.read_bytes())["scalars_hex"]
    atlases = model.atlas_records()
    counts = frequencies(source, atlases)
    gauges = [[max(range(3), key=lambda g: (cell[g], -g)) for cell in row]
              for row in counts]
    baseline = sum(sum(cell) - cell[0] for row in counts for cell in row)
    selected = sum(sum(cell) - cell[g] for row, gs in zip(counts, gauges)
                   for cell, g in zip(row, gs))
    return {
        "schema": 1,
        "status": "training_only_window_exponent_gauge",
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "training_sha256": sha256(TRAIN.read_bytes()).hexdigest(),
        "atlas_sha256": {key: val[1]["sha256"] for key, val in atlases.items()},
        "training_cases": len(source),
        "unit_power_counts": counts,
        "gauges": gauges,
        "training_baseline_rotations": baseline,
        "training_gauged_rotations": selected,
    }


def main():
    assert sys.argv[1:] in ([], ["--write"])
    result = policy()
    target = HERE / "gauge-policy.json"
    if sys.argv[1:] == ["--write"]:
        target.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    else:
        assert json.loads(target.read_bytes()) == result
    print(json.dumps({key: result[key] for key in
                      ("training_cases", "gauges", "training_baseline_rotations",
                       "training_gauged_rotations")}, sort_keys=True))


if __name__ == "__main__":
    main()
