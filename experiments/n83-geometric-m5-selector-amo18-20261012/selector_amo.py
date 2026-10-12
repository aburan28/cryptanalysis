#!/usr/bin/env python3
"""Exact sequential at-most-one encoding for N83 leaf Frobenius selectors."""

import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/n83-geometric-m5-karatsuba18-20261012"
sys.path.insert(0, str(PARENT))
import base_run as runner  # noqa: E402
from karatsuba import build as parent_karatsuba_build, selfcheck  # noqa: E402


def exactly_one(formula, selector):
    """Sinz sequential at-most-one plus an at-least-one clause."""
    assert len(selector) >= 2
    formula.clauses.append(selector[:])
    prefix = [formula.new() for _ in range(len(selector) - 1)]
    formula.clauses.append([-selector[0], prefix[0]])
    for index in range(1, len(selector) - 1):
        formula.clauses.append([-selector[index], prefix[index]])
        formula.clauses.append([-prefix[index - 1], prefix[index]])
        formula.clauses.append([-selector[index], -prefix[index - 1]])
    formula.clauses.append([-selector[-1], -prefix[-1]])


def selfcheck_exactly_one():
    for width in range(2, 7):
        formula = runner.Formula()
        selector = [formula.new() for _ in range(width)]
        exactly_one(formula, selector)
        prefix = list(range(selector[-1] + 1, formula.variables + 1))
        assert len(prefix) == width - 1
        for mask in range(1 << width):
            satisfiable = False
            for aux in range(1 << len(prefix)):
                values = {1: True}
                values.update({literal: bool(mask >> index & 1)
                               for index, literal in enumerate(selector)})
                values.update({literal: bool(aux >> index & 1)
                               for index, literal in enumerate(prefix)})
                if all(any(values[abs(literal)] == (literal > 0)
                           for literal in clause)
                       for clause in formula.clauses):
                    satisfiable = True
                    break
            assert satisfiable == (mask.bit_count() == 1)
    return {"status": "PASS", "exhaustive_widths": [2, 3, 4, 5, 6]}


def build_affine_formula_amo(dimension, offset, target_xs, onb,
                             target_choice=0):
    assert dimension == 18 and offset == 1 << 81
    assert len(target_xs) == 332 and 0 <= target_choice < len(target_xs)
    n = 83
    formula = runner.Formula()
    rotations = []
    for power in range(n):
        sources = [-1] * n
        for source in range(dimension):
            image = onb.toCoords(onb.frob(onb.fromCoords(1 << source), power))
            assert image.bit_count() == 1
            destination = image.bit_length() - 1
            assert sources[destination] == -1
            sources[destination] = source
        fixed = onb.toCoords(onb.frob(onb.fromCoords(offset), power))
        assert fixed.bit_count() == 1
        assert sources[fixed.bit_length() - 1] == -1
        rotations.append((sources, fixed.bit_length() - 1))
    first_seed = [formula.new() for _ in range(dimension)]
    first_leaf = [first_seed[bit] if bit < dimension else
                  1 if bit == 81 else -1 for bit in range(n)]
    leaves = [first_leaf]
    seed_bits = [first_seed]
    orbit_selectors = [None]
    for _ in range(4):
        seed = [formula.new() for _ in range(dimension)]
        selector = [formula.new() for _ in range(n)]
        leaf = [formula.new() for _ in range(n)]
        exactly_one(formula, selector)
        for power, (sources, fixed_position) in enumerate(rotations):
            gate = -selector[power]
            for position, source in enumerate(sources):
                value = (seed[source] if source >= 0 else
                         1 if position == fixed_position else -1)
                formula.clauses.append([gate, -leaf[position], value])
                formula.clauses.append([gate, leaf[position], -value])
        leaves.append(leaf)
        seed_bits.append(seed)
        orbit_selectors.append(selector)
    intermediates = [[formula.new() for _ in range(n)] for _ in range(3)]
    chosen_x = target_xs[target_choice]
    target = [1 if chosen_x >> bit & 1 else -1 for bit in range(n)]
    target_selector = [1 if target_choice >> bit & 1 else -1
                       for bit in range(9)]
    multiplication = runner.multiplication_table(onb)
    square_dest = runner.square_destinations(onb)
    for left, right, output in (
        (leaves[0], leaves[1], intermediates[0]),
        (leaves[2], leaves[3], intermediates[1]),
        (intermediates[0], intermediates[1], intermediates[2]),
        (intermediates[2], leaves[4], target),
    ):
        runner.s3_link_folded(formula, left, right, output,
                              multiplication, square_dest)
    formula.orbit_seed_bits = seed_bits
    formula.orbit_selectors = orbit_selectors
    formula.intermediates = intermediates
    formula.target_x_bits = target
    formula.fixed_target_choice = target_choice
    return formula, leaves, target_selector


def build(onb, target_x, target_choice=0):
    original = runner.build_affine_formula
    runner.build_affine_formula = build_affine_formula_amo
    try:
        return parent_karatsuba_build(onb, target_x, target_choice)
    finally:
        runner.build_affine_formula = original


def main():
    result = json.loads((PARENT / "width18_ordinary.json").read_text())
    onb = runner.field.Onb(83)
    correctness = selfcheck(onb)
    selector_correctness = selfcheck_exactly_one()
    formula, _, _, _ = build(onb, result["formula_target_x"])
    print(json.dumps({"status": "PASS", "amo_shape": runner.stats(formula),
                      "pairwise_shape": result["formula_shape"],
                      "field_selfcheck": correctness,
                      "selector_selfcheck": selector_correctness}, sort_keys=True))


if __name__ == "__main__":
    main()
