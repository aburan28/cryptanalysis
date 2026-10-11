#!/usr/bin/env python3
"""Independent field-equation controls for functional inversion and S3 roots."""

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "ecc2k130-w24-natural-pdp-20261005"
sys.path.insert(0, str(PARENT))

import arithmetic as a  # noqa: E402
import functional as f  # noqa: E402


def main():
    base = json.loads((HERE.parent / "ecc2k130-263-equal-w24-workload-20261005" /
                       "base_selection.json").read_text())
    masks = base["source"]["control_masks_selection_order"][:6]
    basis = a.source_basis()
    ws = [a.source_w(mask, basis) for mask in masks]
    us = [a.halftrace(w) for w in ws]
    samples = [0, 1, *ws]
    rng = random.Random(0)
    samples.extend(rng.randrange(1, 1 << a.N) for _ in range(4))
    for value in samples:
        expected = a.inv(value) if value else 0
        assert f.numeric_inverse_131(value) == expected
        h = f.halftrace_unchecked(value)
        assert a.square(h) ^ h == value ^ a.trace(value)
    assert len(f.halftrace_images()) == a.N

    branches = {}
    for label, u1, u2 in (("regular", us[0], us[1]),
                          ("B0", 1, us[0]),
                          ("B1", us[0], a.halftrace(a.inv(ws[0])))):
        results = []
        for bit in (0, 1):
            root, branch, residual = f.numeric_s3_root(u1, u2, bit)
            assert residual == 0, (label, bit, branch, residual)
            assert branch == label, (label, branch)
            results.append(root)
        if label == "regular":
            assert results[0] != results[1]
        else:
            assert results[0] == results[1]
        branches[label] = [str(root) for root in results]
    print(json.dumps({"status": "PASS", "inverse_samples": len(samples),
                      "halftrace_samples": len(samples), "branches": branches},
                     sort_keys=True))


if __name__ == "__main__":
    main()
