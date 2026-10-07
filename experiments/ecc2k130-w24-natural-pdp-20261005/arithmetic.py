"""Standalone polynomial-basis arithmetic for the exact source W24 SAT input."""

N = 131
LOW_TERMS = (13, 2, 1, 0)
MODULUS = (1 << N) | sum(1 << i for i in LOW_TERMS)
R = 680564733841876926932320129493409985129
LAST_MASK = 16763440
TORSION = (None, (0, 1), (1, 0), (1, 1))


def reduce(value):
    while value.bit_length() > N:
        value ^= MODULUS << (value.bit_length() - N - 1)
    return value


def mul(left, right):
    result = 0
    while right:
        if right & 1:
            result ^= left
        right >>= 1
        left <<= 1
        if left & (1 << N):
            left ^= MODULUS
    return result


def square(value):
    return mul(value, value)


def inv(value):
    if value == 0:
        raise ZeroDivisionError("field inverse of zero")
    a, b, x, y = MODULUS, value, 0, 1
    while b != 1:
        shift = a.bit_length() - b.bit_length()
        if shift < 0:
            a, b, x, y = b, a, y, x
            continue
        a ^= b << shift
        x ^= y << shift
        if a.bit_length() < b.bit_length():
            a, b, x, y = b, a, y, x
    result = reduce(y)
    assert mul(value, result) == 1
    return result


def trace(value):
    term = value
    result = value
    for _ in range(N - 1):
        term = square(term)
        result ^= term
    assert result in (0, 1)
    return result


def halftrace(value):
    assert trace(value) == 0
    term = value
    result = 0
    for _ in range((N + 1) // 2):
        result ^= term
        term = square(square(term))
    assert square(result) ^ result == value
    return result


def source_basis():
    basis = tuple((1 << j) ^ trace(1 << j) for j in range(1, 25))
    assert all(trace(value) == 0 for value in basis)
    return basis


def coordinate(basis, mask):
    result = 0
    for j, value in enumerate(basis):
        if mask & (1 << j):
            result ^= value
    return result


def source_w(mask, basis):
    if not 0 < mask <= LAST_MASK:
        raise ValueError("mask outside frozen source prefix")
    w = coordinate(basis, mask)
    assert w != 0 and trace(w) == 0
    return w


def rational_x(mask, basis):
    w = source_w(mask, basis)
    if trace(inv(w)) != 0:
        raise ValueError("mask is not in the rational source W24 base")
    u = halftrace(w)
    assert u not in (0, 1)
    return 1 ^ inv(u)


def on_curve(point):
    if point is None:
        return True
    x, y = point
    return square(y) ^ mul(x, y) == mul(square(x), x) ^ 1


def negate(point):
    return None if point is None else (point[0], point[0] ^ point[1])


def add(left, right):
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2:
        if x1 == 0 or y2 == (y1 ^ x1):
            return None
        slope = x1 ^ mul(y1, inv(x1))
        x3 = square(slope) ^ slope
        y3 = square(x1) ^ mul(slope ^ 1, x3)
    else:
        slope = mul(y1 ^ y2, inv(x1 ^ x2))
        x3 = square(slope) ^ slope ^ x1 ^ x2
        y3 = mul(slope, x1 ^ x3) ^ x3 ^ y1
    result = (x3, y3)
    assert on_curve(result)
    return result


def scalar_mul(value, point):
    if value < 0:
        return scalar_mul(-value, negate(point))
    result = None
    while value:
        if value & 1:
            result = add(result, point)
        point = add(point, point)
        value >>= 1
    return result


def points_with_x(x):
    if x == 0:
        return ((0, 1),)
    rhs = x ^ inv(square(x))
    if trace(rhs) != 0:
        return ()
    z = halftrace(rhs)
    first = (x, mul(x, z))
    second = negate(first)
    assert on_curve(first) and on_curve(second)
    return (first, second)


def raw_point(mask, basis):
    points = points_with_x(rational_x(mask, basis))
    assert len(points) == 2
    return min(points, key=lambda point: point[1])


def target_fibers(q):
    assert on_curve(q) and q is not None and scalar_mul(R, q) is None
    base = scalar_mul(pow(4, -1, R), q)
    assert scalar_mul(4, base) == q
    fibers = tuple(add(base, torsion) for torsion in TORSION)
    assert len(set(fibers)) == 4
    assert all(point is not None and scalar_mul(4, point) == q for point in fibers)
    return fibers


def s3_cleared(u1, u2, z):
    w1, w2, wz = square(u1) ^ u1, square(u2) ^ u2, square(z) ^ z
    return mul(mul(w1, w2), wz) ^ square(u1 ^ u2 ^ z)


def group_sum(points):
    result = None
    for point in points:
        result = add(result, point)
    return result
