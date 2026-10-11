"""Batch inversion for x-only quotient complements on a binary curve."""

import time

from quotient_pair_probe import CountedCurve, transform


def batch_add_fixed_left(curve, left, rights):
    """Return [left + right], sharing one inversion across ordinary adds.

    Exceptional inputs use the curve's complete group law.  The prefix and
    suffix products use five multiplications per ordinary addition plus one
    inversion for the whole batch; they never assume distinct x coordinates.
    """
    f = curve.f
    out = [None] * len(rights)
    slots = []
    denominators = []
    for index, right in enumerate(rights):
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
    for position in range(len(slots) - 1, -1, -1):
        inverses[position] = f.mul(suffix, prefix[position])
        suffix = f.mul(suffix, denominators[position])
    for position, index in enumerate(slots):
        right = rights[index]
        lam = f.mul(left[1] ^ right[1], inverses[position])
        x = f.sqr(lam) ^ lam ^ left[0] ^ right[0]
        y = f.mul(lam, left[0] ^ x) ^ x ^ left[1]
        out[index] = (x, y)
    return out


def query_prefix_batch(curve, index, target, degree, canonicalize, limit):
    counted = CountedCurve(curve)
    counts = {}
    started = time.perf_counter_ns()
    lookups = 0
    hits = []
    batches = 0
    for representative, pair in index.values():
        point = representative
        negative_candidates = []
        variants = []
        for shift in range(degree):
            for sign in (1, -1):
                candidate = point if sign == 1 else counted.neg(point)
                negative_candidates.append(counted.neg(candidate))
                variants.append((shift, sign))
                if len(negative_candidates) == limit - lookups:
                    break
            if len(negative_candidates) == limit - lookups:
                break
            point = counted.frob(point)
        complements = batch_add_fixed_left(curve, target, negative_candidates)
        counted.counts["add"] += len(complements)
        batches += 1
        for complement, (shift, sign) in zip(complements, variants):
            key, comp_shift = canonicalize.key_and_shift(counted, complement, counts)
            lookups += 1
            counted.counts["lookup"] += 1
            match = index.get(key)
            if match is not None:
                other_representative, other_pair = match
                undo = (-comp_shift) % degree
                aligned = transform(counted, other_representative, undo, 1)
                if aligned == complement:
                    other_sign = 1
                elif counted.neg(aligned) == complement:
                    other_sign = -1
                else:
                    raise AssertionError("x-only orbit collision")
                first = tuple(transform(counted, p, shift, sign) for p in pair)
                second = tuple(transform(counted, p, undo, other_sign)
                               for p in other_pair)
                total = None
                for p in first + second:
                    total = curve.add(total, p)
                assert total == target, "four-point witness failed replay"
                hits.append(lookups)
        if lookups == limit:
            return {"status": "bounded_prefix", "lookups": lookups,
                    "verified_hit_positions": hits,
                    "wall_ns": time.perf_counter_ns() - started,
                    "batches": batches,
                    "point_operations": counted.counts,
                    "canonical_operations": counts}
    raise AssertionError("lookup limit exceeds complete index scan")
