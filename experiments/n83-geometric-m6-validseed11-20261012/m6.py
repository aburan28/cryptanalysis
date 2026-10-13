#!/usr/bin/env python3
"""Six-leaf S3 tree over the shifted width-11 N83 factor base."""

import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "n83-geometric-m5-karatsuba18-20261012"
sys.path.insert(0, str(PARENT))

import base_run as runner  # noqa: E402
from karatsuba import from_onb, parity, power_basis, s3_link_pb  # noqa: E402
from karatsuba import selfcheck, square_rows  # noqa: E402


N = 83
DIMENSION = 11
OFFSET = 1 << 81


def build(onb, target_x):
    """Return a fixed-target S3 tree and its six exact affine leaf domains."""
    assert onb.m == N
    powers, inverse_rows, reductions = power_basis(onb)
    squares = square_rows(onb, powers, inverse_rows)
    one = sum(parity(row & onb.toCoords(onb.one())) << bit
              for bit, row in enumerate(inverse_rows))
    formula = runner.Formula()
    rotations = []
    for power in range(N):
        sources = [-1] * N
        for source in range(DIMENSION):
            image = onb.toCoords(onb.frob(onb.fromCoords(1 << source), power))
            assert image.bit_count() == 1
            destination = image.bit_length() - 1
            assert sources[destination] == -1
            sources[destination] = source
        fixed = onb.toCoords(onb.frob(onb.fromCoords(OFFSET), power))
        assert fixed.bit_count() == 1
        assert sources[fixed.bit_length() - 1] == -1
        rotations.append((sources, fixed.bit_length() - 1))

    first_seed = [formula.new() for _ in range(DIMENSION)]
    first_leaf = [first_seed[bit] if bit < DIMENSION else
                  1 if bit == 81 else -1 for bit in range(N)]
    leaves = [first_leaf]
    seed_bits = [first_seed]
    selectors = [None]
    for _ in range(5):
        seed = [formula.new() for _ in range(DIMENSION)]
        selector = [formula.new() for _ in range(N)]
        leaf = [formula.new() for _ in range(N)]
        formula.clauses.append(selector[:])
        for left in range(N):
            for right in range(left + 1, N):
                formula.clauses.append([-selector[left], -selector[right]])
        for power, (sources, fixed_position) in enumerate(rotations):
            gate = -selector[power]
            for position, source in enumerate(sources):
                value = (seed[source] if source >= 0 else
                         1 if position == fixed_position else -1)
                formula.clauses.append([gate, -leaf[position], value])
                formula.clauses.append([gate, leaf[position], -value])
        leaves.append(leaf)
        seed_bits.append(seed)
        selectors.append(selector)

    seed_bitset = (HERE / "valid_seed_bits.bin").read_bytes()
    assert len(seed_bitset) == (1 << DIMENSION) // 8
    invalid_seeds = [free for free in range(1 << DIMENSION)
                     if not (seed_bitset[free >> 3] >> (free & 7)) & 1]
    assert len(invalid_seeds) == 951
    for seed in seed_bits:
        for free in invalid_seeds:
            formula.clauses.append([
                -literal if free >> bit & 1 else literal
                for bit, literal in enumerate(seed)])

    leaf_pb = [from_onb(formula, leaf, inverse_rows) for leaf in leaves]
    target_onb = [1 if target_x >> bit & 1 else -1 for bit in range(N)]
    target_pb = from_onb(formula, target_onb, inverse_rows)
    intermediate = [[formula.new() for _ in range(N)] for _ in range(4)]
    links = (
        (leaf_pb[0], leaf_pb[1], intermediate[0]),
        (leaf_pb[2], leaf_pb[3], intermediate[1]),
        (leaf_pb[4], leaf_pb[5], intermediate[2]),
        (intermediate[0], intermediate[1], intermediate[3]),
        (intermediate[3], intermediate[2], target_pb),
    )
    for left, right, output in links:
        s3_link_pb(formula, left, right, output, reductions, squares, one)
    formula.orbit_seed_bits = seed_bits
    formula.orbit_selectors = selectors
    formula.valid_seed_filter_clauses = len(seed_bits) * len(invalid_seeds)
    formula.intermediates = intermediate
    formula.target_x_bits = target_onb
    formula.s3_links = [(id(left), id(right), id(output))
                        for left, right, output in links]
    return formula, leaves, intermediate, inverse_rows
