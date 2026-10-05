"""Exact bounded four-leaf join with both S3 intermediates left free.

This is an x-coordinate feasibility oracle. ``no_chain`` is a sound reason
to reject the fixed leaf bits, because every completion within the declared
weight bound is enumerated. A returned x-only witness still needs curve,
subgroup, sign, and distinct-column replay before it is a relation.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

from s3_root_oracle import s3_roots


@dataclass(frozen=True)
class PartialLeaf:
    fixed_mask: int
    fixed_ones: int


def options(leaf: PartialLeaf, n: int, weight: int) -> tuple[int, ...]:
    full = (1 << n) - 1
    if leaf.fixed_mask & ~full or leaf.fixed_ones & ~leaf.fixed_mask:
        raise ValueError("invalid partial leaf masks")
    slack = weight - leaf.fixed_ones.bit_count()
    if slack < 0:
        return ()
    free = [j for j in range(n) if not (leaf.fixed_mask >> j & 1)]
    answer = [leaf.fixed_ones | sum(1 << j for j in selected)
              for size in range(min(slack, len(free)) + 1)
              for selected in itertools.combinations(free, size)]
    return tuple(value for value in answer if value)


def option_count(leaf: PartialLeaf, n: int, weight: int) -> int:
    """Exact number of nonzero sparse completions without listing them."""
    from math import comb

    full = (1 << n) - 1
    if leaf.fixed_mask & ~full or leaf.fixed_ones & ~leaf.fixed_mask:
        raise ValueError("invalid partial leaf masks")
    slack = weight - leaf.fixed_ones.bit_count()
    if slack < 0:
        return 0
    free = n - leaf.fixed_mask.bit_count()
    count = sum(comb(free, j) for j in range(min(slack, free) + 1))
    return count - int(leaf.fixed_ones == 0)


def join(onb, leaves: tuple[PartialLeaf, ...], target_x: int,
         weight: int, pair_cap: int) -> dict:
    """Return one exact x-only chain, reject it, or skip over-budget domains.

    ``pair_cap`` bounds each pair's product of leaf completion counts. A
    skipped state carries no logical conclusion. The target and leaf x values
    are normal-basis coordinate masks in the field declared by ``onb``.
    """
    if len(leaves) != 4 or not 0 < target_x < (1 << onb.m):
        raise ValueError("four leaves and a nonzero field target are required")
    if not 0 < weight < onb.m or pair_cap <= 0:
        raise ValueError("invalid weight or pair cap")
    counts = [option_count(leaf, onb.m, weight) for leaf in leaves]
    pair_counts = [counts[0] * counts[1], counts[2] * counts[3]]
    result = {"status": "skipped", "leaf_option_counts": counts,
              "pair_candidate_counts": pair_counts,
              "pair_cap": pair_cap, "pair_root_calls": [0, 0],
              "final_root_calls": 0, "distinct_pair_outputs": [0, 0],
              "witness": None}
    if max(pair_counts) > pair_cap:
        return result

    domains = [options(leaf, onb.m, weight) for leaf in leaves]
    assert [len(domain) for domain in domains] == counts
    elements = [{value: onb.fromCoords(value) for value in domain}
                for domain in domains]
    right_outputs: dict[int, tuple[int, int]] = {}
    for c, d in itertools.product(domains[2], domains[3]):
        result["pair_root_calls"][1] += 1
        for root in s3_roots(onb, elements[2][c], elements[3][d]):
            right_outputs.setdefault(onb.toCoords(root), (c, d))
    result["distinct_pair_outputs"][1] = len(right_outputs)

    target = onb.fromCoords(target_x)
    seen_left: set[int] = set()
    for a, b in itertools.product(domains[0], domains[1]):
        result["pair_root_calls"][0] += 1
        for middle in s3_roots(onb, elements[0][a], elements[1][b]):
            middle_x = onb.toCoords(middle)
            if middle_x in seen_left:
                continue
            seen_left.add(middle_x)
            result["final_root_calls"] += 1
            partners = (s3_roots(onb, middle, target) if middle else
                        (onb.inv(target),))
            for partner in partners:
                partner_x = onb.toCoords(partner)
                if partner_x in right_outputs:
                    c, d = right_outputs[partner_x]
                    result["status"] = "x_only_witness"
                    result["distinct_pair_outputs"][0] = len(seen_left)
                    result["witness"] = {
                        "leaf_x": [a, b, c, d],
                        "pair_output_x": [middle_x, partner_x],
                        "target_x": target_x,
                    }
                    return result
    result["status"] = "no_chain"
    result["distinct_pair_outputs"][0] = len(seen_left)
    return result
