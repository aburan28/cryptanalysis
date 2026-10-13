"""Exact Voronoi-clipped terminal domain for the secp256k1 radix-256 recoder."""

from __future__ import annotations

from math import isqrt

ORDER = int("fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141", 16)
U = (193508920647619669885755136084601127231,
     238911465918039986966665730306072050094)
V = (-U[1], 303414439467246543595250775667605759171)
W = (U[0] - 2 * V[0], U[1] - 2 * V[1])
NEIGHBORS = (W, V, (W[0] + V[0], W[1] + V[1]))
RADIX = 256
WINDOWS = 15
POWER = RADIX**WINDOWS
DIGIT_WEIGHT_SUM = sum(RADIX**j for j in range(WINDOWS))
DISK_CAP = 66_051


def norm(pair: tuple[int, int]) -> int:
    a, b = pair
    return a*a + 3*a*b + 3*b*b


def twice_inner(pair: tuple[int, int], vector: tuple[int, int]) -> int:
    a, b = pair
    x, y = vector
    return a*(2*x + 3*y) + b*(3*x + 6*y)


def ceil_sqrt(n: int) -> int:
    root = isqrt(n)
    return root + (root*root < n)


# 3*M^2 >= 4*RADIX^2*ORDER is the integer Cauchy certificate.
DIGIT_SUPPORT = ceil_sqrt((4*RADIX*RADIX*ORDER + 2)//3)
HEX_LIMIT = (ORDER + DIGIT_SUPPORT*DIGIT_WEIGHT_SUM)//POWER
U_MAX = isqrt(4*DISK_CAP//3)


def images(pair: tuple[int, int]) -> tuple[tuple[int, int], ...]:
    a, b = pair
    return ((a, b), (-a, -b), (a+3*b, -a-2*b),
            (-a-3*b, a+2*b), (-2*a-3*b, a+b),
            (2*a+3*b, -a-b))


def sector(pair: tuple[int, int]) -> bool:
    a, b = pair
    return a < 0 and -a <= 3*b < -2*a


def in_domain(pair: tuple[int, int]) -> bool:
    return (3*norm(pair) <= DISK_CAP and
            all(abs(twice_inner(pair, vector)) <= HEX_LIMIT
                for vector in NEIGHBORS))


def rows() -> tuple[tuple[int, int, int], ...]:
    result = [(0, 0, 0)]
    offset = 1  # identity is an explicit table slot
    for u in range(1, U_MAX + 1):
        admissible = [b for b in range((u+2)//3, (2*u-1)//3 + 1)
                      if in_domain((-u, b))]
        if admissible:
            assert admissible == list(range(admissible[0], admissible[-1] + 1))
            result.append((admissible[0], admissible[-1] + 1, offset))
            offset += len(admissible)
        else:
            result.append((0, 0, offset))
    assert offset == 11_023
    return tuple(result)


TOP_ROWS = rows()
TOP_ENTRIES = TOP_ROWS[-1][2] + TOP_ROWS[-1][1] - TOP_ROWS[-1][0]
assert TOP_ENTRIES == 11_023
assert DIGIT_SUPPORT == 100588603464850855725768518207408495723870
assert HEX_LIMIT == 87506751043387112747509266240600930742795


def top_index(pair: tuple[int, int]) -> tuple[int, int]:
    assert in_domain(pair)
    if pair == (0, 0):
        return 0, 0
    canonical = [item for item in images(pair) if sector(item)]
    assert len(canonical) == 1
    u, b = -canonical[0][0], canonical[0][1]
    first, stop, offset = TOP_ROWS[u]
    assert first <= b < stop
    return offset + b - first, images(canonical[0]).index(pair)


def independent_slot_capacity(point_entries: int, slots: int = 16) -> int:
    """Maximum choices with balanced six-image point slots and one identity each."""
    q, extra = divmod(point_entries, slots)
    return (6*q-5)**(slots-extra) * (6*(q+1)-5)**extra


def capacity_lower_entries() -> int:
    low, high = 16, 200_000
    while low + 1 < high:
        middle = (low + high)//2
        if independent_slot_capacity(middle) >= ORDER:
            high = middle
        else:
            low = middle
    return high
