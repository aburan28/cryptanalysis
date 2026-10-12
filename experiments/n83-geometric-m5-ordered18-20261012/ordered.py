#!/usr/bin/env python3
"""Order the four interchangeable N83 five-summand leaves by raw x."""

import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "n83-geometric-m5-karatsuba18-20261012"
sys.path.insert(0, str(PARENT))

from karatsuba import build as parent_build  # noqa: E402
from karatsuba import N, parity, runner, selfcheck  # noqa: E402


def require_leq(formula, left, right):
    """Enforce unsigned left <= right; bit zero is least significant."""
    assert len(left) == len(right) == N
    equal_prefix = 1
    for bit in range(N - 1, -1, -1):
        # If all larger bits match, the first differing bit cannot be 1 > 0.
        formula.clauses.append([-equal_prefix, -left[bit], right[bit]])
        if bit:
            different = runner.symbolic_xor(formula, left[bit], right[bit])
            equal_prefix = formula.and_gate(equal_prefix, -different)


def build(onb, target_x, target_choice=0):
    formula, leaves, selector, inverse_rows = parent_build(
        onb, target_x, target_choice)
    for index in range(1, 4):
        require_leq(formula, leaves[index], leaves[index + 1])
    return formula, leaves, selector, inverse_rows
