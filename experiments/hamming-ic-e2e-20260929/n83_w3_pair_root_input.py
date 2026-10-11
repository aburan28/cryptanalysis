#!/usr/bin/env python3
"""Freeze exact N83 W3 projected representative x codes for a root-kernel probe."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "runs/n83_w3_geometry_v2/representatives.json"
SOURCE_SHA256 = "b399c2a1ea4dcc3d27a5feec7ceb18f772560a0e7ddecc8904857fb5e0f1f5cd"
CURVE_ID = "EC1N83Ckb1h2bcb59d56ad6"


def main(out):
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == SOURCE_SHA256
    archived = json.loads(SOURCE.read_text())
    assert archived["curve_id"] == CURVE_ID
    points = [tuple(pair) for pair in archived["representatives"]]
    assert len(points) == len(set(points)) == 539
    x_codes = [point[0] for point in points]
    assert len(set(x_codes)) == len(x_codes)
    assert all(0 < x < (1 << 83) for x in x_codes)
    record = {
        "schema_version": 1,
        "kind": "n83_w3_pair_root_input",
        "curve_id": CURVE_ID,
        "field_degree": 83,
        "field_polynomial_low_terms": [0, 2, 4, 7],
        "curve_b": 1,
        "source_representatives_sha256": SOURCE_SHA256,
        "representative_count": len(points),
        "representatives_xy_decimal": [[str(x), str(y)] for x, y in points],
    }
    out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: n83_w3_pair_root_input.py output.json")
    main(Path(sys.argv[1]))
