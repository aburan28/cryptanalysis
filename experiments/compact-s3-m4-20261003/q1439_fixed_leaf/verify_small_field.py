#!/usr/bin/env python3
"""Independent algebraic scope check for Q1439's two S3 links."""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
sys.path.insert(0, str(HERE.parent))
from chain_s3 import evaluate_s3  # noqa: E402
import curves  # noqa: E402
import field  # noqa: E402
from run_probe import sha  # noqa: E402


def points(n):
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    found = []
    for mask in range(1, 1 << n):
        positive = curve.pointFromX(onb.fromCoords(mask))
        if positive is not None:
            found.extend((positive, curve.neg(positive)))
    return onb, curve, found


def main():
    rows = []
    for n in (3, 5):
        onb, curve, raw = points(n)
        anchors = raw if n == 3 else raw[:1]
        checked = exceptional_mid = exceptional_target = 0
        for anchor in anchors:
            for b, c, d in itertools.product(raw, repeat=3):
                mid = curve.add(b, c)
                if mid is None:
                    exceptional_mid += 1
                    continue
                adjusted = curve.add(mid, d)
                if adjusted is None:
                    exceptional_target += 1
                    continue
                total = curve.add(anchor, adjusted)
                assert curve.add(total, curve.neg(anchor)) == adjusted
                assert evaluate_s3(onb, b[0], c[0], mid[0]) == 0
                assert evaluate_s3(onb, mid[0], d[0], adjusted[0]) == 0
                checked += 1
        rows.append({"degree_n": n, "raw_point_count_nonzero_x": len(raw),
                     "anchor_count": len(anchors),
                     "all_triples_per_anchor": len(raw) ** 3,
                     "nonexceptional_checked": checked,
                     "identity_pair_intermediate": exceptional_mid,
                     "identity_adjusted_target": exceptional_target})
    result = {"kind": "q1439_small_field_s3_reduction_check",
              "status": "passed", "proposal_id": "Q1439",
              "scope": "all raw triples for every nonzero-x anchor at N3 and one anchor at N5; identity pair or adjusted targets counted separately",
              "rows": rows, "source_sha256": sha(Path(__file__))}
    path = HERE / "small_field_verification.json"
    assert not path.exists(), "refuse to overwrite small-field evidence"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
