#!/usr/bin/env python3
"""The four first-branch polarities of the exact N83 preimage selectors."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORDER = HERE.parent / "q20261011_wdsat_order/order_manifest.json"
INDICES = tuple(range(4))


def phases() -> dict[int, dict]:
    source = json.loads(ORDER.read_text())["cells"]["n83"]
    selectors = source["selector_priority"]
    assert len(selectors) == 2 and len(set(selectors)) == 2
    assert all(1 <= x <= source["original_variables"] for x in selectors)
    return {index: {"seed": None,
                    "flip_ids": [selectors[bit] for bit in range(2)
                                 if index & (1 << bit)]}
            for index in INDICES}
