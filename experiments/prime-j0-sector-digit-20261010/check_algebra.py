#!/usr/bin/env python3
"""Independently enumerate the old norm rule and the sector formula."""

import hashlib
import json


def norm(a, b):
    return a * a + 3 * a * b + 3 * b * b


def canonical_pairs(m):
    q, r = divmod(m, 3)
    for b in range(m // 2 + 1):
        yield 0, b
    for a in range(1, q + 1):
        for b in range(q - a + 1):
            yield a, b
        for b in range(q + 1, 2 * q + r - a):
            yield a, b
        for b in range(2 * q + r, m - a):
            yield a, b


def old_four_corners(a, b, m):
    u, v = a + b, -b
    return tuple(
        (u - x * m + v - y * m, -(v - y * m))
        for x in (u // m, u // m + 1)
        for y in (v // m, v // m + 1)
    )


def sector_digit(a, b, m):
    q, r = divmod(m, 3)
    if a == 0:
        return (0, b) if b <= q else (-m, b)
    if b <= q - a:
        return a, b
    if b <= 2 * q + r - 1 - a:
        return a - m, b
    return a, b - m


def main():
    rows = []
    for m in (512, 1024):
        digest = hashlib.sha256()
        ties = count = 0
        for a, b in canonical_pairs(m):
            corners = old_four_corners(a, b, m)
            old = min(corners, key=lambda point: (norm(*point), *point))
            new = sector_digit(a, b, m)
            if old != new:
                raise AssertionError((m, a, b, old, new))
            ties += sum(norm(*point) == norm(*old) for point in corners) > 1
            digest.update(int(new[0]).to_bytes(2, "little", signed=True))
            digest.update(int(new[1]).to_bytes(2, "little", signed=True))
            count += 1
        if count != (m * m + 8) // 6:
            raise AssertionError((m, count))
        rows.append({"radix": m, "canonical_count": count,
                     "norm_ties": ties, "digit_sha256": digest.hexdigest()})
    print(json.dumps({"schema": 1, "status": "passed", "rows": rows}, sort_keys=True))


if __name__ == "__main__":
    main()
