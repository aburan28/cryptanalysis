#!/usr/bin/env python3
"""Screen exact adjacent-window pair keys for reusable precomputed sums."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys

import model


HERE = Path(__file__).resolve().parent
TRAIN = HERE.parent / "prime-j0-mixed-radix640-20261010/fresh-inputs.json"
FRESH = HERE / "selective-holdout.json"
BUDGETS = (256, 1024, 4096, 8192, 16384)


def keys_for_scalar(value: str, atlases) -> tuple[tuple, int]:
    a, b = model.mixed.screen.representative(
        int(value, 16) % model.mixed.screen.ORDER)
    choices = []
    for index, radix in enumerate(model.mixed.RADICES):
        label = "512" if index < 6 else "391" if index == 13 else "640"
        digit, seed_id, exponent, unit = atlases[label][0].decode(a, b)
        choices.append((seed_id, exponent, unit))
        a, b = (a - digit[0]) // radix, (b - digit[1]) // radix
    assert (a, b) == (0, 0)
    keys = tuple((index, choices[index], choices[index + 1])
                 for index in range(0, len(choices), 2)
                 if choices[index][0] and choices[index + 1][0])
    return keys, sum(choice[0] == 0 for choice in choices)


def screen() -> dict:
    train_bytes = TRAIN.read_bytes()
    fresh_bytes = FRESH.read_bytes()
    scalars = json.loads(train_bytes)["scalars_hex"]
    fresh = [case["scalar_hex"] for case in json.loads(fresh_bytes)["cases"]]
    atlases = model.atlas_records()
    train_keys = [keys_for_scalar(value, atlases) for value in scalars]
    fresh_keys = [keys_for_scalar(value, atlases) for value in fresh]
    half = len(train_keys) // 2
    calibration = Counter(key for keys, _ in train_keys[:half] for key in keys)
    validation = [key for keys, _ in train_keys[half:] for key in keys]
    holdout = [key for keys, _ in fresh_keys for key in keys]
    result = {
        "schema": 1,
        "method": "cache full selected (seed, tau exponent, unit) pair per fixed adjacent window pair",
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "training_sha256": sha256(train_bytes).hexdigest(),
        "fresh_fixture_sha256": sha256(fresh_bytes).hexdigest(),
        "atlas_sha256": {name: record[1]["sha256"]
                         for name, record in atlases.items()},
        "calibration_scalars": half,
        "internal_validation_scalars": len(train_keys) - half,
        "fresh_validation_scalars": len(fresh_keys),
        "calibration_unique_pairs": len(calibration),
        "internal_validation_pair_slots": len(validation),
        "fresh_validation_pair_slots": len(holdout),
        "zero_seed_windows": {
            "calibration": sum(count for _, count in train_keys[:half]),
            "internal_validation": sum(count for _, count in train_keys[half:]),
            "fresh_validation": sum(count for _, count in fresh_keys),
        },
        "budgets": [],
    }
    for budget in BUDGETS:
        cached = {key for key, _ in calibration.most_common(budget)}
        result["budgets"].append({
            "entries": min(budget, len(calibration)),
            "internal_validation_hits": sum(key in cached for key in validation),
            "fresh_validation_hits": sum(key in cached for key in holdout),
        })
    return result


if __name__ == "__main__":
    result = screen()
    path = HERE / "pair-reuse-screen.json"
    if sys.argv[1:] == ["--write"]:
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    elif sys.argv[1:] == []:
        assert json.loads(path.read_text()) == result
    else:
        raise SystemExit("usage: pair_reuse_screen.py [--write]")
    print(json.dumps({k: result[k] for k in (
        "calibration_unique_pairs", "internal_validation_pair_slots",
        "fresh_validation_pair_slots", "zero_seed_windows", "budgets")}, sort_keys=True))
