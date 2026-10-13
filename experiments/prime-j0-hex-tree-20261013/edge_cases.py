#!/usr/bin/env python3
"""Rebuild seven boundary-scalar point fixtures independently of the native code."""

from __future__ import annotations

import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "prime-j0-axis152-20261012"))
import holdout2 as independent  # noqa: E402


def make() -> bytes:
    values = [0, 1, 2, independent.ORDER - 1, independent.ORDER,
              independent.ORDER + 1, (1 << 256) - 1]
    cases = []
    for index, scalar in enumerate(values):
        point = independent.multiply(scalar % independent.ORDER)
        cases.append({
            "index": index, "scalar_hex": f"{scalar:064x}",
            "base_x_hex": f"{independent.GX:064x}",
            "base_y_hex": f"{independent.GY:064x}",
            "expected_identity": point is None,
            "expected_x_hex": None if point is None else f"{point[0]:064x}",
            "expected_y_hex": None if point is None else f"{point[1]:064x}",
        })
    return (json.dumps({"schema": 1, "curve": "secp256k1", "cases": cases},
                       sort_keys=True, separators=(",", ":")) + "\n").encode()


if __name__ == "__main__":
    assert (HERE / "edges.json").read_bytes() == make()
    print("edge_fixture=7/7")
