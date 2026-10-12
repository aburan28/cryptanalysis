#!/usr/bin/env python3
"""Dense direct index for six-unit orbits modulo 2^10."""

RADIX_BITS = 10
RADIX = 1 << RADIX_BITS
CLASS_COUNT = 174_764
OFFSETS = (0, 1, 2, 4, 12, 44, 172, 684, 2732, 10924, 43692)


def canonicalize(a, b):
    """Return (dense orbit index, unit sending input to canonical residue)."""
    assert 0 <= a < RADIX and 0 <= b < RADIX
    value = a | b
    if value == 0:
        return 0, 0
    valuation = (value & -value).bit_length() - 1
    m = RADIX_BITS - valuation
    mask = (1 << m) - 1
    a >>= valuation
    b >>= valuation
    parity = (a & 1, b & 1)
    if parity == (1, 0):
        power = 0
    elif parity == (0, 1):
        power = 1
        a, b = (a + 3 * b) & mask, (-a - 2 * b) & mask
    else:
        assert parity == (1, 1)
        power = 2
        a, b = (-2 * a - 3 * b) & mask, (a + b) & mask
    assert a & 1 and not b & 1
    sign = int(m > 1 and a >= (1 << (m - 1)))
    if sign:
        a, b = (-a) & mask, (-b) & mask
    assert a & 1 and not b & 1
    if m == 1:
        assert (a, b) == (1, 0)
        return 1, 2 * power
    assert 1 <= a < 1 << (m - 1)
    index = OFFSETS[m] + ((a - 1) >> 1) * (1 << (m - 1)) + (b >> 1)
    assert OFFSETS[m] <= index < CLASS_COUNT
    return index, 2 * power + sign


def representatives():
    """Yield (index, residue) in atlas order."""
    yield 0, (0, 0)
    yield 1, (RADIX >> 1, 0)
    for m in range(2, RADIX_BITS + 1):
        stride = 1 << (RADIX_BITS - m)
        half = 1 << (m - 1)
        for a in range(1, half, 2):
            for b in range(0, 1 << m, 2):
                index = OFFSETS[m] + ((a - 1) >> 1) * half + (b >> 1)
                yield index, (a * stride, b * stride)
