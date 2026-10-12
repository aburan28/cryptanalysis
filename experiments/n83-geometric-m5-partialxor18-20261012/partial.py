#!/usr/bin/env python3
"""Materialize selected Karatsuba recursion outputs on the frozen N83 gate."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FLAT = HERE.parent / "n83-geometric-m5-flatxor18-20261012"
sys.path.insert(0, str(FLAT))
import flat_karatsuba as flat  # noqa: E402


def build(onb, target_x, cutoff, target_choice=0):
    """Cut XOR expressions at each recursion node of the given length."""
    if cutoff not in (0, 2, 3, 6, 11, 21, 42):
        raise ValueError("cutoff must be a Karatsuba recursion length")
    original = flat.karatsuba

    def partial(formula, left, right):
        result = original(formula, left, right)
        if len(left) == cutoff:
            return [flat.literal_expression(
                flat.materialize_expression(formula, expression))
                for expression in result]
        return result

    flat.karatsuba = partial
    try:
        return flat.build(onb, target_x, target_choice)
    finally:
        flat.karatsuba = original
