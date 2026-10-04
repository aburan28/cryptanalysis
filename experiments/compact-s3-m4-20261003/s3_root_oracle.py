"""Exact S3 roots in the third x coordinate over odd binary fields.

For nonzero a and b, the S3 equation in c is

    (a+b)^2 c^2 + ab c + (ab)^2 + 1 = 0.

When a != b, reducing this quadratic to z^2+z=d gives at most two roots.
The half-trace map solves that Artin-Schreier equation for trace-zero d.
"""

from chain_s3 import evaluate_s3


def half_trace(onb, value):
    assert onb.m & 1
    result = 0
    current = value
    for _ in range((onb.m + 1) // 2):
        result = onb.add(result, current)
        current = onb.frob(current, 2)
    return result


def s3_roots(onb, a, b):
    """Return every field root c of S3(a,b,c), in coordinate order."""
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
