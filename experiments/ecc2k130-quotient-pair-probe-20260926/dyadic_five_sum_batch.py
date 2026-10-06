"""Montgomery-batched binary-curve additions for independent point pairs."""


def batch_add_pairs(curve, pairs):
    """Return each P+Q, sharing one inversion across ordinary additions.

    Identity, equal-x, doubling, and opposite-point cases use the complete
    curve law.  The ordinary path implements y²+xy=x³+a₂x²+a₆ with the
    curve's existing affine formula, which is specialized to a₂=0 here.
    """
    f = curve.f
    out = [None] * len(pairs)
    slots = []
    denominators = []
    for index, (left, right) in enumerate(pairs):
        if left is None or right is None or left[0] == right[0]:
            out[index] = curve.add(left, right)
        else:
            slots.append(index)
            denominators.append(left[0] ^ right[0])
    if not slots:
        return out
    prefix = [f.one()]
    for denominator in denominators:
        prefix.append(f.mul(prefix[-1], denominator))
    suffix = f.inv(prefix[-1])
    inverses = [None] * len(slots)
    for pos in range(len(slots) - 1, -1, -1):
        inverses[pos] = f.mul(suffix, prefix[pos])
        suffix = f.mul(suffix, denominators[pos])
    for pos, index in enumerate(slots):
        left, right = pairs[index]
        lam = f.mul(left[1] ^ right[1], inverses[pos])
        x = f.sqr(lam) ^ lam ^ left[0] ^ right[0]
        y = f.mul(lam, left[0] ^ x) ^ x ^ left[1]
        out[index] = (x, y)
    return out
