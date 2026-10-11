"""Factorized-convolution Hamming constraints over a Boolean XCNF circuit.

This is the balanced-tree construction of La Scala--Marchesin--Tiwari,
Theorem 4.5 (arXiv:2609.18866).  We retain every binary weight digit through
floor(log2(n)); the paper also describes a complement-based truncation.
"""

from __future__ import annotations


def require_exact_weight(circuit, variables: list[int], weight: int) -> dict:
    n = len(variables)
    if not 0 <= weight <= n:
        raise ValueError("weight must lie between zero and the vector length")

    node_count = 0
    convolution_terms = 0

    def combine(left: tuple, right: tuple) -> tuple:
        nonlocal node_count, convolution_terms
        left_size, left_powers = left
        right_size, right_powers = right
        size = left_size + right_size
        node_count += 1
        cache_left = {0: -1}
        cache_right = {0: -1}

        def elementary(degree: int, child_size: int, powers: dict,
                       cache: dict) -> int:
            if degree > child_size:
                return 0
            if degree in cache:
                return cache[degree]
            factors = [powers[1 << bit] for bit in range(degree.bit_length())
                       if degree & (1 << bit)]
            result = -1
            for factor in factors:
                result = circuit.and_(result, factor)
            cache[degree] = result
            return result

        powers = {}
        degree = 1
        while degree <= size:
            terms = []
            lo = max(0, degree - right_size)
            hi = min(degree, left_size)
            for j in range(lo, hi + 1):
                a = elementary(j, left_size, left_powers, cache_left)
                b = elementary(degree - j, right_size, right_powers,
                               cache_right)
                terms.append(circuit.and_(a, b))
                convolution_terms += 1
            powers[degree] = circuit.xor(terms)
            degree <<= 1
        return size, powers

    def visit(values: list[int]) -> tuple:
        if len(values) == 1:
            return 1, {1: values[0]}
        middle = len(values) // 2
        return combine(visit(values[:middle]), visit(values[middle:]))

    _, root = visit(variables)
    for degree, wire in root.items():
        wanted = bool(weight & degree)
        if wire == -1:
            if not wanted:
                circuit.clauses.append("0")
        elif wire == 0:
            if wanted:
                circuit.clauses.append("0")
        else:
            circuit.clauses.append(f"{wire if wanted else -wire} 0")
    return {"root_powers": root, "tree_internal_nodes": node_count,
            "convolution_terms": convolution_terms,
            "paper": "https://arxiv.org/abs/2609.18866",
            "construction": "Theorem 4.5 FC-Hamming, full binary weight digits"}
