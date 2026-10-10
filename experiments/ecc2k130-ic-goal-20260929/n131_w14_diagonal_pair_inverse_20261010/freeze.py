#!/usr/bin/env python3
"""Freeze constructed diagonal-pair outputs and trace-zero field controls."""

import hashlib
import json
import random
from pathlib import Path

from pair_inverse import DiagonalPairInverse, SUPPORT

HERE = Path(__file__).resolve().parent
SEED = 0xD1A6A14C131


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "inputs.json"
    if output.exists():
        raise FileExistsError(output)
    inverse = DiagonalPairInverse()
    f, curve = inverse.field, inverse.curve
    masks = sorted(inverse.columns)
    rng = random.Random(SEED)
    cases = []
    selected = set()
    while len(cases) < 32:
        a, b = sorted(rng.sample(masks, 2))
        if inverse.columns[a] == inverse.columns[b]:
            continue
        right_negative = rng.randrange(2)
        left, right = inverse.atom(a), inverse.atom(b)
        if right_negative:
            right = curve.neg(right)
        total = curve.add(left, right)
        if total is None or total[0] == 0:
            continue
        z = f.inv(total[0])
        if z in selected:
            continue
        selected.add(z)
        cases.append({"kind": "positive", "z": z, "a": a, "b": b,
                      "right_negative": right_negative,
                      "point": list(total)})
    while len(cases) < 64:
        v = rng.getrandbits(131)
        z = f.mul(v, v) ^ v
        if z == 0 or z in selected:
            continue
        selected.add(z)
        cases.append({"kind": "trace_zero_uniform", "z": z})
    result = {"status": "FROZEN", "seed": SEED,
              "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "source_support_sha256": sha(SUPPORT),
              "source_sha256": {"freeze": sha(Path(__file__)),
                                "inverse": sha(HERE / "pair_inverse.py")},
              "input_law": "32 independently sampled distinct-column W14 diagonal-atom pairs with random relative sign, followed by 32 uniform trace-zero field elements generated as v^2+v; positives are construction controls",
              "cases": cases}
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "positive": 32,
                      "trace_zero_uniform": 32}))


if __name__ == "__main__":
    main()
