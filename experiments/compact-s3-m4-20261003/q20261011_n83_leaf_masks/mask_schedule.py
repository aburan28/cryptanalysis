#!/usr/bin/env python3
"""Generate target-independent leaf-only first-branch polarity masks."""
from __future__ import annotations

import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent


def schedule() -> dict[str, dict]:
    out = {"0": {"seed": None, "flip_ids": []}}
    for phase in range(1, 9):
        seed = 148100 + phase
        rng = random.Random(seed)
        flip_ids = [var for var in range(2, 334) if rng.getrandbits(1)]
        assert 0 < len(flip_ids) < 332
        out[str(phase)] = {"seed": seed, "flip_ids": flip_ids}
    return out


def main() -> None:
    path = HERE / "mask_schedule.json"
    assert not path.exists()
    path.write_text(json.dumps(schedule(), indent=2, sort_keys=True) + "\n")
    print("Q1481 masks", [len(v["flip_ids"]) for v in schedule().values()])


if __name__ == "__main__":
    main()
