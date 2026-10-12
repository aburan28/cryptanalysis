#!/usr/bin/env python3
"""Derive exact Q1469 static branch prefixes from the Q1467 source manifest."""
from __future__ import annotations

import json
from pathlib import Path

PARENT = Path(__file__).resolve().parent.parent
SOURCE = PARENT / "q20261011_wdsat_order/order_manifest.json"
MODES = ("selector_pair_mids", "selector_mid_interleave", "selector_leaf_interleave")


def priorities(degree: int) -> dict[str, list[int]]:
    source = json.loads(SOURCE.read_text())["cells"][f"n{degree}"]
    selector = source["selector_priority"]
    mids = source["pair_mid_first_ids"]
    leaves = source["interleaved_leaves_priority"]
    assert len(mids) == 2 * degree and len(leaves) == 4 * degree
    assert len(set(selector + mids + leaves)) == len(selector + mids + leaves)
    interleaved_mids = [variable for bit in range(degree)
                        for variable in (mids[bit], mids[degree + bit])]
    result = {"selector_pair_mids": selector + mids,
              "selector_mid_interleave": selector + interleaved_mids,
              "selector_leaf_interleave": selector + leaves}
    assert tuple(result) == MODES
    for prefix in result.values():
        assert len(prefix) == len(set(prefix))
        assert all(1 <= value <= source["original_variables"] for value in prefix)
    return result
