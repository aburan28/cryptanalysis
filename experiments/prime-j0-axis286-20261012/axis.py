"""The bounded terminal pair as two one-dimensional unit-sector axes."""

from __future__ import annotations

BASE = 286
WINDOWS = 14
CAP = 192_971_294
U_MAX = 16_040
B_MAX = 10_693


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


def factor(pair: tuple[int, int]) -> tuple[int, int, int]:
    """Return (unit code, u, b) for pair = unit((-u,0)+(0,b))."""
    assert 3 * norm(pair) <= CAP
    if pair == (0, 0):
        return 0, 0, 0
    canonical = [candidate for candidate in images(pair) if sector(candidate)]
    assert len(canonical) == 1
    u, b = -canonical[0][0], canonical[0][1]
    assert 1 <= u <= U_MAX and 1 <= b <= B_MAX
    assert 12 * norm((-u, b)) == 9*(2*b-u)**2 + 3*u*u
    assert norm(canonical[0]) == norm(pair)
    code = images(canonical[0]).index(pair)
    assert images((-u, b))[code] == pair
    return code, u, b
