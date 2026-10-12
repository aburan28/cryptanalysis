"""Batch affine sums and x-only keys for signed-Frobenius pair matching."""


def batch_add(curve, pairs):
    """Return P+Q for each pair, using one inversion for nonexceptional sums.

    The prefix-product inversion is Montgomery's trick. Exceptional equal-x
    pairs use the curve's ordinary add rule and remain in the output order.
    """
    f = curve.f
    output = [None] * len(pairs)
    live = []
    prefixes = []
    product = f.one()
    for index, (left, right) in enumerate(pairs):
        if left is None or right is None or left[0] == right[0]:
            output[index] = curve.add(left, right)
            continue
        denominator = f.add(left[0], right[0])
        prefixes.append(product)
        live.append((index, left, right, denominator))
        product = f.mul(product, denominator)
    if not live:
        return output
    suffix_inverse = f.inv(product)
    for position in range(len(live) - 1, -1, -1):
        index, (x1, y1), (x2, y2), denominator = live[position]
        inverse = f.mul(prefixes[position], suffix_inverse)
        suffix_inverse = f.mul(suffix_inverse, denominator)
        slope = f.mul(f.add(y1, y2), inverse)
        x3 = f.add(f.add(f.sqr(slope), slope), denominator)
        y3 = f.add(f.add(f.mul(slope, f.add(x1, x3)), x3), y1)
        output[index] = (x3, y3)
    return output


def x_orbit_key(orbit, point):
    """Minimum cyclic normal-basis x rotation; -P shares the same x."""
    if point is None:
        return -1
    x = orbit.cycle_bits(point[0])
    best = x
    for _ in range(1, orbit.n):
        x = ((x << 1) | (x >> (orbit.n - 1))) & orbit.mask
        if x < best:
            best = x
    return best
