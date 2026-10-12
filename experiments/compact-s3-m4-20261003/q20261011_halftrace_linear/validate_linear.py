#!/usr/bin/env python3
"""Compare the linear half-trace and S3 roots with the archived oracle."""

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(STAGE))
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))

from field import Onb  # noqa: E402
from s3_root_oracle import half_trace as original_half_trace  # noqa: E402
from s3_root_oracle import s3_roots as original_roots  # noqa: E402
from s3_root_oracle_linear import half_trace, masks, s3_roots  # noqa: E402


def main():
    rows = []
    for m in (53, 83, 131):
        onb = Onb(m)
        rng = random.Random(1450 + m)
        assert len(masks(m)) == m
        basis = 0
        random_values = 0
        roots = 0
        for bit in range(m):
            value = onb.fromCoords(1 << bit)
            assert half_trace(onb, value) == original_half_trace(onb, value)
            basis += 1
        for _ in range(128):
            value = onb.fromCoords(rng.getrandbits(m))
            assert half_trace(onb, value) == original_half_trace(onb, value)
            random_values += 1
        for _ in range(32):
            a = onb.fromCoords(rng.randrange(1, 1 << m))
            b = onb.fromCoords(rng.randrange(1, 1 << m))
            assert s3_roots(onb, a, b) == original_roots(onb, a, b)
            roots += 1
        rows.append({"degree": m, "basis_images": basis,
                     "random_values": random_values, "s3_root_pairs": roots})
    print(json.dumps({"status": "PASS", "rows": rows}, sort_keys=True))


if __name__ == "__main__":
    main()
