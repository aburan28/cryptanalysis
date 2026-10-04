"""Compact five-leaf S3 chain and independent point-lift check.

The formula uses four factored S3 links and selects one complete raw
cofactor preimage of the public subgroup target. A SAT model is only a
candidate until the curve group law and exact factor-base membership pass.
"""

from __future__ import annotations

from itertools import product
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/compact-s3-m4-20261003"))

from chain_s3 import Formula, field, multiplication_table, square_destinations  # noqa: E402
from chain_s3_factored import s3_link_factored  # noqa: E402
from chain_s3_multitarget import choose_target_x, decode_choice  # noqa: E402


def build_formula(n: int, weight: int, target_xs: list[int]):
    """Return a five-summand chain with three free intermediate x values."""
    assert n in (53, 83) and 1 <= weight <= n
    onb = field.Onb(n)
    multiplication = multiplication_table(onb)
    square_dest = square_destinations(onb)
    formula = Formula()
    leaves = [[formula.new() for _ in range(n)] for _ in range(5)]
    intermediates = [[formula.new() for _ in range(n)] for _ in range(3)]
    for leaf in leaves:
        formula.at_most(leaf, weight)
        formula.clauses.append(leaf[:])
    target, selector = choose_target_x(formula, n, target_xs)
    for left, right, output in zip(
        [leaves[0], *intermediates],
        leaves[1:],
        [*intermediates, target],
    ):
        s3_link_factored(formula, left, right, output,
                         multiplication, square_dest)
    return formula, leaves, intermediates, selector


def pin_bits(formula, bits: list[int], value: int) -> None:
    formula.clauses.extend(([bit if (value >> i) & 1 else -bit]
                            for i, bit in enumerate(bits)))


def coordinates(bits: list[int], model: dict[int, bool]) -> int:
    return sum(1 << i for i, bit in enumerate(bits) if model.get(bit, False))


def canonical_projected_x(onb, point, n: int) -> int:
    return min(onb.toCoords(onb.frob(point[0], shift))
               for shift in range(n))


def replay_model(onb, curve, order: int, cofactor: int, weight: int,
                 base_keys: set[int], public, raw_targets, leaves, selector,
                 model: dict[int, bool]) -> dict:
    """Replay all 32 sign lifts and check the exact projected base."""
    choice = decode_choice(selector, model)
    if not 0 <= choice < len(raw_targets):
        return {"status": "invalid_target_choice", "choice": choice}
    raw_xs = [coordinates(bits, model) for bits in leaves]
    if any(not x or x.bit_count() > weight for x in raw_xs):
        return {"status": "invalid_leaf_support", "choice": choice,
                "raw_leaf_x": raw_xs}
    raw_points = [curve.pointFromX(onb.fromCoords(x)) for x in raw_xs]
    if any(point is None for point in raw_points):
        return {"status": "nonrational_leaf_x", "choice": choice,
                "raw_leaf_x": raw_xs}
    selected = raw_targets[choice]
    for signs in product((1, -1), repeat=5):
        signed = [point if sign == 1 else curve.neg(point)
                  for point, sign in zip(raw_points, signs)]
        total = None
        for point in signed:
            total = curve.add(total, point)
        if total != selected:
            continue
        assert curve.mul(total, cofactor) == public
        projected = [curve.mul(point, cofactor) for point in signed]
        if any(point is None for point in projected):
            return {"status": "projected_identity", "choice": choice,
                    "raw_leaf_x": raw_xs}
        assert all(curve.mul(point, order) is None for point in projected)
        columns = [canonical_projected_x(onb, point, onb.m)
                   for point in projected]
        if any(key not in base_keys for key in columns):
            return {"status": "outside_exact_base", "choice": choice,
                    "raw_leaf_x": raw_xs, "column_keys": columns}
        public_replay = None
        for point in projected:
            public_replay = curve.add(public_replay, point)
        assert public_replay == public
        return {
            "status": "verified_five_point_relation",
            "choice": choice,
            "raw_leaf_x": raw_xs,
            "signs": list(signs),
            "raw_leaf_points": [[str(v) for v in point]
                                for point in raw_points],
            "raw_target": [str(v) for v in selected],
            "projected_points": [[str(v) for v in point]
                                 for point in projected],
            "column_keys": columns,
            "distinct_columns": len(set(columns)) == 5,
            "public_target": [str(v) for v in public],
        }
    return {"status": "no_sign_lift", "choice": choice,
            "raw_leaf_x": raw_xs}
