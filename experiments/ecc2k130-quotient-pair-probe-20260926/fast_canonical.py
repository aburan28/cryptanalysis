"""Canonicalize a signed-Frobenius point orbit by screening x first.

For the binary Koblitz model, negation preserves x.  The lexicographically
least orbit point therefore has the least Frobenius conjugate of x.  Only
shifts attaining that x need a Frobenius map of y and a sign comparison.
"""


def canonical_x_first(curve, point, degree, counts=None):
    """Return the same (key, shift, sign) as quotient_pair_probe.canonical."""
    if point is None:
        return (-1, -1), 0, 1
    raw_curve = getattr(curve, "curve", curve)
    field = raw_curve.f
    x, y = point
    least_x = x
    least_shifts = [0]
    current_x = x
    for shift in range(1, degree):
        current_x = (field.frob(current_x, 1) if hasattr(field, "frob")
                     else field.sqr(current_x))
        if counts is not None:
            counts["x_field_frob"] = counts.get("x_field_frob", 0) + 1
        if current_x < least_x:
            least_x = current_x
            least_shifts = [shift]
        elif current_x == least_x:
            least_shifts.append(shift)

    best = None
    best_shift = 0
    best_sign = 1
    for shift in least_shifts:
        if shift == 0:
            shifted_y = y
        elif hasattr(field, "frob"):
            shifted_y = field.frob(y, shift)
        else:
            shifted_y = y
            for _ in range(shift):
                shifted_y = field.sqr(shifted_y)
        if counts is not None and shift:
            counts["y_field_frob"] = counts.get("y_field_frob", 0) + 1
        negated_y = (field.add(shifted_y, least_x)
                     if hasattr(field, "add") else shifted_y ^ least_x)
        if counts is not None:
            counts["field_add"] = counts.get("field_add", 0) + 1
        for sign, candidate_y in ((1, shifted_y), (-1, negated_y)):
            key = (least_x, candidate_y)
            if best is None or key < best:
                best, best_shift, best_sign = key, shift, sign
    return best, best_shift, best_sign
