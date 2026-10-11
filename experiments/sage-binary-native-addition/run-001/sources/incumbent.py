# SPDX-License-Identifier: GPL-2.0-or-later
r"""
Batched addition on ordinary binary Weierstrass curves.

The supported model is ``y^2 + x*y = x^3 + a*x^2 + b`` over a finite
field of characteristic two. This includes both Koblitz curves (b=1,
a in GF(2)) and ordinary binary curves in this model.

This module is opt-in and does not change the scalar point API. It is
intended for independent public mathematical computations, such as pair
construction and checking sums. Its branches and field operations are
variable-time.
"""

from sage.rings.finite_rings.finite_field_base import FiniteField
from sage.schemes.elliptic_curves.ell_point import EllipticCurvePoint_field
from itertools import islice, product
from operator import index as integer_index


def _invert_nonzero(values):
    """Invert nonzero elements using one inversion and 3*(n-1) products."""
    if not values:
        return []
    prefix = [values[0]]
    for value in values[1:]:
        prefix.append(prefix[-1] * value)
    inverse = ~prefix[-1]
    result = [None] * len(values)
    for i in range(len(values) - 1, 0, -1):
        result[i] = inverse * prefix[i - 1]
        inverse *= values[i]
    result[0] = inverse
    return result


def _curve_coefficient(curve):
    """Validate the supported model and return its x^2 coefficient."""
    field = curve.base_ring()
    if not isinstance(field, FiniteField) or field.characteristic() != 2:
        raise ValueError('a finite field of characteristic two is required')
    a1, a2, a3, a4, _ = curve.ainvs()
    if a1 != 1 or a3 or a4:
        raise ValueError('expected the model y^2 + x*y = x^3 + a*x^2 + b')
    return a2


def _point_data(curve, P):
    """Validate one point and retain it with its affine coordinates."""
    if not isinstance(P, EllipticCurvePoint_field) or P.curve() is not curve:
        raise ValueError('each input must be a Sage point on this curve')
    if not P:
        return P, None, None
    x, y = P.xy()
    return P, x, y


def _add_prepared(curve, pairs, a2):
    """Add pairs of already validated point/coordinate triples."""
    output = []
    active = []
    denominators = []
    field = curve.base_ring()
    one = field.one()
    zero = field.zero()
    point_class = curve._point
    zero_point = None
    for (P, x1, y1), (Q, x2, y2) in pairs:
        index = len(output)
        output.append(None)
        if x1 is None:
            output[index] = Q
            continue
        if x2 is None:
            output[index] = P
            continue
        if x1 == x2:
            if y1 != y2 or not x1:
                if zero_point is None:
                    zero_point = curve(0)
                output[index] = zero_point
                continue
            numerator = x1*x1 + y1
            denominator = x1
            xsum = zero
        else:
            numerator = y1 + y2
            denominator = x1 + x2
            xsum = denominator
        active.append((index, x1, y1, xsum, numerator))
        denominators.append(denominator)

    for entry, inverse in zip(active, _invert_nonzero(denominators)):
        index, x1, y1, xsum, numerator = entry
        slope = numerator * inverse
        x3 = slope*slope + slope + xsum + a2
        y3 = slope*(x1 + x3) + x3 + y1
        # The specialized point constructor takes a curve. Going through
        # ProjectiveSubscheme.point first tries a point homset and catches
        # AttributeError before retrying with the curve, for every result.
        output[index] = point_class(curve, [x3, y3, one], check=False)
    return output


def add_pairs(curve, pairs):
    r"""
    Return Sage points P+Q for each independent pair on ``curve``.

    Inputs must be valid Sage points belonging to exactly this curve.
    As in Sage's native arithmetic, points constructed with ``check=False``
    remain the caller's responsibility. Infinity, inverses, doubling, and
    the point of order two are handled before batch inversion. The output
    order matches the input order, including for a one-shot iterable.

    EXAMPLES::

        sage: from sage.schemes.elliptic_curves.binary_batch import add_pairs
        sage: F = GF(2**3, 'z')
        sage: E = EllipticCurve(F, [1, 1, 0, 0, 1])
        sage: P = E.random_point()
        sage: add_pairs(E, [(P, P), (P, -P), (E(0), P)]) == [2*P, E(0), P]
        True
        sage: add_pairs(E, [])
        []

    This uses O(n) temporary field elements. It saves inversions only for
    independent additions; it cannot batch dependent steps of a walk.
    """
    a2 = _curve_coefficient(curve)
    prepared = ((_point_data(curve, P), _point_data(curve, Q)) for P, Q in pairs)
    return _add_prepared(curve, prepared, a2)


def add_cartesian(curve, left, right, block_size=1024):
    r"""
    Return all P+Q with P in left and Q in right, in left-major order.

    Each input point is validated and unpacked once. Independent additions
    are processed in blocks, each with at most one inversion. Auxiliary
    storage is O(len(left) + len(right) + block_size), in addition to the
    O(len(left)*len(right)) output list. Duplicates and exceptional sums
    retain their positions. The two inputs may be one-shot iterables.

    EXAMPLES::

        sage: from sage.schemes.elliptic_curves.binary_batch import add_cartesian
        sage: E = EllipticCurve(GF(2**3, 'z'), [1, 1, 0, 0, 1])
        sage: points = list(E)
        sage: add_cartesian(E, points, points, block_size=3) == [P+Q for P in points for Q in points]
        True
    """
    block_size = integer_index(block_size)
    if block_size <= 0:
        raise ValueError('block_size must be a positive integer')
    a2 = _curve_coefficient(curve)
    left = [_point_data(curve, P) for P in left]
    right = [_point_data(curve, Q) for Q in right]
    pairs = product(left, right)
    output = []
    while block := list(islice(pairs, block_size)):
        output.extend(_add_prepared(curve, block, a2))
    return output


def frobenius_points(curve, points, power=1):
    r"""
    Apply the binary Frobenius power to valid points on a Koblitz curve.

    The curve must have a in {0,1} and b=1 in the supported binary model.
    Its coefficients are fixed by squaring, so (x,y) -> (x^2,y^2) maps
    back to the same curve. ``power`` is an integer, reduced modulo the
    field degree; negative powers give inverse Frobenius on rational
    points over that field. This is a point map, not an isogeny object.

    EXAMPLES::

        sage: from sage.schemes.elliptic_curves.binary_batch import frobenius_points
        sage: E = EllipticCurve(GF(2**5, 'z'), [1, 1, 0, 0, 1])
        sage: points = list(E)
        sage: frobenius_points(E, points) == [E.frobenius_isogeny(1)(P) for P in points]
        True
        sage: frobenius_points(E, frobenius_points(E, points), -1) == points
        True
    """
    a2 = _curve_coefficient(curve)
    if (a2 != 0 and a2 != 1) or curve.a6() != 1:
        raise ValueError('Frobenius point maps require a Koblitz curve')
    field = curve.base_ring()
    power = integer_index(power) % int(field.degree())
    one = field.one()
    point_class = curve._point
    output = []
    for P in points:
        P, x, y = _point_data(curve, P)
        if x is None or not power:
            output.append(P)
            continue
        if power == 1:
            x, y = x*x, y*y
        else:
            x, y = x.frobenius(power), y.frobenius(power)
        output.append(point_class(curve, [x, y, one], check=False))
    return output
