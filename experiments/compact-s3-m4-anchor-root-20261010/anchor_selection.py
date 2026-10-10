"""Deterministic exact-base normal-basis anchor-pair selection."""

from __future__ import annotations

from collections import Counter
import hashlib
import math


def weight_mask(n, weight, rank):
    """Lexicographically unrank one fixed-weight n-bit mask."""
    assert 0 <= weight <= n
    assert 0 <= rank < math.comb(n, weight)
    mask = 0
    position = 0
    remaining = weight
    while remaining:
        options = math.comb(n - position - 1, remaining - 1)
        if rank < options:
            mask |= 1 << position
            remaining -= 1
        else:
            rank -= options
        position += 1
    return mask


def candidate_mask(n, weight, curve_id, workload_id, anchor_number, ordinal):
    tag = f"Q1427:{curve_id}:{workload_id}:{anchor_number}:{ordinal}"
    value = int.from_bytes(hashlib.sha256(tag.encode()).digest(), "big")
    return weight_mask(n, weight, value % math.comb(n, weight))


def select_anchor(*, n, weight, curve_id, workload_id, anchor_number,
                  onb, curve, cofactor, subgroup_order, exact_keys,
                  canonical_key, root_oracle, max_candidates=5000):
    """Keep the first distinct exact-base pair with an S3 intermediate."""
    counts = Counter()
    first = None
    seen_masks = set()
    for ordinal in range(max_candidates):
        counts["candidate_masks"] += 1
        xcoords = candidate_mask(n, weight, curve_id, workload_id,
                                 anchor_number, ordinal)
        if xcoords in seen_masks:
            counts["repeated_masks"] += 1
            continue
        seen_masks.add(xcoords)
        counts["point_from_x_calls"] += 1
        point = curve.pointFromX(onb.fromCoords(xcoords))
        if point is None:
            counts["nonrational"] += 1
            continue
        counts["cofactor_mul_calls"] += 1
        subgroup = curve.mul(point, cofactor)
        if subgroup is None:
            counts["identity_projection"] += 1
            continue
        counts["subgroup_order_mul_calls"] += 1
        assert curve.mul(subgroup, subgroup_order) is None
        key = canonical_key(subgroup)
        if key not in exact_keys:
            counts["outside_exact_base"] += 1
            continue
        counts["usable_candidates"] += 1
        current = {"raw_x": xcoords, "column": key, "ordinal": ordinal}
        if first is None:
            first = current
            continue
        if current["column"] == first["column"]:
            counts["duplicate_column"] += 1
            continue
        counts["root_oracle_calls"] += 1
        roots = root_oracle(first["raw_x"], current["raw_x"])
        if not roots:
            counts["zero_root_pairs"] += 1
            continue
        return {"leaves": [first, current], "roots": list(roots),
                "counts": dict(counts), "max_candidates": max_candidates}
    raise RuntimeError(f"No usable root-bearing anchor in {max_candidates} candidates")
