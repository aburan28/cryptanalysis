"""Point evaluation for the saved odd-degree Kohel isogeny and its dual.

Sage's ``EllipticCurveIsogeny._eval`` evaluates the affine rational map and
may divide by zero at a nonzero kernel point.  The complete group morphism
maps precisely those points, and the identity, to the codomain identity.
The caller must construct the isogeny from the checked kernel polynomial;
this helper does not certify an arbitrary polynomial or curve.
"""


def evaluate_with_kernel(isogeny, kernel_polynomial, point):
    """Evaluate a checked odd-degree isogeny, including geometric kernel points.

    ``point`` may be defined over an extension of the isogeny's base field.
    The raw Sage evaluator is used only after ruling out its poles.  For an
    ordinary base-field point this has the same result as ``isogeny(point)``.
    """
    field = point.curve().base_ring()
    domain = isogeny.domain().change_ring(field)
    if point.curve() != domain:
        raise ValueError("point is not on the isogeny source model")
    codomain = isogeny.codomain().change_ring(field)
    if point.is_zero() or kernel_polynomial(point[0]) == 0:
        return codomain(0)
    return isogeny._eval(point)
