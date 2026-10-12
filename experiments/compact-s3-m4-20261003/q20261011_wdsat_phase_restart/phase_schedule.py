#!/usr/bin/env python3
"""Source-bound branch-polarity schedule for one N83 ordinary target."""
from __future__ import annotations

import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ORDER = PARENT / "q20261011_wdsat_order/order_manifest.json"
INDICES = tuple(range(9))


def phases() -> dict[int, dict]:
    source = json.loads(ORDER.read_text())["cells"]["n83"]
    eligible = sorted(set(source["selector_priority"] +
                          source["pair_mid_first_ids"] +
                          source["interleaved_leaves_priority"]))
    assert len(eligible) == (2 + 2 * 83 + 4 * 83)
    assert all(1 <= value <= source["original_variables"] for value in eligible)
    output = {0: {"seed": None, "flip_ids": []}}
    for index in INDICES[1:]:
        seed = 14720900 + index
        rng = random.Random(seed)
        flip_ids = [variable for variable in eligible if rng.getrandbits(1)]
        assert 0 < len(flip_ids) < len(eligible)
        output[index] = {"seed": seed, "flip_ids": flip_ids}
    return output
