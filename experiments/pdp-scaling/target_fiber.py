"""Four original-point targets corresponding to a projected subgroup query."""

from gf2n import INF, Point


KERNEL_4 = (INF, Point(0, 1), Point(1, 0), Point(1, 1))


def scalar_mul(curve, point, k):
    if k < 0:
        raise ValueError("negative scalar")
    result = INF
    while k:
        if k & 1:
            result = curve.add(result, point)
        point = curve.add(point, point)
        k >>= 1
    return result


def projected_preimages(curve, target, prime_order):
    """All E(F_2^n) solutions Q of [4]Q=target on y²+xy=x³+1.

    The intended target lies in the order-r subgroup with odd prime r. The
    rational 4-torsion is exactly KERNEL_4 on this curve in characteristic 2.
    """
    if curve.b != 1 or prime_order <= 2 or prime_order % 2 == 0:
        raise ValueError("wrong curve or odd subgroup order")
    if target.inf or not curve.on_curve(target) or scalar_mul(curve, target, prime_order) != INF:
        raise ValueError("target must be a nonidentity point of the subgroup")
    if len(set(KERNEL_4)) != 4 or any(not curve.on_curve(p) or scalar_mul(curve, p, 4) != INF
                                     for p in KERNEL_4):
        raise ValueError("invalid 4-torsion kernel")
    first = scalar_mul(curve, target, pow(4, -1, prime_order))
    options = tuple(curve.add(first, torsion) for torsion in KERNEL_4)
    if len(set(options)) != 4 or any(scalar_mul(curve, p, 4) != target for p in options):
        raise ValueError("invalid target fiber")
    return options
