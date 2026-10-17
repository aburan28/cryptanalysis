#!/usr/bin/env python3
"""Exact unit-class partition search for the norm-4831 affine digit table.

The cost is a declared source-operation model, not a wall-time prediction.
Every schedule evaluates the same signed unit-coded point sum.
"""

from dataclasses import dataclass
from itertools import product
import json
import math


GENERIC_FIELD_PRODUCTS = 36
SOLINAS_BETA_PRODUCTS = 23
MIXED_MULTIPLIES = 8
PROJECTIVE_MULTIPLIES = 12


@dataclass(frozen=True)
class Schedule:
    # One (unit-power subset, accumulator orientation) per group.
    groups: tuple[tuple[tuple[int, ...], int], ...]

    def counts(self, class_counts: tuple[int, int, int], terminal: bool = True) -> dict:
        active = [(members, anchor, sum(class_counts[c] for c in members))
                  for members, anchor in self.groups]
        active = [(members, anchor, size) for members, anchor, size in active if size]
        n = sum(class_counts)
        if not n:
            return {"mixed_adds": 0, "projective_joins": 0,
                    "beta_products": 0, "source_products": 0}
        mixed = n - len(active) + int(terminal)
        joins = len(active) - 1
        beta = sum(sum(class_counts[c] for c in members if c != anchor)
                   + int(anchor != 0) for members, anchor, _ in active)
        source = (mixed * MIXED_MULTIPLIES * GENERIC_FIELD_PRODUCTS
                  + joins * PROJECTIVE_MULTIPLIES * GENERIC_FIELD_PRODUCTS
                  + beta * SOLINAS_BETA_PRODUCTS)
        return {"mixed_adds": mixed, "projective_joins": joins,
                "beta_products": beta, "source_products": source}


def all_schedules() -> tuple[Schedule, ...]:
    # Canonical restricted-growth labels enumerate all five set partitions.
    partitions = ((0, 0, 0), (0, 0, 1), (0, 1, 0),
                  (0, 1, 1), (0, 1, 2))
    result = []
    for labels in partitions:
        members = tuple(tuple(c for c, label in enumerate(labels) if label == group)
                        for group in range(max(labels) + 1))
        for anchors in product(range(3), repeat=len(members)):
            result.append(Schedule(tuple(zip(members, anchors, strict=True))))
    return tuple(result)


SCHEDULES = all_schedules()
DIRECT = Schedule((((0, 1, 2), 0),))
THREE_BUCKET = Schedule((((0,), 0), ((1,), 1), ((2,), 2)))


def best_schedule(class_counts: tuple[int, int, int]) -> tuple[Schedule, dict]:
    if len(class_counts) != 3 or any(not isinstance(n, int) or n < 0 for n in class_counts):
        raise ValueError("three nonnegative integer class counts required")
    schedule, cost = min(((schedule, schedule.counts(class_counts)) for schedule in SCHEDULES),
               key=lambda item: (item[1]["source_products"],
                                 item[1]["projective_joins"],
                                 item[1]["beta_products"], item[0].groups))
    active = Schedule(tuple((tuple(c for c in members if class_counts[c]), anchor)
                            for members, anchor in schedule.groups
                            if any(class_counts[c] for c in members)))
    assert active.counts(class_counts) == cost
    return active, cost


def omega(pair: tuple[int, int]) -> tuple[int, int]:
    # tau^2 - 3 tau + 3 = 0; omega = tau - 2.
    a, b = pair
    return -2 * a - 3 * b, a + b


def rotate(pair: tuple[int, int], power: int) -> tuple[int, int]:
    for _ in range(power % 3):
        pair = omega(pair)
    return pair


def add(left: tuple[int, int], right: tuple[int, int]) -> tuple[int, int]:
    return left[0] + right[0], left[1] + right[1]


def verify_schedule_identity(schedule: Schedule) -> None:
    """Check the three basis classes; linearity then covers all term values."""
    covered = sorted(c for members, _ in schedule.groups for c in members)
    assert covered == [0, 1, 2]
    for source_class in range(3):
        for basis in ((1, 0), (0, 1)):
            result = (0, 0)
            for members, anchor in schedule.groups:
                bucket = (0, 0)
                if source_class in members:
                    bucket = rotate(basis, (source_class - anchor) % 3)
                result = add(result, rotate(bucket, anchor))
            assert result == rotate(basis, source_class), (schedule, source_class, basis)


def audit(max_digits: int = 20) -> dict:
    for schedule in SCHEDULES:
        verify_schedule_identity(schedule)
    families = {1: 0, 2: 0, 3: 0}
    improvements = []
    triple_count = 0
    weighted_saved = 0
    weighted_two_group = 0
    total_weight = 3 ** max_digits
    for n0 in range(max_digits + 1):
        for n1 in range(max_digits - n0 + 1):
            n2 = max_digits - n0 - n1
            counts = n0, n1, n2
            schedule, cost = best_schedule(counts)
            direct = DIRECT.counts(counts)
            three = THREE_BUCKET.counts(counts)
            assert cost["source_products"] <= direct["source_products"]
            assert cost["source_products"] <= three["source_products"]
            active_groups = sum(any(counts[c] for c in members)
                                for members, _ in schedule.groups)
            families[active_groups] += 1
            triple_count += 1
            weight = (math.factorial(max_digits) //
                      (math.factorial(n0) * math.factorial(n1) * math.factorial(n2)))
            weighted_saved += weight * (direct["source_products"] - cost["source_products"])
            weighted_two_group += weight * (active_groups == 2)
            if cost["source_products"] < direct["source_products"]:
                improvements.append({"counts": counts,
                                     "saved_source_products": direct["source_products"]
                                     - cost["source_products"],
                                     "groups": schedule.groups,
                                     "operations": cost})
    return {"source_model": {"generic_field_products": GENERIC_FIELD_PRODUCTS,
                              "solinas_beta_products": SOLINAS_BETA_PRODUCTS,
                              "mixed_multiplies": MIXED_MULTIPLIES,
                              "projective_multiplies": PROJECTIVE_MULTIPLIES},
            "digits": max_digits, "count_triples": triple_count,
            "chosen_group_count": families,
            "uniform_class_model_expected_saved_products": weighted_saved / total_weight,
            "uniform_class_model_two_group_probability": weighted_two_group / total_weight,
            "better_than_direct_triples": len(improvements),
            "maximum_saved_source_products": max(
                (item["saved_source_products"] for item in improvements), default=0),
            "examples": sorted(improvements,
                               key=lambda item: (-item["saved_source_products"], item["counts"]))[:8]}


if __name__ == "__main__":
    print(json.dumps(audit(), sort_keys=True, indent=2))
