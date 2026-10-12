#!/usr/bin/env python3
"""Exact integer certificates for the fifteen-window radix-384 format."""

from math import isqrt

N = int("fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141", 16)
R = 384
WINDOWS = 15


def main():
    ceiling = isqrt(N)
    ceiling += ceiling * ceiling < N
    lhs = (ceiling + sum(R**j for j in range(1, WINDOWS + 1))) ** 2
    rhs = 3 * R ** (2 * WINDOWS)
    assert lhs < rhs
    assert (R * R + 12) % 6 == 0
    assert (R * R + 12) // 6 == 24_578
    print(f"radix={R} windows={WINDOWS} orbit_count=24578 slots=368670 radius_certificate={lhs < rhs}")


if __name__ == "__main__":
    main()
