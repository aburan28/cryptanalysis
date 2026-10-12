#!/usr/bin/env python3
"""Verify a two-word signed-magnitude quotient by 640."""

from hashlib import sha256
import json
from pathlib import Path
import random
import sys

HERE = Path(__file__).resolve().parent
MASK = (1 << 64) - 1
K = MASK // 5
SEED = 20261010640
COUNT = 100_000


def quotient_remainder(value):
    magnitude = abs(value)
    assert magnitude < 1 << 129
    limbs = (magnitude & MASK, (magnitude >> 64) & MASK, magnitude >> 128)
    assert limbs[2] <= 1
    low_seven = limbs[0] & 127
    low = (limbs[0] >> 7) | ((limbs[1] << 57) & MASK)
    high = (limbs[1] >> 7) | (limbs[2] << 57)
    q_high, r_high = divmod(high, 5)
    q_low, r_low = divmod(low, 5)
    carry = int(r_high + r_low >= 5)
    remainder = low_seven + 128 * (r_high + r_low - 5 * carry)
    quotient_low = r_high * K + q_low + carry
    assert 0 <= quotient_low <= MASK and 0 <= remainder < 640
    quotient = quotient_low | (q_high << 64)
    assert 640 * quotient + remainder == magnitude
    return (-quotient, -remainder) if value < 0 else (quotient, remainder)


def check(value, index_hash):
    quotient, signed_remainder = quotient_remainder(value)
    expected = divmod(abs(value), 640)
    assert (abs(quotient), abs(signed_remainder)) == expected
    assert 640 * quotient + signed_remainder == value
    assert signed_remainder % 640 == value % 640
    # Any atlas digit congruent to the residue may be incorporated by one
    # small signed quotient adjustment, matching Signed192's update rule.
    for shift in (-2, -1, 0, 1, 2):
        digit = signed_remainder + 640 * shift
        updated = quotient + (signed_remainder - digit) // 640
        assert 640 * updated + digit == value
    index_hash.update(value.to_bytes(17, "little", signed=True))


def main():
    assert MASK == 5 * K
    edges = [0, 1, 5, 127, 128, 639, 640, 641, 1 << 64,
             (1 << 64) - 1, 1 << 128, (1 << 129) - 1]
    digest = sha256()
    for value in edges:
        check(value, digest)
        if value:
            check(-value, digest)
    rng = random.Random(SEED)
    for _ in range(COUNT):
        value = rng.getrandbits(129)
        check(value if rng.getrandbits(1) else -value, digest)
    receipt = {"schema": 1, "seed": SEED, "random_cases": COUNT,
               "edge_cases": 2 * len(edges) - 1,
               "input_sha256": digest.hexdigest(),
               "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
               "status": "passed"}
    target = HERE / "fast-division-check.json"
    if sys.argv[1:] == ["--write"]:
        target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    else:
        assert not sys.argv[1:]
        assert json.loads(target.read_bytes()) == receipt
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
