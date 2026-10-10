#!/usr/bin/env python3
"""Exhaust the fixed-seed W15 product identity before Frobenius rotation."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = 13686


def mul(a, b):
    result = 0
    while b:
        if b & 1:
            result ^= a
        a <<= 1
        b >>= 1
    return result


def source(mask):
    return mask << 1


def rank(vectors):
    pivots = {}
    for value in vectors:
        while value:
            bit = value.bit_length()-1
            if bit not in pivots:
                pivots[bit] = value
                break
            value ^= pivots[bit]
    return len(pivots)


def main():
    s = source(SEED)
    basis = [mul(1 << (i+1), (1 << (i+1)) ^ s) for i in range(15)]
    assert rank(basis) == 14
    for left_mask in range(1 << 15):
        w = source(left_mask)
        direct = mul(w, w ^ s)
        linear = 0
        for i, item in enumerate(basis):
            if left_mask >> i & 1:
                linear ^= item
        assert direct == linear and direct.bit_length() <= 31
    receipt = {"status": "PASS_ALL_32768_FIXED_SEED_PRODUCTS",
               "field_modulus": "t^131+t^13+t^2+t+1",
               "seed": SEED, "tested_left_masks": 32768,
               "product_image_dimension": rank(basis),
               "product_coordinate_basis": basis,
               "source_sha256": {"script": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}
    with (HERE / "product_identity.json").open("x") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"], "rank": receipt["product_image_dimension"]}))


if __name__ == "__main__":
    main()
