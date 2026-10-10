#!/usr/bin/env python3
"""Integer certificates for the two-limb radix-384 quotient."""

N = int("fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141", 16)
K = (2**64 - 1) // 3


def main():
    assert 2**64 == 3 * K + 1
    assert 3 * 2**258 > 4 * N  # |a| < 2^129
    assert 9 * 2**256 > 4 * N  # |b| < 2^128
    assert 3 * 444**2 > 4 * 384**2
    assert (2**129 + 443) // 384 < 2**129
    for rh in range(3):
        for rl in range(3):
            max_low_quotient = K if rl == 0 else K - 1
            carry = (rh + rl) // 3
            assert rh * K + max_low_quotient + carry <= 2**64 - 1
    print("two_limb_radix384_certificate=passed")


if __name__ == "__main__":
    main()
