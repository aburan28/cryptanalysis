"""Exact terminal disk and six-unit rank for fifteen radix-256 windows."""

from __future__ import annotations

from math import isqrt

BASE = 256
WINDOWS = 15
RADIUS = 1 << 128
CAP = (RADIUS + sum(BASE**j for j in range(1, WINDOWS + 1)))**2 // BASE**(2 * WINDOWS)
U_MAX = isqrt(4 * CAP // 3)


def norm(pair: tuple[int, int]) -> int:
    a, b = pair
    return a*a + 3*a*b + 3*b*b


def images(pair: tuple[int, int]) -> tuple[tuple[int, int], ...]:
    a, b = pair
    return ((a, b), (-a, -b), (a+3*b, -a-2*b),
            (-a-3*b, a+2*b), (-2*a-3*b, a+b),
            (2*a+3*b, -a-b))


def sector(pair: tuple[int, int]) -> bool:
    a, b = pair
    return a < 0 and -a <= 3*b < -2*a


def rows() -> tuple[tuple[int, int, int], ...]:
    """For each u: first b, exclusive last b, first table index."""
    result = [(0, 0, 0)]
    offset = 1  # table index zero represents the identity
    for u in range(1, U_MAX + 1):
        values = [b for b in range((u+2)//3, (2*u-1)//3 + 1)
                  if 3*norm((-u, b)) <= CAP]
        if values:
            assert values == list(range(values[0], values[-1] + 1))
            result.append((values[0], values[-1] + 1, offset))
            offset += len(values)
        else:
            result.append((0, 0, offset))
    assert offset == 13_314
    return tuple(result)


TOP_ROWS = rows()
TOP_ENTRIES = TOP_ROWS[-1][2] + TOP_ROWS[-1][1] - TOP_ROWS[-1][0]
assert CAP == 66_051 and U_MAX == 296 and TOP_ENTRIES == 13_314


def top_index(pair: tuple[int, int]) -> tuple[int, int]:
    """Return (point-table index, unit code) for a bounded terminal pair."""
    assert 3*norm(pair) <= CAP
    if pair == (0, 0):
        return 0, 0
    canonical = [item for item in images(pair) if sector(item)]
    assert len(canonical) == 1
    u, b = -canonical[0][0], canonical[0][1]
    first, stop, offset = TOP_ROWS[u]
    assert first <= b < stop
    code = images(canonical[0]).index(pair)
    return offset + b - first, code
