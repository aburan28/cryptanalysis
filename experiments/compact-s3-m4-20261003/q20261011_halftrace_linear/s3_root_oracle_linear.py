"""S3 roots with a coordinate-linear half-trace in the type-II normal basis.

For q=2m+1, gamma_i^(2^k)=gamma_fold(2^k i mod q).  Therefore the
half-trace image of each basis coordinate is a fixed m-bit mask.  Building
the masks depends only on the field degree; each query XORs the masks of
its set coordinates.  `basis_xors` counts those query-dependent XORs.
"""

from chain_s3 import evaluate_s3

_MASKS = {}


def masks(m):
    if m not in _MASKS:
        q = 2 * m + 1
        rows = []
        for i in range(1, m + 1):
            position = i
            image = 0
            for _ in range((m + 1) // 2):
                folded = min(position, q - position)
                image ^= 1 << (folded - 1)
                position = (position * 4) % q
            rows.append(image)
        _MASKS[m] = tuple(rows)
    return _MASKS[m]


def half_trace(onb, value):
    coords = onb.toCoords(value)
    image = 0
    xors = 0
    table = masks(onb.m)
    while coords:
        bit = coords & -coords
        image ^= table[bit.bit_length() - 1]
        coords ^= bit
        xors += 1
    onb.linear_halftrace_calls = getattr(onb, "linear_halftrace_calls", 0) + 1
    onb.linear_halftrace_basis_xors = (
        getattr(onb, "linear_halftrace_basis_xors", 0) + xors)
    return onb.fromCoords(image)


def s3_roots(onb, a, b):
    """Return every root c of S3(a,b,c), in coordinate order."""
    assert a and b
    product = onb.mul(a, b)
    if a == b:
        root = onb.mul(onb.add(onb.sqr(product), onb.one()),
                       onb.inv(product))
        assert evaluate_s3(onb, a, b, root) == 0
        return (root,)
    total = onb.add(a, b)
    total_squared = onb.sqr(total)
    inverse_product = onb.inv(product)
    constant = onb.add(onb.sqr(product), onb.one())
    rhs = onb.mul(onb.mul(total_squared, constant),
                  onb.sqr(inverse_product))
    if onb.trace(rhs):
        return ()
    z = half_trace(onb, rhs)
    assert onb.add(onb.sqr(z), z) == rhs
    scale = onb.mul(product, onb.inv(total_squared))
    first = onb.mul(scale, z)
    second = onb.add(first, scale)
    assert first != second
    assert evaluate_s3(onb, a, b, first) == 0
    assert evaluate_s3(onb, a, b, second) == 0
    return tuple(sorted((first, second), key=onb.toCoords))
